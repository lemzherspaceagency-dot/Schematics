class_name GameSim
extends DrawKit
# Game state + simulation: accounts, player slots, level setup, chefs, machines, customers, scoring.
# main.gd extends this and adds all the drawing / screens.

const NO_CELL := Vector2i(-1, -1)

enum S { LOADING, MENU, LEVELS, SHOP, BRIEF, PLAY, PAUSE, RESULT, PLAYERS, CUSTOMIZE, PROFILES, NAME, ONLINE }

# keyboard schemes, one per player slot
const KEYS := [
	{"up": KEY_W, "down": KEY_S, "left": KEY_A, "right": KEY_D, "act": [KEY_E, KEY_SPACE], "label": "WASD + E"},
	{"up": KEY_UP, "down": KEY_DOWN, "left": KEY_LEFT, "right": KEY_RIGHT, "act": [KEY_ENTER, KEY_KP_ENTER], "label": "Arrows + Enter"},
	{"up": KEY_I, "down": KEY_K, "left": KEY_J, "right": KEY_L, "act": [KEY_U], "label": "IJKL + U"},
	{"up": KEY_T, "down": KEY_G, "left": KEY_F, "right": KEY_H, "act": [KEY_R], "label": "TFGH + R"},
]

var sfx: Sfx
var acc := Accounts.new()

var state: S = S.LOADING
var pending := -1                  # screen we are fading towards (-1 = none)
var fade := 1.0                    # 0 clear .. 1 black

# ---- player slots (local co-op) ----
var slots: Array = []              # 4 x {on, pid, look, name}

# ---- network (see net.gd). 0 offline, 1 host, 2 client ----
var net_mode := 0
var ev_out: Array = []             # fx events queued for clients while hosting

# ---- grid / level ----
var cur_level := 0
var world := 0
var lv: Dictionary = {}
var map: Array = []
var astar := AStarGrid2D.new()
var stations := {}                 # Vector2i -> Dictionary
var plates := {}                   # Vector2i -> Array of items
var all_seats: Array = []          # every table on the map (priority order)
var chair_of := {}                 # table cell -> the chair cell its customer sits on
var seats: Array = []              # seats open this level
var chefs: Array[Chef] = []
var customers: Array = []
var pops := {}                     # Vector2i -> seconds left of a "bounce" on that tile

# ---- level run ----
var time_left := 0.0
var intro := 0.0
var earned := 0
var served := 0
var lost := 0
var streak := 0
var best_streak := 0
var spawn_timer := 0.0
var rush_shown := false
var banner := ""
var show_recipes := false
var banner_t := 0.0
var earned_shown := 0.0
var coins_shown := 0.0
var float_icons: Array = []

# ---- result ----
var result_t := 0.0
var result_stars := 0
var result_new_best := false
var level_unlocked_msg := false
var result_payouts: Array = []     # [{name, look, coins}]
var result_bonus := 1.0


# ====================================================================
# Accounts, slots, upgrades
# ====================================================================

func _prof() -> Dictionary:
	return acc.get_profile(acc.active)


func _ulv(id: String) -> int:
	return int((_prof().get("upg", {}) as Dictionary).get(id, 0))


func _stars_of(i: int) -> int:
	return int((_prof().get("stars", []) as Array)[i])


func _unlocked(i: int) -> bool:
	return i == 0 or _stars_of(i - 1) >= 1


func _init_slots() -> void:
	slots = []
	for i in Data.MAX_PLAYERS:
		slots.append({"on": i == 0, "pid": "", "look": Data.default_look(i), "name": "Guest %d" % (i + 1)})
	slots[0]["pid"] = acc.active


func _slot_profile(i: int) -> Dictionary:
	var pid: String = slots[i]["pid"]
	return acc.get_profile(pid)


func _slot_name(i: int) -> String:
	var p := _slot_profile(i)
	if not p.is_empty():
		return str(p["name"])
	return str(slots[i]["name"])


