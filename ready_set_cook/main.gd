extends Node2D
# Ready, Set, Cook! v0.2
# Everything is drawn in code (no art files). Tap/click only, so it works on phones.

const W := 720.0
const H := 1280.0
const TILE := 64
const ORIGIN := Vector2(8, 96)
const NO_CELL := Vector2i(-1, -1)
const SAVE_PATH := "user://save_v2.json"
const SEAT_ROW := 9
const SEAT_ORDER := [4, 6, 2, 8]   # columns, filled in this order as levels add seats

# M meat crate, V veg crate, D dough crate, C chopping board, S stove, O oven
# A assembly plate, B bin, X counter, T customer seat, q dining floor, # wall
const MAP := [
	"###########",
	"#MVDXBXXOX#",
	"#.........#",
	"#.CC.A.SS.#",
	"#.........#",
	"#.........#",
	"#.........#",
	"#.........#",
	"#.........#",
	"#XTXTXTXTX#",
	"#qqqqqqqqq#",
	"#qqqqqqqqq#",
	"#qqqqqqqqq#",
	"#qqqqqqqqq#",
	"#qqqqqqqqq#",
	"###########",
]

enum S { MENU, LEVELS, SHOP, BRIEF, PLAY, PAUSE, RESULT }

const C_BG := Color("1b1b2f")
const C_PANEL := Color("2b2d4a")
const C_ACCENT := Color("ff7b54")
const C_GOLD := Color("ffd166")
const C_GOOD := Color("7bd389")
const C_BAD := Color("ef476f")

var font: Font = ThemeDB.fallback_font
var sfx: Sfx
var style_cache := {}

var state: S = S.MENU
var t_global := 0.0
var buttons: Array = []
var mouse_down := false

# ---- save data ----
var coins := 0
var stars: Array = []
var upg := {}
var sound_on := true

# ---- grid ----
var cols := 0
var rows := 0
var astar := AStarGrid2D.new()
var stations := {}               # Vector2i -> Dictionary
var seats: Array = []            # Vector2i of the seat cells for the current level

# ---- level state ----
var cur_level := 0
var lv: Dictionary = {}
var time_left := 0.0
var intro := 0.0
var earned := 0
var served := 0
var lost := 0
var streak := 0
var best_streak := 0
var customers: Array = []
var spawn_timer := 0.0
var rush_shown := false
var chef_pos := Vector2.ZERO
var chef_face := 1.0
var chef_moving := false
var path: Array[Vector2i] = []
var target_cell := NO_CELL
var held := ""
var plate: Array = []
var message := ""
var message_time := 0.0
var particles: Array = []
var popups: Array = []
var shake := 0.0
var result_t := 0.0
var result_stars := 0
var result_new_best := false
var banner := ""
var banner_t := 0.0
var level_unlocked_msg := false

# ---- animation state ----
var state_t := 0.0                 # seconds since the current screen appeared
var pending := -1                  # screen we are fading towards (-1 = none)
var fade := 0.0                    # 0 clear .. 1 black
var coins_shown := 0.0
var earned_shown := 0.0
var xf := Transform2D.IDENTITY     # current draw transform (so ellipses compose with it)
var chef_vel := Vector2.ZERO
var chef_sq := 0.0                 # squash spring (positive = tall)
var chef_sq_v := 0.0
var walk_phase := 0.0
var held_pos := Vector2.ZERO
var held_pop := 0.0
var last_held := ""
var pops := {}                     # Vector2i -> seconds left of a "bounce" on that tile
var float_icons: Array = []        # background food for menus
var hud_bump := 0.0


func _ready() -> void:
	_init_fonts()
	sfx = Sfx.new()
	add_child(sfx)
	rows = MAP.size()
	cols = MAP[0].length()
	astar.region = Rect2i(0, 0, cols, rows)
	astar.cell_size = Vector2(TILE, TILE)
	astar.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_NEVER
	astar.update()
	for y in rows:
		for x in cols:
			if MAP[y][x] != ".":
				astar.set_point_solid(Vector2i(x, y), true)
	_load_save()
	sfx.set_enabled(sound_on)
	for i in 14:
		float_icons.append({"p": Vector2(randf() * W, randf() * H), "v": randf_range(14, 36), "r": randf() * TAU, "w": randf_range(-0.8, 0.8),
			"id": ["dish:salad", "dish:burger", "dish:soup", "dish:steak", "veg", "meat", "bun", "patty"][i % 8], "s": randf_range(20, 34)})
	chef_pos = _cell_center(Vector2i(5, 5))
	held_pos = chef_pos


# ====================================================================
# Save / load
# ====================================================================

func _load_save() -> void:
	stars = []
	for i in Data.LEVELS.size():
		stars.append(0)
	upg = {}
	for u in Data.UPGRADES:
		upg[u["id"]] = 0
	if not FileAccess.file_exists(SAVE_PATH):
		return
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if f == null:
		return
	var data = JSON.parse_string(f.get_as_text())
	if not (data is Dictionary):
		return
	coins = int(data.get("coins", 0))
	sound_on = bool(data.get("sound", true))
	var s = data.get("stars", [])
	if s is Array:
		for i in mini(s.size(), stars.size()):
			stars[i] = int(s[i])
	var u = data.get("upg", {})
	if u is Dictionary:
		for k in upg:
			upg[k] = int(u.get(k, 0))


func _save() -> void:
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f == null:
		return
	f.store_string(JSON.stringify({"coins": coins, "stars": stars, "upg": upg, "sound": sound_on}))


func _unlocked(i: int) -> bool:
	return i == 0 or int(stars[i - 1]) >= 1


func _ulv(id: String) -> int:
	return int(upg.get(id, 0))


# ====================================================================
# Level control
# ====================================================================

func _start_level(i: int) -> void:
	cur_level = i
	lv = Data.LEVELS[i]
	time_left = float(lv["time"])
	earned = 0
	served = 0
	lost = 0
	streak = 0
	best_streak = 0
	customers = []
	particles = []
	popups = []
	held = ""
	plate = []
	path = []
	target_cell = NO_CELL
	spawn_timer = 1.5
	rush_shown = false
	banner_t = 0.0
	message_time = 0.0
	shake = 0.0
	chef_pos = _cell_center(Vector2i(5, 5))
	chef_vel = Vector2.ZERO
	held_pos = chef_pos
	last_held = ""
	pops = {}
	earned_shown = 0.0
	state_t = 0.0
	stations = {}
	for y in rows:
		for x in cols:
			var k: String = MAP[y][x]
			if Data.RULES.has(k):
				stations[Vector2i(x, y)] = {"in": "", "out": "", "t": 0.0, "st": "idle", "puff": 0.0}
	seats = []
	for n in int(lv["seats"]):
		seats.append(Vector2i(SEAT_ORDER[n], SEAT_ROW))
	intro = 3.0
	state = S.PLAY


func _end_level() -> void:
	var goals: Array = lv["goals"]
	result_stars = 0
	for g in goals:
		if earned >= int(g):
			result_stars += 1
	result_new_best = result_stars > int(stars[cur_level])
	level_unlocked_msg = false
	if result_new_best:
		if cur_level + 1 < stars.size() and int(stars[cur_level]) == 0:
			level_unlocked_msg = true
		stars[cur_level] = result_stars
	coins += earned
	_save()
	result_t = 0.0
	state_t = 0.0
	state = S.RESULT
	sfx.play("win" if result_stars > 0 else "lose")


# ====================================================================
# Input
# ====================================================================

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		mouse_down = event.pressed
		if event.pressed:
			_on_tap(get_local_mouse_position())
	elif event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		if state == S.PLAY:
			state = S.PAUSE
		elif state == S.PAUSE:
			state = S.PLAY


func _on_tap(p: Vector2) -> void:
	if pending >= 0:
		return
	for i in range(buttons.size() - 1, -1, -1):
		var b: Dictionary = buttons[i]
		var r: Rect2 = b["rect"]
		if r.has_point(p):
			sfx.play("click")
			_on_button(b["id"])
			return
	if state == S.PLAY and intro <= 0.0:
		_on_game_tap(p)


func _on_button(id: String) -> void:
	match id:
		"play":
			_goto(S.LEVELS)
		"shop":
			_goto(S.SHOP)
		"menu":
			_goto(S.MENU)
		"sound":
			sound_on = not sound_on
			sfx.set_enabled(sound_on)
			_save()
		"pause":
			state = S.PAUSE
		"resume":
			state = S.PLAY
		"restart":
			_start_level(cur_level)
		"retry":
			_goto(S.BRIEF)
		"next":
			cur_level = mini(cur_level + 1, Data.LEVELS.size() - 1)
			_goto(S.BRIEF)
		"start":
			_goto(S.PLAY)
		"levels":
			_goto(S.LEVELS)
		_:
			if id.begins_with("lvl_"):
				cur_level = int(id.substr(4))
				lv = Data.LEVELS[cur_level]
				_goto(S.BRIEF)
			elif id.begins_with("buy_"):
				_buy(id.substr(4))


func _goto(next: S) -> void:
	if pending < 0:
		pending = next