func _slot_look(i: int) -> Dictionary:
	var p := _slot_profile(i)
	if not p.is_empty():
		return p["look"]
	return slots[i]["look"]


func _nplayers() -> int:
	var n := 0
	for s in slots:
		if bool(s["on"]):
			n += 1
	n += _remote_defs().size()
	return clampi(n, 1, Data.MAX_PLAYERS)


func _goals() -> Array:
	var base: Array = lv["goals"] if not lv.is_empty() else Data.LEVELS[cur_level]["goals"]
	var k := 1.0 + 0.55 * float(_nplayers() - 1)
	var out: Array = []
	for g in base:
		out.append(int(round(float(g) * k / 5.0)) * 5)
	return out


# ====================================================================
# Hooks main.gd / net.gd override
# ====================================================================

func _on_level_started() -> void:
	pass


func _on_level_ended() -> void:
	pass


func _remote_defs() -> Array:
	return []


# ====================================================================
# Level setup
# ====================================================================

func _setup_map(w: int) -> void:
	world = w
	map = Data.WORLDS[w]["map"]
	astar = AStarGrid2D.new()
	astar.region = Rect2i(0, 0, Data.COLS, Data.ROWS)
	astar.cell_size = Vector2(TILE, TILE)
	astar.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_NEVER
	astar.update()
	all_seats = []
	chair_of = {}
	for y in Data.ROWS:
		for x in Data.COLS:
			var k: String = map[y][x]
			if not (k in ".w"):
				astar.set_point_solid(Vector2i(x, y), true)
			if k == "T":
				all_seats.append(Vector2i(x, y))
	# every table gets the chair standing next to it (north first, so customers face the camera)
	for t in all_seats:
		var tc: Vector2i = t
		for d in [Vector2i(0, -1), Vector2i(-1, 0), Vector2i(1, 0), Vector2i(0, 1)]:
			var n: Vector2i = tc + (d as Vector2i)
			if n.x >= 0 and n.y >= 0 and n.x < Data.COLS and n.y < Data.ROWS and map[n.y][n.x] == "c" and not chair_of.values().has(n):
				chair_of[tc] = n
				break
	# tables are filled centre-out
	var mid := 0.0
	for s in all_seats:
		mid += float(Vector2i(s).x)
	mid /= maxf(1.0, float(all_seats.size()))
	all_seats.sort_custom(func(a, b): return absf(float(a.x) - mid) < absf(float(b.x) - mid))


func _build_chefs(spawn_list: Array) -> void:
	chefs = []
	var idx := 0
	for i in Data.MAX_PLAYERS:
		if not bool(slots[i]["on"]):
			continue
		var ch := Chef.new()
		ch.id = idx
		ch.scheme = i
		ch.name = _slot_name(i)
		ch.profile_id = str(slots[i]["pid"])
		ch.look = (_slot_look(i) as Dictionary).duplicate()
		ch.pos = _cell_center(spawn_list[idx % spawn_list.size()])
		ch.held_pos = ch.pos
		chefs.append(ch)
		idx += 1
	# network players take the remaining spots
	for r in _remote_defs():
		if chefs.size() >= Data.MAX_PLAYERS:
			break
		var rc := Chef.new()
		rc.id = chefs.size()
		rc.name = str(r["name"])
		rc.look = (r["look"] as Dictionary).duplicate()
		rc.remote = true
		rc.peer = int(r["peer"])
		rc.pos = _cell_center(spawn_list[rc.id % spawn_list.size()])
		rc.held_pos = rc.pos
		chefs.append(rc)


func _start_level(i: int) -> void:
	cur_level = i
	lv = Data.LEVELS[i]
	_setup_map(i / 5)
	time_left = float(lv["time"])
	earned = 0
	served = 0
	lost = 0
	streak = 0
	best_streak = 0
	customers = []
	particles = []
	popups = []
	pops = {}
	spawn_timer = 1.5
	rush_shown = false
	banner_t = 0.0
	shake = 0.0
	earned_shown = 0.0
	stations = {}
	plates = {}
	for y in Data.ROWS:
		for x in Data.COLS:
			var k: String = map[y][x]
			if Data.RULES.has(k):
				stations[Vector2i(x, y)] = {"in": "", "out": "", "t": 0.0, "st": "idle", "puff": 0.0}
			elif k == "A":
				plates[Vector2i(x, y)] = []
	var n := _nplayers()
	var open := mini(all_seats.size(), int(lv["seats"]) + (n - 1) / 2)
	seats = []
	for k in open:
		seats.append(all_seats[k])
	_build_chefs(Data.WORLDS[world]["spawns"])
	intro = 3.0
	state_t = 0.0
	state = S.PLAY
	_on_level_started()


func _end_level() -> void:
	var goals := _goals()
	result_stars = 0
	for g in goals:
		if earned >= int(g):
			result_stars += 1
	var host := _prof()
	result_new_best = result_stars > _stars_of(cur_level)
	level_unlocked_msg = false
	var n := _nplayers()
	result_bonus = Data.coop_multiplier(n)
	result_payouts = []
	var credited := {}
	for ch in chefs:
		var pid := ch.profile_id
		var pay := int(round(earned * result_bonus))
		result_payouts.append({"name": ch.name, "look": ch.look, "coins": pay, "served": ch.served, "guest": pid == "" or not acc.profiles.has(pid)})
		if pid != "" and acc.profiles.has(pid) and not credited.has(pid):
			credited[pid] = true
			var p: Dictionary = acc.get_profile(pid)
			p["coins"] = int(p["coins"]) + pay
			var st: Dictionary = p["stats"]
			st["served"] = int(st["served"]) + ch.served
			st["games"] = int(st["games"]) + 1
			st["coins_earned"] = int(st["coins_earned"]) + pay
			if n > 1:
				st["coop_games"] = int(st["coop_games"]) + 1
			st["best_combo"] = maxi(int(st["best_combo"]), best_streak)
			var stars_arr: Array = p["stars"]
			if cur_level + 1 < stars_arr.size() and int(stars_arr[cur_level]) == 0 and result_stars > 0 and pid == acc.active:
				level_unlocked_msg = true
			stars_arr[cur_level] = maxi(int(stars_arr[cur_level]), result_stars)
	if host.is_empty():
		pass
	acc.save_all()
	result_t = 0.0
	state_t = 0.0
	state = S.RESULT
	_snd("win" if result_stars > 0 else "lose")
	_on_level_ended()


# ====================================================================
# Input -> chefs
# ====================================================================

# keys that drive this chef; a solo player on slot 1 may also use the arrow keys
func _schemes_for(ch: Chef) -> Array:
	var out: Array = [ch.scheme]
	if ch.scheme == 0 and slots.size() > 1 and not bool(slots[1]["on"]):
		out.append(1)
	return out


func _scheme_dir(ch: Chef) -> Vector2i:
	var d := Vector2i.ZERO
	for si in _schemes_for(ch):
		var k: Dictionary = KEYS[si]
		if Input.is_physical_key_pressed(k["left"]):
			d.x -= 1
		if Input.is_physical_key_pressed(k["right"]):
			d.x += 1
		if Input.is_physical_key_pressed(k["up"]):
			d.y -= 1
		if Input.is_physical_key_pressed(k["down"]):
			d.y += 1
	var dev := ch.scheme
	if Input.get_connected_joypads().has(dev):
		var ax := Input.get_joy_axis(dev, JOY_AXIS_LEFT_X)
		var ay := Input.get_joy_axis(dev, JOY_AXIS_LEFT_Y)
		if ax < -0.5 or Input.is_joy_button_pressed(dev, JOY_BUTTON_DPAD_LEFT):
			d.x -= 1
		if ax > 0.5 or Input.is_joy_button_pressed(dev, JOY_BUTTON_DPAD_RIGHT):
			d.x += 1
		if ay < -0.5 or Input.is_joy_button_pressed(dev, JOY_BUTTON_DPAD_UP):
			d.y -= 1
		if ay > 0.5 or Input.is_joy_button_pressed(dev, JOY_BUTTON_DPAD_DOWN):
			d.y += 1
	d.x = clampi(d.x, -1, 1)
	d.y = clampi(d.y, -1, 1)
	# one axis at a time: keep going the way we were facing if both are held
	if d.x != 0 and d.y != 0:
		if ch.dir.x != 0:
			d.y = 0
		else:
			d.x = 0
	return d