func _buy(id: String) -> void:
	var lvl := _ulv(id)
	var cost := Data.upgrade_cost(lvl)
	for u in Data.UPGRADES:
		if u["id"] == id and lvl < int(u["max"]) and coins >= cost:
			coins -= cost
			upg[id] = lvl + 1
			_save()
			sfx.play("coin")
			sfx.play("ding", 1.2)
			return
	sfx.play("error")


func _on_game_tap(p: Vector2) -> void:
	var cell := _pos_to_cell(p)
	if cell.x < 0 or cell.y < 0 or cell.x >= cols or cell.y >= rows:
		return
	var kind: String = MAP[cell.y][cell.x]
	var start := _pos_to_cell(chef_pos)
	if kind == ".":
		path = astar.get_id_path(start, cell)
		target_cell = NO_CELL
		return
	if kind == "q" or kind == "T":
		# tapping a customer or their table: pick the nearest seat column
		var best_seat := NO_CELL
		var best_d := 99
		for s in seats:
			var sc: Vector2i = s
			var d := absi(sc.x - cell.x)
			if d < best_d:
				best_d = d
				best_seat = sc
		if best_seat == NO_CELL or best_d > 1:
			return
		cell = best_seat
		kind = "T"
	if kind == "#" or kind == "X":
		return
	_walk_to_station(cell, start)


func _walk_to_station(cell: Vector2i, start: Vector2i) -> void:
	var best: Array[Vector2i] = []
	for d in [Vector2i(0, 1), Vector2i(0, -1), Vector2i(1, 0), Vector2i(-1, 0)]:
		var n: Vector2i = cell + d
		if n.x < 0 or n.y < 0 or n.x >= cols or n.y >= rows:
			continue
		if MAP[n.y][n.x] != ".":
			continue
		var candidate := astar.get_id_path(start, n)
		if candidate.is_empty():
			continue
		if best.is_empty() or candidate.size() < best.size():
			best = candidate
	if not best.is_empty():
		path = best
		target_cell = cell


# ====================================================================
# Simulation
# ====================================================================

func _process(delta: float) -> void:
	t_global += delta
	state_t += delta
	# screen transitions: fade out, swap, fade in
	if pending >= 0:
		fade = minf(1.0, fade + delta / 0.16)
		if fade >= 1.0:
			var target: int = pending
			pending = -1
			state_t = 0.0
			if target == S.PLAY:
				_start_level(cur_level)
			else:
				state = target as S
				if state == S.BRIEF:
					lv = Data.LEVELS[cur_level]
	elif fade > 0.0:
		fade = maxf(0.0, fade - delta / 0.22)
	coins_shown = lerpf(coins_shown, float(coins), 1.0 - exp(-8.0 * delta))
	if absf(coins_shown - coins) < 0.5:
		coins_shown = float(coins)
	earned_shown = lerpf(earned_shown, float(earned), 1.0 - exp(-7.0 * delta))
	if state == S.RESULT:
		result_t += delta
		var star_times := [0.8, 1.4, 2.0]
		for i in result_stars:
			var before: float = result_t - delta
			if before < star_times[i] and result_t >= star_times[i]:
				sfx.play("star", 1.0 + i * 0.25)
				var sx: float = W / 2 - 160 + i * 160
				var sy: float = 400.0 - (30.0 if i == 1 else 0.0)
				_burst(Vector2(sx, sy), C_GOLD, 26, 320.0)
				shake = 4.0
		if result_stars == 3 and result_t > 2.0 and randf() < 0.5:
			var cols := [C_GOLD, C_ACCENT, C_GOOD, Color("4cc9f0"), Color("ef476f")]
			particles.append({"p": Vector2(randf() * W, -10), "v": Vector2(randf_range(-40, 40), 120), "g": 60.0, "life": 4.0, "max": 4.0, "col": cols[randi() % 5], "r": randf_range(4, 7), "tex": ""})
	_update_fx(delta)
	if state == S.PLAY:
		_update_game(delta)
	for ic in float_icons:
		var p: Vector2 = ic["p"]
		p.y -= float(ic["v"]) * delta
		if p.y < -60.0:
			p = Vector2(randf() * W, H + 60.0)
		ic["p"] = p
		ic["r"] = float(ic["r"]) + float(ic["w"]) * delta
	queue_redraw()


func _update_fx(delta: float) -> void:
	for i in range(particles.size() - 1, -1, -1):
		var q: Dictionary = particles[i]
		q["life"] = float(q["life"]) - delta
		if float(q["life"]) <= 0.0:
			particles.remove_at(i)
			continue
		if q.has("tgt"):
			q["age"] = float(q["age"]) + delta
			if float(q["age"]) > 0.45:
				q["p"] = Vector2(q["p"]).lerp(Vector2(q["tgt"]), 1.0 - exp(-9.0 * delta))
				if Vector2(q["p"]).distance_to(Vector2(q["tgt"])) < 22.0:
					hud_bump = 1.0
					sfx.play("tick", 1.9 + randf() * 0.4)
					particles.remove_at(i)
					continue
			else:
				var v0: Vector2 = q["v"]
				v0.y += float(q["g"]) * delta
				q["v"] = v0
				q["p"] = Vector2(q["p"]) + v0 * delta
			continue
		var v: Vector2 = q["v"]
		v.y += float(q["g"]) * delta
		q["v"] = v
		q["p"] = Vector2(q["p"]) + v * delta
	for i in range(popups.size() - 1, -1, -1):
		var q: Dictionary = popups[i]
		q["life"] = float(q["life"]) - delta
		if float(q["life"]) <= 0.0:
			popups.remove_at(i)
			continue
		q["p"] = Vector2(q["p"]) + Vector2(0, -42) * delta
	shake = maxf(0.0, shake - delta * 30.0)
	hud_bump = maxf(0.0, hud_bump - delta * 5.0)
	# chef squash/stretch spring, held-item follow + pop
	chef_sq_v += (-chef_sq * 260.0 - chef_sq_v * 13.0) * delta
	chef_sq += chef_sq_v * delta
	var ht := chef_pos + Vector2(0, -62)
	held_pos = held_pos.lerp(ht, 1.0 - exp(-22.0 * delta))
	if held != last_held:
		last_held = held
		held_pop = 1.0
	held_pop = maxf(0.0, held_pop - delta * 4.0)
	for k in pops.keys():
		pops[k] = float(pops[k]) - delta
		if float(pops[k]) <= 0.0:
			pops.erase(k)
	position = Vector2(randf_range(-1, 1), randf_range(-1, 1)) * shake if shake > 0.0 else Vector2.ZERO
	if message_time > 0.0:
		message_time -= delta
	if banner_t > 0.0:
		banner_t -= delta


func _update_game(delta: float) -> void:
	if intro > 0.0:
		var prev := ceili(intro)
		intro -= delta
		if intro <= 0.0:
			sfx.play("go")
			_banner("GO!")
		elif ceili(intro) != prev:
			sfx.play("tick")
		return
	time_left -= delta
	if time_left <= 0.0:
		time_left = 0.0
		_end_level()
		return
	if time_left < 20.0 and not rush_shown:
		rush_shown = true
		_banner("RUSH HOUR!")
		sfx.play("bell")
	_update_chef(delta)
	_update_stations(delta)
	_update_customers(delta)


func _update_chef(delta: float) -> void:
	var top: float = 260.0 * (1.0 + 0.12 * _ulv("boots"))
	if path.is_empty():
		chef_vel = chef_vel.move_toward(Vector2.ZERO, 3000.0 * delta)
		chef_moving = false
		return
	var target := _cell_center(path[0])
	var to := target - chef_pos
	var dist := to.length()
	var want := top
	if path.size() == 1:
		want = top * clampf(dist / 48.0, 0.3, 1.0)   # ease into the final tile
	chef_vel = chef_vel.move_toward(to.normalized() * want, 2400.0 * delta)
	var move := chef_vel * delta
	if move.length() >= dist:
		chef_pos = target
		path.remove_at(0)
		if path.is_empty():
			chef_vel = Vector2.ZERO
			chef_moving = false
			if target_cell != NO_CELL:
				var c := target_cell
				target_cell = NO_CELL
				_interact(c)
	else:
		chef_pos += move
	chef_moving = chef_vel.length() > 20.0
	if absf(chef_vel.x) > 8.0:
		chef_face = lerpf(chef_face, signf(chef_vel.x), 1.0 - exp(-18.0 * delta))
	walk_phase += chef_vel.length() * delta * 0.11


func _update_stations(delta: float) -> void:
	for key in stations:
		var c: Vector2i = key
		var s: Dictionary = stations[c]
		var kind: String = MAP[c.y][c.x]
		var rule: Dictionary = Data.RULES[kind]
		var st: String = s["st"]
		if st == "working":
			s["t"] = float(s["t"]) + delta
			var need := _station_time(kind)
			if float(s["t"]) >= need:
				s["st"] = "done"
				sfx.play("ding", 1.0 if kind != "C" else 1.3)
				_burst(_cell_center(c), Color("ffffff"), 6, 90.0)
			elif kind != "C":
				_steam(s, c, delta, Color(1, 1, 1, 0.5))
		elif st == "done" and float(rule["burn"]) > 0.0:
			s["t"] = float(s["t"]) + delta
			_steam(s, c, delta, Color(1, 1, 1, 0.5))
			if float(s["t"]) >= float(rule["burn"]):
				s["st"] = "burnt"
				s["out"] = "burnt"
				sfx.play("burn")
				shake = 6.0
				_burst(_cell_center(c), Color("333333"), 14, 140.0)
				_popup(_cell_center(c) + Vector2(0, -30), "BURNT!", C_BAD, 24)
		elif st == "burnt":
			_steam(s, c, delta, Color(0.2, 0.2, 0.2, 0.6))