# ---- the 3D camera (world3d.gd) ----
var view: KitchenView = null


func _tilted() -> bool:
	return state == S.PLAY or state == S.PAUSE


func _project(p: Vector2) -> Vector2:
	if view == null or not _tilted():
		return p
	return view.project(p, 0.0)


func _unproject(p: Vector2) -> Vector2:
	if view == null:
		return p
	return view.pick(p)


func _cell_of(p: Vector2) -> Vector2i:
	return Vector2i(((p - ORIGIN) / TILE).floor())


func _cell_center(c: Vector2i) -> Vector2:
	return ORIGIN + (Vector2(c) + Vector2(0.5, 0.5)) * TILE


func _walkable(c: Vector2i) -> bool:
	return c.x >= 0 and c.y >= 0 and c.x < Data.COLS and c.y < Data.ROWS and map[c.y][c.x] in ".w"


func _is_interactive(c: Vector2i) -> bool:
	if c.x < 0 or c.y < 0 or c.x >= Data.COLS or c.y >= Data.ROWS:
		return false
	var k: String = map[c.y][c.x]
	if k == "T":
		return seats.has(c)
	return k in "MVDCSOAB"


func _cell_blocked(ch: Chef, n: Vector2i) -> bool:
	for o in chefs:
		if o == ch:
			continue
		if _cell_of(o.pos) == n:
			return true
		if not o.path.is_empty() and o.path[0] == n and o.id < ch.id:
			return true
	return false


func _chef_act(ch: Chef) -> void:
	if state != S.PLAY or intro > 0.0:
		return
	var c := _cell_of(ch.pos)
	var dirs: Array = [ch.dir, Vector2i(0, -1), Vector2i(0, 1), Vector2i(-1, 0), Vector2i(1, 0)]
	for d in dirs:
		var n: Vector2i = c + (d as Vector2i)
		if _is_interactive(n):
			ch.dir = d
			if d.x != 0:
				ch.face = float(d.x)
			_interact(ch, n)
			return


# Mouse / touch: tap the floor to walk, tap a station to walk there and use it. Controls chef 0.
func _on_game_tap(p: Vector2) -> void:
	if chefs.is_empty() or chefs[0].remote:
		return
	_chef_tap(chefs[0], p)


func _chef_tap(ch: Chef, p: Vector2) -> void:
	var cell := _pos_to_cell(p)
	if cell.x < 0 or cell.y < 0 or cell.x >= Data.COLS or cell.y >= Data.ROWS:
		return
	var kind: String = map[cell.y][cell.x]
	var start := _cell_of(ch.pos)
	if kind in ".w":
		ch.path = _path(ch, start, cell)
		ch.target = NO_CELL
		return
	if kind == "c":
		# tapping a customer's chair: that table
		for t in chair_of:
			if chair_of[t] == cell:
				cell = t
				kind = "T"
	if kind == "T" and not seats.has(cell):
		return
	if not (kind in "MVDCSOABT"):
		return
	_walk_to_station(ch, cell, start)


func _pos_to_cell(p: Vector2) -> Vector2i:
	return Vector2i(((p - ORIGIN) / TILE).floor())


func _path(ch: Chef, from: Vector2i, to: Vector2i) -> Array[Vector2i]:
	# other chefs count as walls while we plan (restored straight after)
	var toggled: Array[Vector2i] = []
	for o in chefs:
		if o == ch:
			continue
		var oc := _cell_of(o.pos)
		if oc != to and oc != from and astar.is_in_boundsv(oc) and not astar.is_point_solid(oc):
			astar.set_point_solid(oc, true)
			toggled.append(oc)
	var result := astar.get_id_path(from, to)
	for c in toggled:
		astar.set_point_solid(c, false)
	if result.is_empty():
		result = astar.get_id_path(from, to)
	var out: Array[Vector2i] = []
	for c in result:
		out.append(c)
	return out


func _walk_to_station(ch: Chef, cell: Vector2i, start: Vector2i) -> void:
	var best: Array[Vector2i] = []
	var best_score := 9999
	for d in [Vector2i(0, 1), Vector2i(0, -1), Vector2i(1, 0), Vector2i(-1, 0)]:
		var n: Vector2i = cell + d
		if not _walkable(n):
			continue
		var candidate := _path(ch, start, n)
		if candidate.is_empty():
			continue
		# prefer a free spot next to the station over one somebody is standing on
		var score := candidate.size()
		for o in chefs:
			if o != ch and (_cell_of(o.pos) == n or (not o.path.is_empty() and o.path[o.path.size() - 1] == n)):
				score += 8
		if score < best_score:
			best_score = score
			best = candidate
	if not best.is_empty():
		ch.path = best
		ch.target = cell


# ====================================================================
# Simulation tick
# ====================================================================

func _update_game(delta: float) -> void:
	if intro > 0.0:
		var prev := ceili(intro)
		intro -= delta
		if intro <= 0.0:
			_snd("go")
			_banner("GO!")
		elif ceili(intro) != prev:
			_snd("tick")
		return
	time_left -= delta
	if time_left <= 0.0:
		time_left = 0.0
		_end_level()
		return
	if time_left < 20.0 and not rush_shown:
		rush_shown = true
		_banner("RUSH HOUR!")
		_snd("bell")
	for ch in chefs:
		_update_chef(ch, delta)
	_update_stations(delta)
	_update_customers(delta)


func _update_chef(ch: Chef, delta: float) -> void:
	var top: float = 260.0 * (1.0 + 0.12 * _ulv("boots"))
	# controller input
	if not ch.remote:
		ch.in_dir = _scheme_dir(ch)
	if ch.in_dir != Vector2i.ZERO:
		ch.dir = ch.in_dir
		if ch.in_dir.x != 0:
			ch.face = lerpf(ch.face, float(ch.in_dir.x), 0.5)
		ch.target = NO_CELL
		if ch.path.size() > 1:
			ch.path = [ch.path[0]]
		if ch.path.size() <= 1:
			var base: Vector2i = ch.path[0] if not ch.path.is_empty() else _cell_of(ch.pos)
			var nxt: Vector2i = base + ch.in_dir
			if _walkable(nxt):
				ch.path.append(nxt)
	ch.bump = maxf(0.0, ch.bump - delta * 3.0)
	if ch.path.is_empty():
		ch.vel = ch.vel.move_toward(Vector2.ZERO, 3000.0 * delta)
		ch.moving = false
		ch.blocked = 0.0
		return
	var nxt_cell: Vector2i = ch.path[0]
	# somebody in the way? wait (and give up after a moment)
	if _cell_of(ch.pos) != nxt_cell and _cell_blocked(ch, nxt_cell):
		ch.vel = ch.vel.move_toward(Vector2.ZERO, 4000.0 * delta)
		ch.blocked += delta
		ch.moving = false
		if ch.blocked > 0.7:
			ch.blocked = 0.0
			ch.bump = 1.0
			ch.sq_v += 3.0
			if ch.target != NO_CELL:
				_walk_to_station(ch, ch.target, _cell_of(ch.pos))
			else:
				ch.path = []
		return
	ch.blocked = 0.0
	var target := _cell_center(nxt_cell)
	var to := target - ch.pos
	var dist := to.length()
	var want := top
	if ch.path.size() == 1 and ch.in_dir == Vector2i.ZERO:
		want = top * clampf(dist / 48.0, 0.3, 1.0)   # ease into the final tile
	ch.vel = ch.vel.move_toward(to.normalized() * want, 2400.0 * delta)
	var move := ch.vel * delta
	if move.length() >= dist:
		ch.pos = target
		ch.path.remove_at(0)
		if ch.path.is_empty():
			if ch.in_dir == Vector2i.ZERO:
				ch.vel = Vector2.ZERO
			if ch.target != NO_CELL:
				var c := ch.target
				ch.target = NO_CELL
				_interact(ch, c)
	else:
		ch.pos += move
	ch.moving = ch.vel.length() > 20.0
	if absf(ch.vel.x) > 8.0:
		ch.face = lerpf(ch.face, signf(ch.vel.x), 1.0 - exp(-18.0 * delta))
	if absf(ch.vel.x) > absf(ch.vel.y):
		ch.dir = Vector2i(int(signf(ch.vel.x)), 0)
	elif ch.vel.length() > 8.0:
		ch.dir = Vector2i(0, int(signf(ch.vel.y)))
	ch.walk += ch.vel.length() * delta * 0.11