func _steam(s: Dictionary, c: Vector2i, delta: float, col: Color) -> void:
	s["puff"] = float(s["puff"]) - delta
	if float(s["puff"]) <= 0.0:
		s["puff"] = 0.25
		particles.append({"p": _cell_center(c) + Vector2(randf_range(-12, 12), -18), "v": Vector2(randf_range(-10, 10), -50), "g": -10.0, "life": 0.9, "max": 0.9, "col": col, "r": randf_range(10, 16), "tex": "puff"})


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
				sfx.play("error")
				var pos := _seat_pos(c["seat"])
				_popup(pos + Vector2(0, 60), "Too slow!", C_BAD, 22)
				shake = 5.0
		elif st == "angry" or st == "happy":
			if float(c["t"]) > 1.2:
				customers.remove_at(i)
	# spawn
	spawn_timer -= delta
	if spawn_timer <= 0.0 and customers.size() < seats.size():
		_spawn_customer()
		var sp: Array = lv["spawn"]
		var lo: float = sp[0]
		var hi: float = sp[1]
		var f := 0.6 if time_left < 20.0 else 1.0
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
	var pat: float = float(lv["patience"]) * (1.0 + 0.15 * _ulv("chairs"))
	customers.append({
		"seat": free[randi() % free.size()],
		"order": recipes[randi() % recipes.size()],
		"pat": pat, "max": pat, "st": "wait", "t": 0.0,
		"look": randi() % 6,
	})
	sfx.play("bell", 1.0 + randf_range(-0.1, 0.1))


# ====================================================================
# Interactions
# ====================================================================

func _interact(cell: Vector2i) -> void:
	var kind: String = MAP[cell.y][cell.x]
	pops[cell] = 0.3
	chef_sq_v += 4.0
	if Data.CRATES.has(kind):
		if held == "":
			held = Data.CRATES[kind]
			sfx.play("pop")
			_say("Got %s" % held)
		else:
			_err("Hands full!")
	elif kind == "B":
		if held != "":
			held = ""
			sfx.play("pop", 0.7)
			_say("Trashed it")
		else:
			_err("Nothing to throw away")
	elif Data.RULES.has(kind):
		_use_machine(cell, kind)
	elif kind == "A":
		_use_plate(cell)
	elif kind == "T":
		_serve(cell)


func _use_machine(cell: Vector2i, kind: String) -> void:
	var s: Dictionary = stations[cell]
	var rule: Dictionary = Data.RULES[kind]
	var map: Dictionary = rule["map"]
	var st: String = s["st"]
	if st == "idle":
		if held == "":
			_err("Needs: %s" % rule["need"])
		elif map.has(held):
			s["in"] = held
			s["out"] = map[held]
			s["t"] = 0.0
			s["st"] = "working"
			held = ""
			sfx.play("chop" if kind == "C" else "pop")
			_burst(_cell_center(cell), Color("ffe066"), 5, 70.0)
		else:
			_err("Can't use that here")
	elif st == "working":
		_err("Not ready yet")
	else:
		if held != "":
			_err("Hands full!")
		else:
			held = s["out"]
			var was_burnt: bool = st == "burnt"
			s["st"] = "idle"
			s["in"] = ""
			s["out"] = ""
			s["t"] = 0.0
			sfx.play("pop", 1.2)
			if was_burnt:
				_say("Yuck! Throw it in the bin")
			else:
				_say("Hot!")


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


func _use_plate(cell: Vector2i) -> void:
	if held != "":
		if held.begins_with("dish:") or not _is_ingredient(held):
			_err("That doesn't go on a plate")
		elif plate.size() >= 3:
			_err("Plate is full")
		else:
			plate.append(held)
			held = ""
			sfx.play("pop")
			if _recipe_for(plate) != "":
				sfx.play("ding", 1.4)
				_burst(_cell_center(cell), C_GOLD, 8, 100.0)
				_say("%s is ready! Pick it up" % Data.RECIPES[_recipe_for(plate)]["name"])
		return
	if plate.is_empty():
		_err("The plate is empty")
		return
	var id := _recipe_for(plate)
	if id != "":
		held = "dish:" + id
		plate = []
		sfx.play("pop", 1.3)
	else:
		held = plate.pop_back()
		_say("Took it back off")
		sfx.play("pop", 0.8)


func _serve(cell: Vector2i) -> void:
	var cust: Dictionary = {}
	for c in customers:
		if Vector2i(c["seat"]) == cell and c["st"] == "wait":
			cust = c
	if cust.is_empty():
		_err("Nobody sitting here")
		return
	if not held.begins_with("dish:"):
		_err("Bring a finished dish")
		return
	var want: String = cust["order"]
	var got := held.substr(5)
	if got != want:
		streak = 0
		_err("They ordered %s!" % Data.RECIPES[want]["name"])
		return
	var price: int = Data.RECIPES[want]["price"]
	var frac: float = float(cust["pat"]) / float(cust["max"])
	var tip := int(round(price * frac * 0.5 * (1.0 + 0.25 * _ulv("tips"))))
	streak += 1
	best_streak = maxi(best_streak, streak)
	var mult := 1.0 + 0.1 * minf(streak - 1, 5)
	var total := int(round((price + tip) * mult))
	earned += total
	served += 1
	held = ""
	cust["st"] = "happy"
	cust["t"] = 0.0
	var pos := _seat_pos(cell)
	sfx.play("coin")
	_burst(pos + Vector2(0, 60), C_GOLD, 12, 170.0)
	for i in mini(8, 3 + total / 8):
		var a := randf() * TAU
		particles.append({"p": pos + Vector2(0, 50), "v": Vector2(cos(a), sin(a) - 1.0) * randf_range(90, 220), "g": 500.0, "life": 1.4, "max": 1.4, "col": Color.WHITE, "r": 8.0, "tex": "coin", "tgt": Vector2(40, 37), "age": 0.0})
	_popup(pos + Vector2(0, 40), "+%d" % total, C_GOLD, 34)
	if tip > 0:
		_popup(pos + Vector2(0, 76), "tip %d" % tip, C_GOOD, 18)
	if streak >= 2:
		_popup(pos + Vector2(0, 100), "combo x%.1f" % mult, C_ACCENT, 20)


# ====================================================================
# Effects helpers
# ====================================================================

func _say(text: String) -> void:
	message = text
	message_time = 2.2


func _err(text: String) -> void:
	_say(text)
	sfx.play("error")


func _banner(text: String) -> void:
	banner = text
	banner_t = 1.4


func _burst(p: Vector2, col: Color, n: int, speed: float) -> void:
	for i in n:
		var a := randf() * TAU
		var v := Vector2(cos(a), sin(a)) * randf_range(0.3, 1.0) * speed
		particles.append({"p": p, "v": v, "g": 260.0, "life": 0.7, "max": 0.7, "col": col, "r": randf_range(4, 8), "tex": "spark"})


func _popup(p: Vector2, text: String, col: Color, size: int) -> void:
	popups.append({"p": p, "text": text, "life": 1.3, "col": col, "size": size})


func _cell_center(c: Vector2i) -> Vector2:
	return ORIGIN + (Vector2(c) + Vector2(0.5, 0.5)) * TILE


func _pos_to_cell(p: Vector2) -> Vector2i:
	return Vector2i(((p - ORIGIN) / TILE).floor())


func _seat_pos(seat: Vector2i) -> Vector2:
	return _cell_center(seat) + Vector2(0, TILE * 1.1)


# ====================================================================
# Drawing: helpers
# ====================================================================

const C_OUTLINE := Color("3b2618")

var tex_cache := {}
var f_reg: Font


func _init_fonts() -> void:
	f_reg = load("res://fonts/Fredoka.ttf")
	var fv := FontVariation.new()
	fv.base_font = f_reg
	var ts := TextServerManager.get_primary_interface()
	if ts != null:
		fv.variation_opentype = {ts.name_to_tag("weight"): 700}
	font = fv


func _tex(tex_name: String) -> Texture2D:
	if not tex_cache.has(tex_name):
		tex_cache[tex_name] = load("res://art/%s.svg" % tex_name)
	return tex_cache[tex_name]


# Draw a sprite centred on c. All art is authored at 2x, so sc = 1 is "native" size.
func _spr(tex_name: String, c: Vector2, sc: float = 1.0, rot: float = 0.0, mod: Color = Color.WHITE, sq: Vector2 = Vector2.ONE) -> void:
	var t := _tex(tex_name)
	var k := 0.5 * sc
	draw_set_transform_matrix(xf * Transform2D(rot, Vector2(k * sq.x, k * sq.y), 0.0, c))
	draw_texture(t, -t.get_size() / 2.0, mod)
	draw_set_transform_matrix(xf)


func _tile_spr(tex_name: String, rect: Rect2, mod: Color = Color.WHITE) -> void:
	draw_texture_rect(_tex(tex_name), rect, false, mod)