func _update_stations(delta: float) -> void:
	for key in stations:
		var c: Vector2i = key
		var s: Dictionary = stations[c]
		var kind: String = map[c.y][c.x]
		var rule: Dictionary = Data.RULES[kind]
		var st: String = s["st"]
		if st == "working":
			s["t"] = float(s["t"]) + delta
			if float(s["t"]) >= _station_time(kind):
				s["st"] = "done"
				_snd("ding", 1.0 if kind != "C" else 1.3)
				_fx_burst(_cell_center(c), Color("ffffff"), 6, 90.0)
		elif st == "done" and float(rule["burn"]) > 0.0:
			s["t"] = float(s["t"]) + delta
			if float(s["t"]) >= float(rule["burn"]):
				s["st"] = "burnt"
				s["out"] = "burnt"
				_snd("burn")
				_fx_shake(6.0)
				_fx_burst(_cell_center(c), Color("333333"), 14, 140.0)
				_fx_popup(_cell_center(c) + Vector2(0, -30), "BURNT!", C_BAD, 24)


# puffs of steam, runs on host and clients
func _station_fx(delta: float) -> void:
	for key in stations:
		var c: Vector2i = key
		var s: Dictionary = stations[c]
		var kind: String = map[c.y][c.x]
		var st: String = s["st"]
		if st == "idle" or (kind == "C" and st != "burnt"):
			continue
		s["puff"] = float(s["puff"]) - delta
		if float(s["puff"]) <= 0.0:
			s["puff"] = 0.25
			_puff(_cell_center(c) + Vector2(randf_range(-12, 12), -18), Color(0.2, 0.2, 0.2, 0.6) if st == "burnt" else Color(1, 1, 1, 0.5))


func _station_time(kind: String) -> float:
	var base: float = Data.RULES[kind]["time"]
	if kind == "C":
		return base * pow(0.85, _ulv("knife"))
	return base * pow(0.88, _ulv("pan"))


func _update_customers(delta: float) -> void:
	for i in range(customers.size() - 1, -1, -1):
		var c: Dictionary = customers[i]
		c["t"] = float(c["t"]) + delta
		var st: String = c["st"]
		if st == "wait":
			c["pat"] = float(c["pat"]) - delta
			if float(c["pat"]) <= 0.0:
				c["st"] = "angry"
				c["t"] = 0.0
				streak = 0
				lost += 1
				_snd("error")
				_fx_popup(_customer_pos(c["seat"]) + Vector2(0, 70), "Too slow!", C_BAD, 22)
				_fx_shake(5.0)
		elif st == "angry" or st == "happy":
			if float(c["t"]) > 1.2:
				customers.remove_at(i)
	spawn_timer -= delta
	if spawn_timer <= 0.0 and customers.size() < seats.size():
		_spawn_customer()
		var sp: Array = lv["spawn"]
		var lo: float = sp[0]
		var hi: float = sp[1]
		var f := 0.6 if time_left < 20.0 else 1.0
		f /= 1.0 + 0.35 * float(_nplayers() - 1)
		spawn_timer = randf_range(lo, hi) * f