# 9-slice stretch of a 2x-authored texture. cx/ct/cb are the corner sizes in texture pixels.
func _nine(tex_name: String, r: Rect2, tint: Color, cx: float, ct: float, cb: float) -> void:
	var t := _tex(tex_name)
	var ts := t.get_size()
	var k := 0.5
	var xs := [0.0, cx, ts.x - cx, ts.x]
	var ys := [0.0, ct, ts.y - cb, ts.y]
	var dx := [r.position.x, r.position.x + cx * k, r.end.x - cx * k, r.end.x]
	var dy := [r.position.y, r.position.y + ct * k, r.end.y - cb * k, r.end.y]
	for j in 3:
		for i in 3:
			var dst := Rect2(float(dx[i]), float(dy[j]), float(dx[i + 1]) - float(dx[i]), float(dy[j + 1]) - float(dy[j]))
			var src := Rect2(float(xs[i]), float(ys[j]), float(xs[i + 1]) - float(xs[i]), float(ys[j + 1]) - float(ys[j]))
			draw_texture_rect_region(t, dst, src, tint)


func _panel(r: Rect2, tint: Color = Color.WHITE) -> void:
	_nine("panel", r, tint, 36.0, 36.0, 36.0)


func _rr(rect: Rect2, col: Color, radius: int = 12, border: Color = Color(0, 0, 0, 0), bw: int = 0) -> void:
	var key := "%s_%d_%s_%d" % [col.to_html(true), radius, border.to_html(true), bw]
	var sb: StyleBoxFlat
	if style_cache.has(key):
		sb = style_cache[key]
	else:
		sb = StyleBoxFlat.new()
		sb.bg_color = col
		sb.set_corner_radius_all(radius)
		sb.anti_aliasing = true
		if bw > 0:
			sb.border_color = border
			sb.set_border_width_all(bw)
		style_cache[key] = sb
	draw_style_box(sb, rect)


func _txt(s: String, pos: Vector2, size: int, col: Color = Color.WHITE, align: int = HORIZONTAL_ALIGNMENT_LEFT, w: float = -1.0) -> void:
	var ol := maxi(3, size / 5)
	draw_string(font, pos + Vector2(0, maxf(2.0, size / 14.0)), s, align, w, size, Color(0, 0, 0, 0.3))
	draw_string_outline(font, pos, s, align, w, size, ol, C_OUTLINE)
	draw_string(font, pos, s, align, w, size, col)


func _ctext(s: String, center: Vector2, size: int, col: Color = Color.WHITE) -> void:
	_txt(s, Vector2(center.x - 500.0, center.y), size, col, HORIZONTAL_ALIGNMENT_CENTER, 1000.0)


func _xf_set(t: Transform2D) -> void:
	xf = t
	draw_set_transform_matrix(t)


func _xf_reset() -> void:
	xf = Transform2D.IDENTITY
	draw_set_transform_matrix(Transform2D.IDENTITY)


# scale/rotate everything drawn next around the point c
func _xf_about(c: Vector2, sx: float, sy: float, rot: float = 0.0) -> void:
	var t := Transform2D(rot, Vector2(sx, sy), 0.0, Vector2.ZERO)
	t.origin = c - t.basis_xform(c)
	_xf_set(t)


func _ease_back(x: float) -> float:
	var t := clampf(x, 0.0, 1.0)
	var c1 := 1.70158
	var c3 := c1 + 1.0
	return 1.0 + c3 * pow(t - 1.0, 3.0) + c1 * pow(t - 1.0, 2.0)


func _ease_out(x: float) -> float:
	return 1.0 - pow(1.0 - clampf(x, 0.0, 1.0), 3.0)


func _pop_in(delay: float, dur: float = 0.45) -> float:
	return _ease_back((state_t - delay) / dur)


func _ell(c: Vector2, rx: float, ry: float, col: Color) -> void:
	draw_set_transform_matrix(xf * Transform2D(Vector2(1.0, 0.0), Vector2(0.0, ry / rx), c))
	draw_circle(Vector2.ZERO, rx, col)
	draw_set_transform_matrix(xf)


func _star_shape(c: Vector2, r: float, col: Color) -> void:
	var pts := PackedVector2Array()
	for i in 10:
		var rad := r if i % 2 == 0 else r * 0.45
		var a := -PI / 2.0 + i * PI / 5.0
		pts.append(c + Vector2(cos(a), sin(a)) * rad)
	draw_colored_polygon(pts, col)


func _star(c: Vector2, r: float, on: bool) -> void:
	_spr("star_on" if on else "star_off", c, r / 22.0)


func _coin(c: Vector2, r: float) -> void:
	_spr("coin", c, r / 18.0)


func _bar(r: Rect2, frac: float, col: Color) -> void:
	_rr(r.grow(2), C_OUTLINE, int(r.size.y / 2) + 2)
	_rr(r, Color("5a4a6a"), int(r.size.y / 2))
	if frac > 0.01:
		var w := maxf(r.size.y, r.size.x * clampf(frac, 0.0, 1.0))
		_rr(Rect2(r.position, Vector2(w, r.size.y)), col, int(r.size.y / 2))
		_rr(Rect2(r.position + Vector2(4, 2), Vector2(maxf(0.0, w - 8), r.size.y * 0.3)), Color(1, 1, 1, 0.35), int(r.size.y / 4))


func _button(rect: Rect2, label: String, id: String, col: Color = C_ACCENT, fsize: int = 32, enabled: bool = true) -> void:
	buttons.append({"rect": rect, "id": id})
	var hover := rect.has_point(get_local_mouse_position()) and enabled
	var down := hover and mouse_down
	var c := col if enabled else Color("8a8da6")
	if hover:
		c = c.lightened(0.1)
	var r := rect
	var lip := 11.0
	if down:
		r.position.y += 5.0
	_nine("btn_down" if down else "btn", Rect2(r.position, Vector2(r.size.x, r.size.y + lip)), c, 40.0, 34.0, 44.0)
	_ctext(label, Vector2(r.position.x + r.size.x / 2.0, r.position.y + r.size.y / 2.0 + fsize * 0.36), fsize)


# ----- items & dishes (sprites) -----

func _draw_item(id: String, c: Vector2, s: float) -> void:
	if id.begins_with("dish:"):
		_draw_dish(id.substr(5), c, s)
		return
	_spr("item_" + id, c, s / 22.0)


func _draw_dish(id: String, c: Vector2, s: float) -> void:
	_spr("dish_" + id, c, s / 22.0)


# ----- faces (drawn in code so they can blink / emote) -----

func _draw_face(c: Vector2, look: float, mood: float, blink: float, spacing: float = 9.0, size: float = 1.0) -> void:
	# c = centre of the head; mood -1 angry .. 0 flat .. 1 happy
	var ink := Color("2a1a12")
	for sx in [-1.0, 1.0]:
		var e: Vector2 = c + Vector2(sx * spacing * size + look * 2.0, -1.0 * size)
		if mood > 0.85:
			# happy closed eyes ^ ^
			draw_arc(e + Vector2(0, 1.5 * size), 4.0 * size, PI + 0.3, TAU - 0.3, 8, ink, 2.4 * size)
		else:
			_ell(e, 4.4 * size, 5.2 * size * blink, Color.WHITE)
			_ell(e + Vector2(look * 1.2, 0.5), 2.7 * size, 3.4 * size * blink, ink)
			if blink > 0.5:
				draw_circle(e + Vector2(-0.8 + look * 1.2, -1.2) * size, 0.9 * size, Color.WHITE)
		if mood < -0.3:
			draw_line(e + Vector2(sx * 5.0 * size, -9.0 * size), e + Vector2(-sx * 5.0 * size, -5.0 * size), ink, 2.4 * size)
	var m := c + Vector2(look * 2.0, 11.0 * size)
	if mood > 0.15:
		draw_arc(m + Vector2(0, -2 * size), 6.0 * size, 0.25, PI - 0.25, 10, ink, 2.4 * size)
		if mood > 0.85:
			draw_circle(m + Vector2(0, 2 * size), 3.0 * size, Color("e63946"))
	elif mood < -0.15:
		draw_arc(m + Vector2(0, 4 * size), 5.0 * size, PI + 0.4, TAU - 0.4, 10, ink, 2.4 * size)
	else:
		draw_line(m + Vector2(-4, 0) * size, m + Vector2(4, 0) * size, ink, 2.4 * size)


func _draw_chef(c: Vector2, face: float, bob: float, scale_f: float = 1.0, lean: float = 0.0, sq: float = 0.0, phase: float = 0.0, mood: float = 0.6) -> void:
	# c = tile centre; feet sit about 24px below it
	var feet := c + Vector2(0, 24)
	var cs := 0.7 * scale_f
	_xf_set(Transform2D(Vector2(1, 0), Vector2(0, 0.32), feet + Vector2(0, 1)))
	draw_circle(Vector2.ZERO, 24 * scale_f, Color(0, 0, 0, 0.3))
	var t := Transform2D(lean, Vector2(cs * (1.0 - sq * 0.5), cs * (1.0 + sq)), 0.0, feet)
	_xf_set(t)
	var step := sin(phase)
	var up := -absf(step) * 3.0 if absf(chef_vel.x) + absf(chef_vel.y) > 20.0 or scale_f > 1.2 else 0.0
	up += bob
	# feet
	_spr("shoe", Vector2(-14, -8 - maxf(0.0, step) * 8.0), 1.4)
	_spr("shoe", Vector2(14, -8 - maxf(0.0, -step) * 8.0), 1.4)
	# body + arms
	var body_c := Vector2(0, -34 + up * 0.6)
	_spr("chef_body", body_c, 1.5)
	_spr("hand", Vector2(-40, -26 + step * 7.0 + up * 0.6), 1.4)
	_spr("hand", Vector2(40, -26 - step * 7.0 + up * 0.6), 1.4)
	# head (lags a little behind the body for a bouncy feel)
	var head_tilt := clampf(chef_vel.x / 260.0, -1.0, 1.0) * 0.1 + sin(t_global * 2.0) * 0.015
	var hc := Vector2(0, -92 + up)
	_xf_set(t * Transform2D(head_tilt, Vector2.ONE, 0.0, Vector2.ZERO))
	_spr("chef_head", hc + Vector2(0, -19), 1.5)
	var blink := 0.15 if fmod(t_global, 3.6) > 3.45 else 1.0
	_draw_face(hc + Vector2(0, 8), face, mood, blink, 12.0, 1.5)
	_xf_reset()


# ====================================================================
# Drawing: screens
# ====================================================================

func _draw() -> void:
	buttons = []
	_draw_background()
	match state:
		S.MENU:
			_draw_menu()
		S.LEVELS:
			_draw_levels()
		S.SHOP:
			_draw_shop()
		S.BRIEF:
			_draw_brief()
		S.PLAY, S.PAUSE:
			_draw_game()
			if state == S.PAUSE:
				_draw_pause()
		S.RESULT:
			_draw_result()
	_draw_particles()
	_draw_vignette()
	if fade > 0.0:
		draw_rect(Rect2(-20, -20, W + 40, H + 40), Color(0.12, 0.07, 0.1, fade))


func _draw_vignette() -> void:
	var c0 := Color(0, 0, 0, 0.3)
	var c1 := Color(0, 0, 0, 0)
	draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(W, 0), Vector2(W, 120), Vector2(0, 120)]), PackedColorArray([c0, c0, c1, c1]))
	draw_polygon(PackedVector2Array([Vector2(0, H - 140), Vector2(W, H - 140), Vector2(W, H), Vector2(0, H)]), PackedColorArray([c1, c1, c0, c0]))
	draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(70, 0), Vector2(70, H), Vector2(0, H)]), PackedColorArray([c0, c1, c1, c0]))
	draw_polygon(PackedVector2Array([Vector2(W - 70, 0), Vector2(W, 0), Vector2(W, H), Vector2(W - 70, H)]), PackedColorArray([c1, c0, c0, c1]))


func _draw_background() -> void:
	draw_rect(Rect2(-20, -20, W + 40, H + 40), C_BG)
	if state == S.PLAY or state == S.PAUSE:
		return
	var warm := state == S.MENU or state == S.RESULT or state == S.BRIEF
	var top := Color("ffbe6b") if warm else Color("7a5cb0")
	var bot := Color("f0506e") if warm else Color("3a2a66")
	draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(W, 0), Vector2(W, H), Vector2(0, H)]), PackedColorArray([top, top, bot, bot]))
	# slowly rotating sunburst
	var cc := Vector2(W / 2, 560)
	for i in 14:
		var a0 := t_global * 0.12 + i * TAU / 14.0
		var a1 := a0 + TAU / 28.0
		draw_colored_polygon(PackedVector2Array([cc, cc + Vector2(cos(a0), sin(a0)) * 1500.0, cc + Vector2(cos(a1), sin(a1)) * 1500.0]), Color(1, 1, 1, 0.09))
	for ic in float_icons:
		var q: Vector2 = ic["p"]
		_spr("item_" + str(ic["id"]) if not str(ic["id"]).begins_with("dish:") else "dish_" + str(ic["id"]).substr(5), q, float(ic["s"]) / 20.0, float(ic["r"]), Color(1, 1, 1, 0.55))


func _draw_particles() -> void:
	for q in particles:
		var a: float = float(q["life"]) / float(q["max"])
		var col: Color = q["col"]
		var kind: String = q["tex"]
		var r: float = float(q["r"])
		if kind == "puff":
			col.a *= a * 0.9
			_spr("puff", q["p"], r * (2.2 - a) / 18.0, 0.0, col)
		elif kind == "spark":
			col.a = minf(1.0, a * 2.0)
			_spr("spark", q["p"], r * (0.5 + a) / 9.0, float(q["life"]) * 6.0, col)
		elif kind == "coin":
			_spr("coin", q["p"], 0.5 * (0.8 + 0.2 * sin(float(q["life"]) * 20.0)), 0.0, Color.WHITE)
		else:
			col.a *= a
			draw_circle(q["p"], r * (0.5 + a * 0.5), col)
	for q in popups:
		var a: float = clampf(float(q["life"]) * 2.0, 0.0, 1.0)
		var col: Color = q["col"]
		col.a = a
		var age: float = 1.3 - float(q["life"])
		var sc := 1.0 + 0.6 * maxf(0.0, 1.0 - age * 5.0)
		_ctext(q["text"], q["p"], int(float(q["size"]) * sc), col)


func _coin_bar() -> void:
	var bump := 1.0 + hud_bump * 0.25
	_nine("panel", Rect2(W - 214, 14, 196, 54), Color("3a2a4e"), 36.0, 36.0, 36.0)
	_spr("coin", Vector2(W - 184, 41), 0.9 * bump)
	_txt(str(int(round(coins_shown))), Vector2(W - 156, 53), 30, C_GOLD)


func _menu_title(text: String, y: float, size: int, col: Color, delay: float, tilt: float = 0.0) -> void:
	var k := _pop_in(delay, 0.5)
	if k <= 0.0:
		return
	var bobv := sin(t_global * 2.6 + delay * 4.0) * 5.0
	_xf_about(Vector2(W / 2, y), k, k, tilt + sin(t_global * 1.7 + delay) * 0.02)
	_ctext(text, Vector2(W / 2, y + bobv), size, col)
	_xf_reset()


func _draw_menu() -> void:
	_coin_bar()
	_menu_title("READY", 215, 110, Color("ffffff"), 0.05, -0.06)
	_menu_title("SET", 315, 110, C_GOLD, 0.15, 0.04)
	_menu_title("COOK!", 430, 140, Color("ff5a36"), 0.25, -0.04)
	# hero chef
	var hk := _pop_in(0.35, 0.6)
	var hb := sin(t_global * 3.4) * 6.0
	_draw_item("dish:burger", Vector2(W / 2 - 215, 735 + sin(t_global * 2.0) * 9.0), 40 * hk)
	_draw_item("dish:salad", Vector2(W / 2 + 215, 745 + cos(t_global * 2.2) * 9.0), 40 * hk)
	_xf_about(Vector2(W / 2, 760), hk, hk)
	_draw_chef(Vector2(W / 2, 640 + hb), 1.0, 0.0, 2.2, sin(t_global * 1.5) * 0.04, absf(sin(t_global * 3.4)) * 0.03, t_global * 1.2, 1.0)
	_xf_reset()
	# buttons
	var pk := _pop_in(0.5, 0.5)
	var pulse := 1.0 + sin(t_global * 5.0) * 0.025
	if pk > 0.0:
		var br := Rect2(W / 2 - 190 * pk * pulse, 850, 380 * pk * pulse, 100)
		_button(br, "PLAY", "play", Color("ff6b3d"), 54)
	var sk := _pop_in(0.62, 0.5)
	if sk > 0.0:
		_button(Rect2(W / 2 - 190 * sk, 985, 380 * sk, 84), "UPGRADES", "shop", Color("4c8bf5"), 34)
	var ok := _pop_in(0.72, 0.5)
	if ok > 0.0:
		_button(Rect2(W / 2 - 150 * ok, 1100, 300 * ok, 70), "SOUND: ON" if sound_on else "SOUND: OFF", "sound", Color("8d99ae"), 26)
	var total := 0
	for s in stars:
		total += int(s)
	_spr("star_on", Vector2(W / 2 - 62, 1215), 0.55)
	_txt("%d / %d" % [total, Data.LEVELS.size() * 3], Vector2(W / 2 - 40, 1226), 28, C_GOLD)