func _spawn_customer() -> void:
	var free: Array = []
	for s in seats:
		var taken := false
		for c in customers:
			if Vector2i(c["seat"]) == Vector2i(s):
				taken = true
		if not taken:
			free.append(s)
	if free.is_empty():
		return
	var recipes: Array = lv["recipes"]
	var vip := randf() < float(lv["vip"])
	var pat: float = float(lv["patience"]) * (1.0 + 0.15 * _ulv("chairs")) * (0.75 if vip else 1.0)
	customers.append({
		"seat": free[randi() % free.size()],
		"order": recipes[randi() % recipes.size()],
		"pat": pat, "max": pat, "st": "wait", "t": 0.0,
		"look": randi() % 6, "vip": vip,
	})
	_snd("bell", 1.0 + randf_range(-0.1, 0.1))


func _customer_pos(seat: Vector2i) -> Vector2:
	return _cell_center(chair_of.get(seat, seat))


# ====================================================================
# Interactions
# ====================================================================

func _interact(ch: Chef, cell: Vector2i) -> void:
	var kind: String = map[cell.y][cell.x]
	pops[cell] = 0.3
	ch.sq_v += 4.0
	if Data.CRATES.has(kind):
		if ch.held == "":
			ch.held = Data.CRATES[kind]
			_snd("pop")
		else:
			_err(ch, "Hands full!")
	elif kind == "B":
		if ch.held != "":
			ch.held = ""
			_snd("pop", 0.7)
		else:
			_err(ch, "Nothing to throw away")
	elif Data.RULES.has(kind):
		_use_machine(ch, cell, kind)
	elif kind == "A":
		_use_plate(ch, cell)
	elif kind == "T":
		_serve(ch, cell)


func _use_machine(ch: Chef, cell: Vector2i, kind: String) -> void:
	var s: Dictionary = stations[cell]
	var rule: Dictionary = Data.RULES[kind]
	var map_in: Dictionary = rule["map"]
	var st: String = s["st"]
	if st == "idle":
		if ch.held == "":
			_err(ch, "Needs: %s" % rule["need"])
		elif map_in.has(ch.held):
			s["in"] = ch.held
			s["out"] = map_in[ch.held]
			s["t"] = 0.0
			s["st"] = "working"
			ch.held = ""
			_snd("chop" if kind == "C" else "pop")
			_fx_burst(_cell_center(cell), Color("ffe066"), 5, 70.0)
		else:
			_err(ch, "Can't use that here")
	elif st == "working":
		_err(ch, "Not ready yet")
	else:
		if ch.held != "":
			_err(ch, "Hands full!")
		else:
			ch.held = s["out"]
			var was_burnt: bool = st == "burnt"
			s["st"] = "idle"
			s["in"] = ""
			s["out"] = ""
			s["t"] = 0.0
			_snd("pop", 1.2)
			if was_burnt:
				_say(ch, "Yuck! Bin it!", C_BAD)


func _recipe_for(items: Array) -> String:
	var sorted_items := items.duplicate()
	sorted_items.sort()
	for id in Data.RECIPES:
		var r: Array = Data.RECIPES[id]["items"].duplicate()
		r.sort()
		if r == sorted_items:
			return id
	return ""


func _is_ingredient(item: String) -> bool:
	for id in Data.RECIPES:
		if item in Data.RECIPES[id]["items"]:
			return true
	return false


func _use_plate(ch: Chef, cell: Vector2i) -> void:
	var plate: Array = plates[cell]
	if ch.held != "":
		if ch.held.begins_with("dish:") or not _is_ingredient(ch.held):
			_err(ch, "Doesn't go on a plate")
		elif plate.size() >= 3:
			_err(ch, "Plate is full")
		else:
			plate.append(ch.held)
			ch.held = ""
			_snd("pop")
			var id := _recipe_for(plate)
			if id != "":
				_snd("ding", 1.4)
				_fx_burst(_cell_center(cell), C_GOLD, 8, 100.0)
				_say(ch, "%s ready!" % Data.RECIPES[id]["name"], C_GOLD)
		return
	if plate.is_empty():
		_err(ch, "Plate is empty")
		return
	var rid := _recipe_for(plate)
	if rid != "":
		ch.held = "dish:" + rid
		plates[cell] = []
		_snd("pop", 1.3)
	else:
		ch.held = plate.pop_back()
		_snd("pop", 0.8)