func _draw_levels() -> void:
	_coin_bar()
	_button(Rect2(20, 18, 130, 52), "BACK", "menu", Color("8d99ae"), 24)
	_ctext("Choose a level", Vector2(W / 2, 150), 56)
	for i in Data.LEVELS.size():
		var col := i % 2
		var row := i / 2
		var k := _pop_in(0.04 * i, 0.4)
		if k <= 0.0:
			continue
		var r := Rect2(30 + col * 340, 190 + row * 215, 320, 195)
		_xf_about(r.get_center(), k, k)
		var d: Dictionary = Data.LEVELS[i]
		var open := _unlocked(i)
		var tint := Color("ffb457") if open else Color("8a8da6")
		if open and int(stars[i]) >= 1:
			tint = Color("7fd98f")
		if open and int(stars[i]) >= 3:
			tint = Color("ffd84a")
		_panel(r, tint)
		if open:
			buttons.append({"rect": r, "id": "lvl_%d" % i})
			_txt(str(i + 1), r.position + Vector2(22, 78), 66, Color("ff6b3d"))
			_txt(d["name"], r.position + Vector2(18, 118), 25, Color.WHITE, HORIZONTAL_ALIGNMENT_LEFT, 290)
			var recs: Array = d["recipes"]
			for n in recs.size():
				_draw_dish(recs[n], r.position + Vector2(40 + n * 62, 156), 14)
			for n in 3:
				_star(r.position + Vector2(212 + n * 34, 42), 15, n < int(stars[i]))
			_txt("%ds" % int(d["time"]), r.position + Vector2(232, 90), 24, Color.WHITE)
		else:
			_draw_lock(r.get_center() + Vector2(0, -22))
			_ctext("get a star on level %d" % i, r.get_center() + Vector2(0, 62), 18, Color(1, 1, 1, 0.85))
		_xf_reset()


func _draw_lock(c: Vector2) -> void:
	draw_arc(c + Vector2(0, -12), 17, PI, TAU, 14, C_OUTLINE, 11.0)
	draw_arc(c + Vector2(0, -12), 17, PI, TAU, 14, Color("d7dae8"), 6.0)
	_rr(Rect2(c + Vector2(-26, -12), Vector2(52, 42)), Color("ffd166"), 10, C_OUTLINE, 4)
	draw_circle(c + Vector2(0, 7), 6, C_OUTLINE)


func _upgrade_icon(id: String, c: Vector2) -> void:
	match id:
		"boots":
			_spr("shoe", c, 2.6)
		"knife":
			_spr("chop_board", c, 1.1)
		"pan":
			_spr("pot", c, 1.1)
		"chairs":
			_spr("seat", c, 1.1)
		"tips":
			_spr("coin", c, 1.7)


func _draw_shop() -> void:
	_coin_bar()
	_button(Rect2(20, 18, 130, 52), "BACK", "menu", Color("8d99ae"), 24)
	_ctext("Upgrades", Vector2(W / 2, 150), 58)
	var y := 195.0
	var n := 0
	for u in Data.UPGRADES:
		var k := _pop_in(0.06 * n, 0.4)
		n += 1
		var id: String = u["id"]
		var lvl := _ulv(id)
		var mx: int = u["max"]
		var r := Rect2(24, y, 672, 175)
		y += 190.0
		if k <= 0.0:
			continue
		_xf_about(r.get_center(), k, k)
		_panel(r, Color("c99a6b"))
		_spr("puff", r.position + Vector2(80, 88), 1.8, 0.0, Color(1, 1, 1, 0.9))
		_upgrade_icon(id, r.position + Vector2(80, 88))
		_txt(u["name"], r.position + Vector2(150, 56), 34, Color.WHITE)
		_txt(u["desc"], r.position + Vector2(150, 92), 18, Color(1, 1, 1, 0.95), HORIZONTAL_ALIGNMENT_LEFT, 300)
		for p in mx:
			_rr(Rect2(r.position + Vector2(150 + p * 40, 114), Vector2(32, 26)), C_GOOD if p < lvl else Color(0, 0, 0, 0.25), 8, C_OUTLINE, 3)
		if lvl >= mx:
			_ctext("MAX", r.position + Vector2(570, 104), 38, C_GOLD)
		else:
			var cost := Data.upgrade_cost(lvl)
			_button(Rect2(r.position + Vector2(462, 40), Vector2(190, 84)), "     %d" % cost, "buy_" + id, Color("39b36b"), 34, coins >= cost)
			_coin(r.position + Vector2(500, 84), 16)
		_xf_reset()
	_ctext("Coins come from serving customers.", Vector2(W / 2, 1180), 24, Color(1, 1, 1, 0.9))


func _draw_brief() -> void:
	var d: Dictionary = Data.LEVELS[cur_level]
	_button(Rect2(20, 18, 130, 52), "BACK", "levels", Color("8d99ae"), 24)
	_ctext("Level %d" % (cur_level + 1), Vector2(W / 2, 150), 40, Color(1, 1, 1, 0.9))
	_menu_title(d["name"], 230, 68, C_GOLD, 0.0)
	_ctext("%d seconds  -  %d tables" % [int(d["time"]), int(d["seats"])], Vector2(W / 2, 292), 26)
	var recs: Array = d["recipes"]
	var y := 340.0
	var n := 0
	for id in recs:
		var k := _pop_in(0.1 + 0.08 * n, 0.4)
		n += 1
		var r := Rect2(40, y, 640, 120)
		y += 132.0
		if k <= 0.0:
			continue
		_xf_about(r.get_center(), k, k)
		_panel(r, Color("c99a6b"))
		_draw_dish(id, r.position + Vector2(66, 62), 26)
		_txt("%s  (%d coins)" % [Data.RECIPES[id]["name"], int(Data.RECIPES[id]["price"])], r.position + Vector2(130, 52), 30, Color.WHITE)
		_txt(Data.RECIPES[id]["steps"], r.position + Vector2(130, 92), 20, Color(1, 1, 1, 0.95), HORIZONTAL_ALIGNMENT_LEFT, 500)
		_xf_reset()
	var goals: Array = d["goals"]
	_ctext("Earn coins for stars", Vector2(W / 2, 1000), 30)
	for k in 3:
		var cx := W / 2 - 200 + k * 200
		_star(Vector2(cx, 1055), 28, k < int(stars[cur_level]))
		_ctext(str(int(goals[k])), Vector2(cx, 1115), 30, C_GOLD)
	_button(Rect2(W / 2 - 170, 1145, 340, 100), "START!", "start", Color("ff6b3d"), 50)


func _draw_pause() -> void:
	draw_rect(Rect2(0, 0, W, H), Color(0.1, 0.05, 0.12, 0.72))
	buttons = []
	_ctext("PAUSED", Vector2(W / 2, 400), 96)
	_button(Rect2(W / 2 - 190, 500, 380, 100), "RESUME", "resume", Color("ff6b3d"), 44)
	_button(Rect2(W / 2 - 190, 640, 380, 84), "RESTART", "restart", Color("4c8bf5"), 32)
	_button(Rect2(W / 2 - 190, 755, 380, 84), "QUIT", "levels", Color("8d99ae"), 32)


func _draw_result() -> void:
	var t := result_t
	var win := result_stars > 0
	var bk := _ease_back(t / 0.5)
	_xf_about(Vector2(W / 2, 190), bk, bk)
	_spr("ribbon", Vector2(W / 2, 190), 1.35, 0.0, Color.WHITE if win else Color("8d99ae"))
	_ctext("TIME'S UP!" if win else "TRY AGAIN", Vector2(W / 2, 205), 56, Color.WHITE)
	_xf_reset()
	_ctext(lv["name"], Vector2(W / 2, 300), 30, Color(1, 1, 1, 0.95))
	var goals: Array = lv["goals"]
	for k in 3:
		var cx := W / 2 - 160 + k * 160
		var cy := 450.0 - (30.0 if k == 1 else 0.0)
		_star(Vector2(cx, cy), 70, false)
		var show_t: float = [0.8, 1.4, 2.0][k]
		if k < result_stars and t >= show_t:
			var sc := 1.0 + maxf(0.0, 0.7 - (t - show_t) * 2.4)
			var rot := sin((t - show_t) * 9.0) * 0.12 * maxf(0.0, 1.0 - (t - show_t))
			_spr("glow", Vector2(cx, cy), 2.2 * minf(1.0, (t - show_t) * 3.0), 0.0, Color(1, 1, 1, 0.55))
			_spr("star_on", Vector2(cx, cy), 70.0 / 22.0 * sc, rot)
		_ctext(str(int(goals[k])), Vector2(cx, cy + 105), 26, Color(1, 1, 1, 0.9))
	var shown := int(minf(1.0, t / 0.8) * earned)
	_coin(Vector2(W / 2 - 120, 650), 30)
	_txt("+%d" % shown, Vector2(W / 2 - 78, 672), 70, C_GOLD)
	_ctext("Served: %d     Lost: %d     Best combo: x%d" % [served, lost, best_streak], Vector2(W / 2, 740), 26)
	if result_new_best and result_stars > 0:
		_ctext("NEW BEST!", Vector2(W / 2, 800 + sin(t * 8.0) * 4.0), 44, Color("ff5a36"))
	if level_unlocked_msg:
		_ctext("Next level unlocked!", Vector2(W / 2, 850), 32, C_GOOD)
	if t > 1.0:
		var bkk := _ease_back((t - 1.0) / 0.4)
		var can_next := result_stars > 0 and cur_level + 1 < Data.LEVELS.size()
		if can_next:
			_button(Rect2(W / 2 - 190 * bkk, 920, 380 * bkk, 100), "NEXT LEVEL", "next", Color("ff6b3d"), 40)
		_button(Rect2(W / 2 - 190 * bkk, 1045, 380 * bkk, 80), "RETRY", "retry", Color("4c8bf5"), 32)
		_button(Rect2(W / 2 - 190 * bkk, 1145, 180 * bkk, 70), "LEVELS", "levels", Color("8d99ae"), 24)
		_button(Rect2(W / 2 + 10 * bkk, 1145, 180 * bkk, 70), "UPGRADES", "shop", Color("39b36b"), 22)


# ----- gameplay -----

func _tutorial_text() -> String:
	if cur_level != 0:
		return ""
	if held.begins_with("dish:"):
		return "Tap the customer to serve!"
	if held == "veg":
		return "Tap a CHOP board"
	if held == "veg_chop":
		return "Tap the PLATE in the middle"
	if held == "":
		if _recipe_for(plate) != "":
			return "Tap the PLATE to pick up the salad"
		for k in stations:
			var s: Dictionary = stations[k]
			if MAP[Vector2i(k).y][Vector2i(k).x] == "C" and s["st"] == "done":
				return "Tap the chop board to grab the veg"
		return "Tap the VEG crate. Salad = 2 chopped veg"
	return ""


func _draw_game() -> void:
	_draw_kitchen()
	_draw_customers_and_chef()
	_draw_hud()
	if intro > 0.0:
		_draw_intro()
	elif banner_t > 0.0:
		var k := _ease_back((1.4 - banner_t) / 0.35)
		var a := clampf(banner_t * 2.0, 0.0, 1.0)
		_xf_about(Vector2(W / 2, 560), k, k)
		_ctext(banner, Vector2(W / 2, 560), 100, Color(C_GOLD.r, C_GOLD.g, C_GOLD.b, a))
		_xf_reset()


func _draw_intro() -> void:
	draw_rect(Rect2(0, 0, W, H), Color(0.1, 0.05, 0.12, 0.5))
	var elapsed := 3.0 - intro
	var idx := clampi(int(elapsed), 0, 2)
	var texts := ["READY?", "SET...", "COOK!"]
	var cols := [Color("ffffff"), C_GOLD, Color("ff5a36")]
	var local := elapsed - float(idx)
	var k := _ease_back(local / 0.4)
	var out_a := clampf((1.0 - local) * 5.0, 0.0, 1.0)
	var col: Color = cols[idx]
	col.a = out_a
	_xf_about(Vector2(W / 2, 620), k, k, sin(local * 6.0) * 0.05)
	_ctext(texts[idx], Vector2(W / 2, 640), 150, col)
	_xf_reset()
	_ctext("Level %d: %s" % [cur_level + 1, lv["name"]], Vector2(W / 2, 470), 36, Color(1, 1, 1, 0.95))


func _draw_kitchen() -> void:
	for y in rows:
		for x in cols:
			var kind: String = MAP[y][x]
			var rect := Rect2(ORIGIN + Vector2(x, y) * TILE, Vector2(TILE, TILE))
			_draw_tile(kind, rect, x, y)
	# wall decorations (row 0)
	var wy := ORIGIN.y
	for lx in [2.7, 8.3]:
		var sway := sin(t_global * 1.3 + lx) * 0.05
		_xf_about(Vector2(ORIGIN.x + lx * TILE, wy), 1.0, 1.0, sway)
		_spr("lamp", Vector2(ORIGIN.x + lx * TILE, wy + 36), 0.95)
		_xf_reset()
	_spr("wall_pan", Vector2(ORIGIN.x + 1.1 * TILE, wy + 34), 0.62)
	_spr("wall_shelf", Vector2(ORIGIN.x + 4.9 * TILE, wy + 30), 0.5)
	_spr("wall_clock", Vector2(ORIGIN.x + 6.9 * TILE, wy + 32), 0.5)
	_spr("wall_pan", Vector2(ORIGIN.x + 9.6 * TILE, wy + 34), 0.62)
	# station overlays
	for key in stations:
		var c: Vector2i = key
		_draw_station_state(c, stations[c])
	# plate contents
	var pc := _cell_center(Vector2i(5, 3)) + Vector2(0, -6)
	if not plate.is_empty():
		var id := _recipe_for(plate)
		if id != "":
			var bounce := 1.0 + sin(t_global * 6.0) * 0.04
			_draw_dish(id, pc, 17 * bounce)
			_spr("spark", pc + Vector2(18, -18), 0.45, t_global * 2.0)
		else:
			for i in plate.size():
				_draw_item(plate[i], pc + Vector2(-16 + i * 16, -3 + (i % 2) * 8), 10)
	# lamp glow
	for lx in [2.7, 8.3]:
		_spr("lamp_glow", Vector2(ORIGIN.x + lx * TILE, wy + 150), 3.4, 0.0, Color(1, 0.95, 0.8, 0.28 + sin(t_global * 3.0 + lx) * 0.03))


func _draw_tile(kind: String, rect: Rect2, x: int, y: int) -> void:
	var ctr := rect.position + rect.size / 2.0
	var checker := (x + y) % 2 == 0
	match kind:
		"#":
			_tile_spr("wall", rect)
			return
		"q":
			_tile_spr("carpet_a" if checker else "carpet_b", rect)
			return
		".":
			_tile_spr("floor_a" if checker else "floor_b", rect)
			return
	_tile_spr("floor_a" if checker else "floor_b", rect)
	var c := Vector2i(x, y)
	var spr_name := ""
	match kind:
		"X": spr_name = "counter"
		"M": spr_name = "crate_meat"
		"V": spr_name = "crate_veg"
		"D": spr_name = "crate_dough"
		"C": spr_name = "chop_board"
		"S": spr_name = "stove"
		"O": spr_name = "oven"
		"A": spr_name = "plate_station"
		"B": spr_name = "bin"
		"T":
			var open := false
			for s in seats:
				if Vector2i(s) == c:
					open = true
			spr_name = "seat" if open else "seat_closed"
	var k := 0.0
	if pops.has(c):
		k = sin(float(pops[c]) / 0.3 * PI) * 0.13
	var jitter := 0.0
	if kind == "C" and stations.has(c) and stations[c]["st"] == "working":
		jitter = sin(t_global * 45.0) * 1.6
		k += absf(sin(t_global * 22.0)) * 0.025
	_xf_about(rect.position + Vector2(TILE / 2.0, TILE * 0.92), 1.0 + k, 1.0 - k)
	_tile_spr(spr_name, Rect2(rect.position + Vector2(0, jitter), rect.size))
	_xf_reset()
	if kind == "T":
		return
	if kind == "S" or kind == "O":
		pass


func _draw_station_state(c: Vector2i, s: Dictionary) -> void:
	var kind: String = MAP[c.y][c.x]
	var ctr := _cell_center(c)
	var rect := Rect2(ORIGIN + Vector2(c) * TILE, Vector2(TILE, TILE))
	var st: String = s["st"]
	var k := 0.0
	if pops.has(c):
		k = sin(float(pops[c]) / 0.3 * PI) * 0.13
	if kind == "S" and st != "idle":
		for fx in [-20.0, 0.0, 20.0]:
			var fl := 0.8 + sin(t_global * 17.0 + fx) * 0.2
			_spr("flame", ctr + Vector2(fx, 14), 0.5 * fl, 0.0, Color(1, 1, 1, 0.95), Vector2(1.0, fl))
		_xf_about(rect.position + Vector2(TILE / 2.0, TILE * 0.92), 1.0 + k, 1.0 - k)
		_tile_spr("pot", Rect2(rect.position + Vector2(0, -4 + sin(t_global * 25.0) * (0.8 if st == "working" else 0.0)), rect.size))
		_xf_reset()
	if kind == "O" and st != "idle":
		var g := 0.55 + sin(t_global * 5.0) * 0.12
		_tile_spr("oven_glow", rect, Color(1, 1, 1, g if st != "burnt" else 0.25))
	if kind == "C" and st != "idle":
		_draw_item(s["out"] if st != "working" else s["in"], ctr + Vector2(0, -4 + sin(t_global * 45.0) * 1.4), 13)
	if st == "idle":
		return
	# status badge with progress ring
	var badge := ctr + Vector2(21, -23)
	var bsc := 1.0
	var ring := C_GOOD
	var frac := 1.0
	var rule: Dictionary = Data.RULES[kind]
	var burn: float = rule["burn"]
	if st == "working":
		frac = clampf(float(s["t"]) / _station_time(kind), 0.0, 1.0)
		ring = Color("ffb703")
	elif st == "done":
		bsc = 1.0 + sin(t_global * 8.0) * 0.07
		if burn > 0.0:
			var left: float = burn - float(s["t"])
			frac = clampf(left / (burn - _station_time(kind)), 0.0, 1.0)
			ring = C_GOOD.lerp(C_BAD, 1.0 - frac)
			if left < 2.5:
				badge += Vector2(sin(t_global * 60.0) * 1.8, 0)
				bsc = 1.1 + sin(t_global * 14.0) * 0.1
	elif st == "burnt":
		ring = C_BAD
		bsc = 1.0 + sin(t_global * 10.0) * 0.08
	_xf_about(badge, bsc, bsc)
	draw_circle(badge + Vector2(0, 2), 21, Color(0, 0, 0, 0.3))
	draw_circle(badge, 21, C_OUTLINE)
	draw_circle(badge, 18, Color.WHITE if st != "burnt" else Color("ffd0d0"))
	draw_arc(badge, 15, -PI / 2, -PI / 2 + TAU * frac, 28, ring, 4.0)
	var icon: String = s["in"] if st == "working" else s["out"]
	_draw_item(icon, badge + Vector2(0, 1), 9)
	_xf_reset()
	if st == "done" and burn > 0.0 and float(s["t"]) > burn - 2.5 and int(t_global * 6.0) % 2 == 0:
		_ctext("!", badge + Vector2(0, -26), 34, C_BAD)