func _serve(ch: Chef, cell: Vector2i) -> void:
	var cust: Dictionary = {}
	for c in customers:
		if Vector2i(c["seat"]) == cell and c["st"] == "wait":
			cust = c
	if cust.is_empty():
		_err(ch, "Nobody there")
		return
	if not ch.held.begins_with("dish:"):
		_err(ch, "Bring a finished dish")
		return
	var want: String = cust["order"]
	var got := ch.held.substr(5)
	if got != want:
		streak = 0
		_err(ch, "They wanted %s!" % Data.RECIPES[want]["name"])
		return
	var price: int = Data.RECIPES[want]["price"]
	var frac: float = float(cust["pat"]) / float(cust["max"])
	var tip_mult := 2.0 if bool(cust["vip"]) else 1.0
	var tip := int(round(price * frac * 0.5 * tip_mult * (1.0 + 0.25 * _ulv("tips"))))
	streak += 1
	best_streak = maxi(best_streak, streak)
	var mult := 1.0 + 0.1 * minf(streak - 1, 5)
	var total := int(round((price + tip) * mult))
	if bool(cust["vip"]):
		total += 10
	earned += total
	served += 1
	ch.served += 1
	ch.coins_made += total
	ch.held = ""
	cust["st"] = "happy"
	cust["t"] = 0.0
	var pos := _customer_pos(cell)
	_snd("coin")
	_fx_burst(pos + Vector2(0, 20), C_GOLD, 12, 170.0)
	_fx_coinfly(pos + Vector2(0, 10), mini(8, 3 + total / 8))
	_fx_popup(pos + Vector2(0, -40), "+%d" % total, C_GOLD, 36)
	if tip > 0:
		_fx_popup(pos + Vector2(0, -4), "tip %d" % tip, C_GOOD, 20)
	if bool(cust["vip"]):
		_fx_popup(pos + Vector2(0, 28), "VIP +10", C_ACCENT, 20)
	if streak >= 2:
		_fx_popup(pos + Vector2(0, 56), "combo x%.1f" % mult, C_ACCENT, 22)


# ====================================================================
# fx wrappers: do it locally, and queue it for network clients when hosting
# ====================================================================

func _snd(sound: String, pitch: float = 1.0) -> void:
	sfx.play(sound, pitch)
	if net_mode == 1:
		ev_out.append(["snd", sound, pitch])


func _fx_burst(p: Vector2, col: Color, n: int, speed: float) -> void:
	_burst(p, col, n, speed)
	if net_mode == 1:
		ev_out.append(["burst", p, col, n, speed])


func _fx_popup(p: Vector2, text: String, col: Color, size: int) -> void:
	_popup(p, text, col, size)
	if net_mode == 1:
		ev_out.append(["pop", p, text, col, size])


func _fx_coinfly(from: Vector2, n: int) -> void:
	_coin_fly(from, Vector2(52, 38), n)
	if net_mode == 1:
		ev_out.append(["coins", from, n])


func _fx_shake(v: float) -> void:
	shake = maxf(shake, v)
	if net_mode == 1:
		ev_out.append(["shake", v])


func _banner(text: String) -> void:
	banner = text
	banner_t = 1.4
	if net_mode == 1:
		ev_out.append(["banner", text])


# a hint floating over a chef's head
func _say(ch: Chef, text: String, col: Color = C_GOLD) -> void:
	_fx_popup(ch.pos + Vector2(0, -78), text, col, 22)


func _err(ch: Chef, text: String) -> void:
	_say(ch, text, C_BAD)
	_snd("error")