func _draw_customers_and_chef() -> void:
	# draw back-to-front so a lower thing overlaps a higher one
	for c in customers:
		_draw_customer(c)
	var bob := sin(t_global * 3.0) * 1.0
	_draw_chef(chef_pos, chef_face, bob, 1.0, clampf(chef_vel.x / 260.0, -1.0, 1.0) * 0.08, chef_sq, walk_phase, 0.7)
	if held != "":
		var hp := held_pos + Vector2(0, -34 + sin(t_global * 5.0) * 2.0)
		var k := 1.0 + 0.35 * _ease_out(held_pop) * held_pop
		_xf_about(hp, k, k)
		draw_circle(hp + Vector2(0, 3), 27, Color(0, 0, 0, 0.25))
		draw_circle(hp, 27, C_OUTLINE)
		draw_circle(hp, 24, Color("fffaf0"))
		draw_circle(hp + Vector2(-8, -9), 7, Color(1, 1, 1, 0.9))
		_draw_item(held, hp, 15)
		_xf_reset()


func _draw_customer(c: Dictionary) -> void:
	var seat: Vector2i = c["seat"]
	var base := _cell_center(seat) + Vector2(0, TILE * 0.98)
	var st: String = c["st"]
	var t: float = c["t"]
	var side := 1.0 if seat.x % 4 == 0 else -1.0
	var slide := 0.0
	var hop := 0.0
	var alpha := 1.0
	if t < 0.8:
		var e := 1.0 - _ease_out(t / 0.8)
		slide = e * 170.0 * side
		hop = absf(sin(t * 16.0)) * 7.0 * e
	if st == "happy":
		hop = absf(sin(t * 9.0)) * 10.0 * maxf(0.0, 1.0 - t * 0.8)
		if t > 0.7:
			var e2 := (t - 0.7) / 0.5
			slide = -e2 * e2 * 170.0 * side
			alpha = 1.0 - clampf(e2, 0.0, 1.0)
	elif st == "angry":
		hop = 0.0
		slide = sin(t * 40.0) * 3.0 * maxf(0.0, 1.0 - t)
		if t > 0.7:
			var e3 := (t - 0.7) / 0.5
			slide += e3 * e3 * 170.0 * -side
			alpha = 1.0 - clampf(e3, 0.0, 1.0)
	var pos := base + Vector2(slide, -hop + sin(t_global * 3.0 + seat.x) * 1.5)
	var look: int = c["look"]
	var mod := Color(1, 1, 1, alpha)
	var frac: float = float(c["pat"]) / float(c["max"])
	_ell(pos + Vector2(0, 66), 38, 8, Color(0, 0, 0, 0.22 * alpha))
	_spr("cust_body_%d" % look, pos + Vector2(0, 42), 1.25, 0.0, mod)
	_spr("cust_head_%d" % look, pos + Vector2(0, -5), 1.25, 0.0, mod)
	var mood := 1.0 if st == "happy" else (-1.0 if st == "angry" else clampf((frac - 0.4) * 2.5, -1.0, 0.7))
	var blink := 0.15 if fmod(t_global + seat.x * 0.7, 4.0) > 3.85 else 1.0
	if alpha > 0.5:
		_draw_face(pos, 0.0, mood, blink, 9.0, 1.25)
	if st == "happy":
		for i in 3:
			var hy := pos.y - 40 - fmod(t * 40.0 + i * 20.0, 60.0)
			_spr("heart", Vector2(pos.x + (i - 1) * 22, hy), 0.5, 0.0, Color(1, 1, 1, alpha))
	elif st == "angry":
		_txt("#!?", pos + Vector2(-20, -34), 26, C_BAD)
	# order bubble
	if st == "wait":
		var bk := _ease_back((t - 0.6) / 0.4)
		if bk > 0.0:
			var urgent := frac < 0.3
			var shake := sin(t_global * 40.0) * 2.0 if urgent else 0.0
			var bpos := pos + Vector2(shake, 96)
			_xf_about(bpos + Vector2(0, -20), bk, bk)
			_spr("bubble", bpos + Vector2(0, 28), 1.0, 0.0, Color(1, 0.85, 0.85) if urgent else Color.WHITE)
			var dish_id: String = c["order"]
			var matches := held.begins_with("dish:") and held.substr(5) == dish_id
			var dsc := 20.0 + (2.0 * sin(t_global * 8.0) if matches else 0.0)
			_draw_dish(dish_id, bpos + Vector2(0, 28), dsc)
			var bar_col := C_GOOD if frac > 0.5 else (C_GOLD if frac > 0.25 else C_BAD)
			_bar(Rect2(bpos + Vector2(-38, 62), Vector2(76, 9)), frac, bar_col)
			_xf_reset()
			if matches:
				draw_arc(pos + Vector2(0, 30), 66 + sin(t_global * 8.0) * 3.0, 0, TAU, 32, Color(C_GOLD.r, C_GOLD.g, C_GOLD.b, 0.85), 4.0)


func _draw_hud() -> void:
	var goals: Array = lv["goals"]
	var nxt := int(goals[2])
	for g in goals:
		if earned < int(g):
			nxt = int(g)
			break
	_nine("panel", Rect2(8, 8, 226, 58), Color("3a2a4e"), 36.0, 36.0, 36.0)
	_spr("coin", Vector2(40, 37), 0.95 * (1.0 + hud_bump * 0.3))
	_txt("%d / %d" % [int(round(earned_shown)), nxt], Vector2(68, 48), 28, C_GOLD)
	var secs := int(ceil(time_left))
	var urgent := time_left < 20.0
	var tcol := Color.WHITE if not urgent else (C_BAD if int(t_global * 4.0) % 2 == 0 else Color.WHITE)
	var tsc := 1.0 + (sin(t_global * 8.0) * 0.05 if urgent else 0.0)
	_nine("panel", Rect2(W / 2 - 20, 8, 140, 58), Color("3a2a4e"), 36.0, 36.0, 36.0)
	_spr("wall_clock", Vector2(W / 2 + 12, 37), 0.34, sin(t_global * 3.0) * 0.05 if urgent else 0.0)
	_xf_about(Vector2(W / 2 + 80, 37), tsc, tsc)
	_ctext("%d:%02d" % [secs / 60, secs % 60], Vector2(W / 2 + 62, 50), 32, tcol)
	_xf_reset()
	_button(Rect2(W - 78, 10, 62, 52), "II", "pause", Color("8d99ae"), 26)
	# star progress bar
	var gmax := float(goals[2])
	var bar := Rect2(14, 76, W - 28, 12)
	_bar(bar, earned_shown / gmax, C_GOLD)
	for k in 3:
		var sx := bar.position.x + bar.size.x * float(goals[k]) / gmax
		if k == 2:
			sx -= 10.0
		var on := earned >= int(goals[k])
		_star(Vector2(sx, 82), 15 + (3.0 * sin(t_global * 6.0) if on else 0.0), on)
	if streak >= 2:
		_xf_about(Vector2(W / 2 - 120, 37), 1.0 + 0.1 * sin(t_global * 10.0), 1.0 + 0.1 * sin(t_global * 10.0))
		_nine("panel", Rect2(W / 2 - 170, 12, 100, 50), Color("ff7a3d"), 36.0, 36.0, 36.0)
		_ctext("x%d" % streak, Vector2(W / 2 - 120, 49), 30)
		_xf_reset()
	# messages and tutorial
	var tut := _tutorial_text()
	if message_time > 0.0:
		var k := _ease_back((2.2 - message_time) / 0.25)
		_xf_about(Vector2(W / 2, 1092), k, k)
		_nine("panel", Rect2(W / 2 - 290, 1068, 580, 50), Color("3a2a4e"), 36.0, 36.0, 36.0)
		_ctext(message, Vector2(W / 2, 1102), 26, C_GOLD)
		_xf_reset()
	elif tut != "" and intro <= 0.0:
		_nine("panel", Rect2(W / 2 - 310, 1068, 620, 50), Color("3a2a4e"), 36.0, 36.0, 36.0)
		_ctext(tut, Vector2(W / 2, 1102), 26, Color.WHITE)
	# recipe strip
	draw_rect(Rect2(0, 1124, W, 156), Color("2a1d3a"))
	draw_rect(Rect2(0, 1124, W, 4), Color("4a3a66"))
	var recs: Array = lv["recipes"]
	for k in recs.size():
		var id: String = recs[k]
		var rx := 10.0 + (k % 2) * 355.0
		var ry := 1136.0 + (k / 2) * 70.0
		_nine("panel", Rect2(rx, ry, 345, 66), Color("5a4a7a"), 36.0, 36.0, 36.0)
		_draw_dish(id, Vector2(rx + 34, ry + 33), 15)
		_txt(Data.RECIPES[id]["name"], Vector2(rx + 68, ry + 28), 22, Color.WHITE)
		_txt(Data.RECIPES[id]["steps"], Vector2(rx + 68, ry + 53), 14, Color(1, 1, 1, 0.8), HORIZONTAL_ALIGNMENT_LEFT, 270)
