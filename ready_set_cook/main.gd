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


func _ready() -> void:
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
	sfx.enabled = sound_on


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
			state = S.LEVELS
		"shop":
			state = S.SHOP
		"menu":
			state = S.MENU
		"sound":
			sound_on = not sound_on
			sfx.enabled = sound_on
			_save()
		"pause":
			state = S.PAUSE
		"resume":
			state = S.PLAY
		"restart":
			_start_level(cur_level)
		"retry":
			state = S.BRIEF
		"next":
			cur_level = mini(cur_level + 1, Data.LEVELS.size() - 1)
			state = S.BRIEF
		"start":
			_start_level(cur_level)
		"levels":
			state = S.LEVELS
		_:
			if id.begins_with("lvl_"):
				cur_level = int(id.substr(4))
				lv = Data.LEVELS[cur_level]
				state = S.BRIEF
			elif id.begins_with("buy_"):
				_buy(id.substr(4))


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
	if state == S.RESULT:
		result_t += delta
		var star_times := [0.8, 1.4, 2.0]
		for i in result_stars:
			var before: float = result_t - delta
			if before < star_times[i] and result_t >= star_times[i]:
				sfx.play("star", 1.0 + i * 0.25)
	_update_fx(delta)
	if state == S.PLAY:
		_update_game(delta)
	queue_redraw()


func _update_fx(delta: float) -> void:
	for i in range(particles.size() - 1, -1, -1):
		var q: Dictionary = particles[i]
		q["life"] = float(q["life"]) - delta
		if float(q["life"]) <= 0.0:
			particles.remove_at(i)
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
	chef_moving = false
	if path.is_empty():
		return
	var target := _cell_center(path[0])
	var to := target - chef_pos
	var step: float = 260.0 * (1.0 + 0.12 * _ulv("boots")) * delta
	if to.length() <= step:
		chef_pos = target
		path.remove_at(0)
		if path.is_empty() and target_cell != NO_CELL:
			var c := target_cell
			target_cell = NO_CELL
			_interact(c)
	else:
		chef_moving = true
		if absf(to.x) > 1.0:
			chef_face = signf(to.x)
		chef_pos += to.normalized() * step


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
		particles.append({"p": _cell_center(c) + Vector2(randf_range(-12, 12), -18), "v": Vector2(randf_range(-10, 10), -50), "g": -10.0, "life": 0.7, "max": 0.7, "col": col, "r": randf_range(4, 8)})


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
		"skin": [Color("f1c27d"), Color("e0ac69"), Color("c68642"), Color("8d5524"), Color("ffdbac")][randi() % 5],
		"hair": [Color("3b2f2f"), Color("a0522d"), Color("f4d35e"), Color("222222"), Color("c1440e"), Color("8338ec")][randi() % 6],
		"shirt": [Color("ef476f"), Color("06d6a0"), Color("118ab2"), Color("ffd166"), Color("9b5de5")][randi() % 5],
	})
	sfx.play("bell", 1.0 + randf_range(-0.1, 0.1))


# ====================================================================
# Interactions
# ====================================================================

func _interact(cell: Vector2i) -> void:
	var kind: String = MAP[cell.y][cell.x]
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
	_burst(pos + Vector2(0, 60), C_GOLD, 14, 170.0)
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
		particles.append({"p": p, "v": v, "g": 260.0, "life": 0.6, "max": 0.6, "col": col, "r": randf_range(3, 6)})


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
	draw_string_outline(font, pos, s, align, w, size, maxi(2, size / 7), Color(0, 0, 0, 0.55))
	draw_string(font, pos, s, align, w, size, col)


func _ctext(s: String, center: Vector2, size: int, col: Color = Color.WHITE) -> void:
	_txt(s, Vector2(center.x - 500.0, center.y), size, col, HORIZONTAL_ALIGNMENT_CENTER, 1000.0)


func _ell(c: Vector2, rx: float, ry: float, col: Color) -> void:
	draw_set_transform(c, 0.0, Vector2(1.0, ry / rx))
	draw_circle(Vector2.ZERO, rx, col)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


func _star(c: Vector2, r: float, col: Color) -> void:
	var pts := PackedVector2Array()
	for i in 10:
		var rad := r if i % 2 == 0 else r * 0.45
		var a := -PI / 2.0 + i * PI / 5.0
		pts.append(c + Vector2(cos(a), sin(a)) * rad)
	draw_colored_polygon(pts, col)


func _coin(c: Vector2, r: float) -> void:
	draw_circle(c, r, Color("e09f3e"))
	draw_circle(c, r * 0.8, C_GOLD)
	draw_arc(c, r * 0.5, 0.6, 2.4, 8, Color("e09f3e"), maxf(1.5, r * 0.12))


func _button(rect: Rect2, label: String, id: String, col: Color = C_ACCENT, fsize: int = 32, enabled: bool = true) -> void:
	buttons.append({"rect": rect, "id": id})
	var hover := rect.has_point(get_local_mouse_position())
	var down := hover and mouse_down
	var c := col if enabled else Color("555770")
	if hover and enabled:
		c = c.lightened(0.12)
	var r := rect
	if down:
		r = rect.grow(-3)
	_rr(Rect2(r.position + Vector2(0, 6), r.size), c.darkened(0.45), 18)
	_rr(r, c, 18, c.lightened(0.25), 3)
	_ctext(label, Vector2(r.position.x + r.size.x / 2.0, r.position.y + r.size.y / 2.0 + fsize * 0.35), fsize)


# ----- item art -----

func _draw_item(id: String, c: Vector2, s: float) -> void:
	if id.begins_with("dish:"):
		_draw_dish(id.substr(5), c, s)
		return
	match id:
		"veg":
			draw_circle(c, s, Color("6a994e"))
			draw_circle(c + Vector2(-s * 0.2, -s * 0.2), s * 0.6, Color("a7c957"))
			draw_arc(c, s * 0.5, 0.3, 2.2, 10, Color("386641"), 2.0)
			draw_arc(c, s * 0.8, 3.4, 5.2, 10, Color("386641"), 2.0)
		"meat":
			_ell(c, s * 1.05, s * 0.75, Color("e5989b"))
			draw_arc(c, s * 0.5, 0.2, 2.6, 10, Color("ffcdb2"), 2.5)
			draw_circle(c + Vector2(s * 0.45, 0), s * 0.22, Color("fff1e6"))
		"dough":
			draw_circle(c, s, Color("f1e3c0"))
			draw_circle(c + Vector2(-s * 0.3, -s * 0.3), s * 0.35, Color("fff8e7"))
		"veg_chop":
			for o in [Vector2(-0.45, -0.35), Vector2(0.4, -0.4), Vector2(-0.1, 0.05), Vector2(-0.5, 0.45), Vector2(0.45, 0.4)]:
				var p: Vector2 = c + o * s
				draw_rect(Rect2(p - Vector2(s * 0.3, s * 0.3), Vector2(s * 0.6, s * 0.6)), Color("80b918"))
				draw_rect(Rect2(p - Vector2(s * 0.15, s * 0.15), Vector2(s * 0.3, s * 0.3)), Color("b5e48c"))
		"meat_chop":
			for o in [Vector2(-0.45, -0.3), Vector2(0.4, -0.4), Vector2(0.0, 0.05), Vector2(-0.4, 0.45), Vector2(0.45, 0.35)]:
				draw_circle(c + o * s, s * 0.34, Color("e5989b"))
		"veg_cook":
			draw_circle(c, s, Color("bc6c25"))
			for o in [Vector2(-0.4, -0.2), Vector2(0.3, -0.35), Vector2(0.1, 0.35)]:
				draw_circle(c + o * s, s * 0.28, Color("606c38"))
		"meat_cooked":
			_ell(c, s * 1.05, s * 0.75, Color("7f4f24"))
			for i in 3:
				draw_line(c + Vector2(-s * 0.5 + i * s * 0.5, -s * 0.4), c + Vector2(-s * 0.2 + i * s * 0.5, s * 0.4), Color("432818"), 2.5)
		"patty":
			draw_circle(c, s, Color("6f4518"))
			draw_circle(c + Vector2(-s * 0.25, -s * 0.25), s * 0.35, Color("8a5a2b"))
		"bun":
			_ell(c + Vector2(0, s * 0.1), s * 1.1, s * 0.8, Color("e9a23b"))
			draw_rect(Rect2(c + Vector2(-s * 1.1, s * 0.35), Vector2(s * 2.2, s * 0.6)), Color(0, 0, 0, 0))
			for o in [Vector2(-0.4, -0.2), Vector2(0.1, -0.35), Vector2(0.45, -0.1), Vector2(0.0, 0.1)]:
				draw_circle(c + o * s, s * 0.1, Color("fff1c1"))
		"burnt":
			draw_circle(c, s * 0.9, Color("1a1a1a"))
			draw_circle(c + Vector2(s * 0.5, -s * 0.2), s * 0.5, Color("2b2b2b"))
			draw_circle(c + Vector2(-s * 0.4, s * 0.3), s * 0.4, Color("262626"))
		_:
			draw_circle(c, s * 0.6, Color.MAGENTA)


func _draw_dish(id: String, c: Vector2, s: float) -> void:
	draw_circle(c + Vector2(0, 2), s * 1.3, Color(0, 0, 0, 0.25))
	draw_circle(c, s * 1.25, Color("eaeaea"))
	draw_circle(c, s * 1.0, Color("ffffff"))
	match id:
		"salad":
			for o in [Vector2(-0.4, -0.2), Vector2(0.35, -0.3), Vector2(0.0, 0.3), Vector2(-0.2, -0.5), Vector2(0.4, 0.2)]:
				draw_circle(c + o * s, s * 0.38, Color("80b918"))
			draw_circle(c + Vector2(0.2, 0.0) * s, s * 0.2, Color("e63946"))
			draw_circle(c + Vector2(-0.3, 0.3) * s, s * 0.17, Color("e63946"))
		"steak":
			_ell(c + Vector2(-s * 0.1, 0), s * 0.75, s * 0.55, Color("7f4f24"))
			for i in 3:
				draw_line(c + Vector2(-s * 0.5 + i * s * 0.35, -s * 0.3), c + Vector2(-s * 0.35 + i * s * 0.35, s * 0.3), Color("432818"), 2.0)
			draw_circle(c + Vector2(0.55, 0.4) * s, s * 0.25, Color("80b918"))
			draw_circle(c + Vector2(0.65, 0.1) * s, s * 0.2, Color("80b918"))
		"soup":
			draw_circle(c, s * 0.85, Color("bc6c25"))
			draw_circle(c, s * 0.6, Color("dda15e"))
			for o in [Vector2(-0.25, -0.1), Vector2(0.2, 0.15), Vector2(0.0, -0.3)]:
				draw_circle(c + o * s, s * 0.14, Color("606c38"))
		"burger":
			_ell(c + Vector2(0, s * 0.45), s * 0.85, s * 0.3, Color("e9a23b"))
			draw_rect(Rect2(c + Vector2(-s * 0.85, s * 0.05), Vector2(s * 1.7, s * 0.3)), Color("6f4518"))
			draw_rect(Rect2(c + Vector2(-s * 0.9, -s * 0.12), Vector2(s * 1.8, s * 0.17)), Color("80b918"))
			_ell(c + Vector2(0, -s * 0.2), s * 0.85, s * 0.5, Color("e9a23b"))
			for o in [Vector2(-0.4, -0.35), Vector2(0.1, -0.5), Vector2(0.45, -0.3)]:
				draw_circle(c + o * s, s * 0.08, Color("fff1c1"))


func _draw_chef(c: Vector2, face: float, bob: float, scale_f: float = 1.0) -> void:
	var p := c + Vector2(0, bob)
	draw_circle(c + Vector2(0, 22 * scale_f), 20 * scale_f, Color(0, 0, 0, 0.25))
	_ell(p + Vector2(0, 8 * scale_f), 20 * scale_f, 22 * scale_f, Color("ffffff"))
	_ell(p + Vector2(0, 12 * scale_f), 14 * scale_f, 16 * scale_f, Color("4cc9f0"))
	draw_circle(p + Vector2(0, -12 * scale_f), 17 * scale_f, Color("ffd5b5"))
	draw_circle(p + Vector2(0, -34 * scale_f), 12 * scale_f, Color("ffffff"))
	draw_circle(p + Vector2(-11 * scale_f, -30 * scale_f), 9 * scale_f, Color("ffffff"))
	draw_circle(p + Vector2(11 * scale_f, -30 * scale_f), 9 * scale_f, Color("ffffff"))
	draw_rect(Rect2(p + Vector2(-14, -28) * scale_f, Vector2(28, 8) * scale_f), Color("ffffff"))
	var fx := face * 4.0 * scale_f
	draw_circle(p + Vector2(-6 * scale_f + fx, -12 * scale_f), 2.6 * scale_f, Color("222222"))
	draw_circle(p + Vector2(6 * scale_f + fx, -12 * scale_f), 2.6 * scale_f, Color("222222"))
	draw_arc(p + Vector2(fx, -7 * scale_f), 6 * scale_f, 0.3, PI - 0.3, 8, Color("c1440e"), 2.0)


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


func _draw_background() -> void:
	draw_rect(Rect2(-20, -20, W + 40, H + 40), C_BG)
	if state == S.PLAY or state == S.PAUSE:
		return
	# slow drifting checker pattern for menus
	var off := fmod(t_global * 20.0, 80.0)
	for i in range(-1, 10):
		for j in range(-1, 17):
			if (i + j) % 2 == 0:
				draw_rect(Rect2(i * 80.0 + off - 80.0, j * 80.0 + off - 80.0, 80, 80), Color(1, 1, 1, 0.025))


func _draw_particles() -> void:
	for q in particles:
		var a: float = float(q["life"]) / float(q["max"])
		var col: Color = q["col"]
		col.a *= a
		draw_circle(q["p"], float(q["r"]) * (0.5 + a * 0.5), col)
	for q in popups:
		var a: float = clampf(float(q["life"]) * 2.0, 0.0, 1.0)
		var col: Color = q["col"]
		col.a = a
		_ctext(q["text"], q["p"], int(q["size"]), col)


func _coin_bar() -> void:
	_rr(Rect2(W - 210, 18, 192, 52), Color(0, 0, 0, 0.35), 26)
	_coin(Vector2(W - 184, 44), 17)
	_txt(str(coins), Vector2(W - 156, 56), 30, C_GOLD)


func _draw_menu() -> void:
	_coin_bar()
	var bob := sin(t_global * 3.0) * 8.0
	_ctext("READY", Vector2(W / 2, 250 + bob), 110, C_GOLD)
	_ctext("SET", Vector2(W / 2, 350 - bob), 110, Color("ffffff"))
	_ctext("COOK!", Vector2(W / 2, 450 + bob), 130, C_ACCENT)
	_draw_chef(Vector2(W / 2, 640 + sin(t_global * 4.0) * 10.0), 1.0, 0.0, 2.6)
	_draw_item("dish:burger", Vector2(W / 2 - 200, 690 + sin(t_global * 2.0) * 8.0), 34)
	_draw_item("dish:salad", Vector2(W / 2 + 200, 700 + cos(t_global * 2.0) * 8.0), 34)
	_button(Rect2(W / 2 - 190, 840, 380, 100), "PLAY", "play", C_ACCENT, 48)
	_button(Rect2(W / 2 - 190, 965, 380, 84), "UPGRADES", "shop", Color("4361ee"), 34)
	_button(Rect2(W / 2 - 190, 1070, 380, 70), "SOUND: ON" if sound_on else "SOUND: OFF", "sound", Color("6c757d"), 26)
	var total := 0
	for s in stars:
		total += int(s)
	_ctext("Stars: %d / %d" % [total, Data.LEVELS.size() * 3], Vector2(W / 2, 1200), 26, C_GOLD)
	_ctext("v0.2", Vector2(W / 2, 1245), 18, Color(1, 1, 1, 0.4))


func _draw_levels() -> void:
	_coin_bar()
	_button(Rect2(20, 18, 140, 52), "BACK", "menu", Color("6c757d"), 24)
	_ctext("Choose a level", Vector2(W / 2, 150), 50)
	for i in Data.LEVELS.size():
		var col := i % 2
		var row := i / 2
		var r := Rect2(30 + col * 340, 190 + row * 215, 320, 195)
		var d: Dictionary = Data.LEVELS[i]
		var open := _unlocked(i)
		var base := C_PANEL if open else Color("23243a")
		_rr(Rect2(r.position + Vector2(0, 6), r.size), base.darkened(0.4), 20)
		_rr(r, base, 20, Color("ffffff") if open and int(stars[i]) == 0 else Color(1, 1, 1, 0.1), 3 if open and int(stars[i]) == 0 else 2)
		if open:
			buttons.append({"rect": r, "id": "lvl_%d" % i})
			_txt(str(i + 1), r.position + Vector2(16, 60), 60, C_ACCENT)
			_txt(d["name"], r.position + Vector2(16, 100), 26, Color.WHITE, HORIZONTAL_ALIGNMENT_LEFT, 290)
			var recs: Array = d["recipes"]
			for k in recs.size():
				_draw_dish(recs[k], r.position + Vector2(36 + k * 62, 135), 15)
			for k in 3:
				var got := k < int(stars[i])
				_star(r.position + Vector2(220 + k * 30, 40), 14, C_GOLD if got else Color(1, 1, 1, 0.15))
			_txt("%ds" % int(d["time"]), r.position + Vector2(230, 80), 22, Color(1, 1, 1, 0.7))
		else:
			_ctext("LOCKED", r.position + Vector2(160, 105), 34, Color(1, 1, 1, 0.3))
			_ctext("get 1 star on level %d" % i, r.position + Vector2(160, 140), 18, Color(1, 1, 1, 0.3))


func _draw_shop() -> void:
	_coin_bar()
	_button(Rect2(20, 18, 140, 52), "BACK", "menu", Color("6c757d"), 24)
	_ctext("Upgrades", Vector2(W / 2, 150), 56)
	var y := 200.0
	for u in Data.UPGRADES:
		var id: String = u["id"]
		var lvl := _ulv(id)
		var mx: int = u["max"]
		var r := Rect2(24, y, 672, 175)
		_rr(Rect2(r.position + Vector2(0, 6), r.size), C_PANEL.darkened(0.4), 20)
		_rr(r, C_PANEL, 20)
		_txt(u["name"], r.position + Vector2(24, 52), 34, Color.WHITE)
		_txt(u["desc"], r.position + Vector2(24, 88), 20, Color(1, 1, 1, 0.65))
		for k in mx:
			_rr(Rect2(r.position + Vector2(24 + k * 44, 112), Vector2(36, 28)), C_GOOD if k < lvl else Color(1, 1, 1, 0.12), 8)
		if lvl >= mx:
			_ctext("MAX", r.position + Vector2(570, 100), 34, C_GOLD)
		else:
			var cost := Data.upgrade_cost(lvl)
			_button(Rect2(r.position + Vector2(450, 40), Vector2(200, 95)), "%d" % cost, "buy_" + id, Color("2a9d8f"), 34, coins >= cost)
			_coin(r.position + Vector2(480, 88), 14)
		y += 190.0
	_ctext("Coins come from serving customers.", Vector2(W / 2, 1180), 22, Color(1, 1, 1, 0.5))


func _draw_brief() -> void:
	var d: Dictionary = Data.LEVELS[cur_level]
	_button(Rect2(20, 18, 140, 52), "BACK", "levels", Color("6c757d"), 24)
	_ctext("Level %d" % (cur_level + 1), Vector2(W / 2, 170), 40, Color(1, 1, 1, 0.7))
	_ctext(d["name"], Vector2(W / 2, 240), 64, C_GOLD)
	_ctext("%d seconds  -  %d tables" % [int(d["time"]), int(d["seats"])], Vector2(W / 2, 300), 26)
	_ctext("MENU", Vector2(W / 2, 400), 34, C_ACCENT)
	var recs: Array = d["recipes"]
	var y := 430.0
	for id in recs:
		var r := Rect2(40, y, 640, 120)
		_rr(r, C_PANEL, 20)
		_draw_dish(id, Vector2(100, y + 60), 32)
		_txt("%s  (%d coins)" % [Data.RECIPES[id]["name"], int(Data.RECIPES[id]["price"])], Vector2(165, y + 52), 30, Color.WHITE)
		_txt(Data.RECIPES[id]["steps"], Vector2(165, y + 92), 21, Color(1, 1, 1, 0.7), HORIZONTAL_ALIGNMENT_LEFT, 500)
		y += 132.0
	var goals: Array = d["goals"]
	_ctext("Earn coins for stars", Vector2(W / 2, 1010), 28)
	for k in 3:
		var cx := W / 2 - 200 + k * 200
		_star(Vector2(cx, 1060), 24, C_GOLD if k < int(stars[cur_level]) else Color(1, 1, 1, 0.25))
		_ctext(str(int(goals[k])), Vector2(cx, 1125), 30, C_GOLD)
	_button(Rect2(W / 2 - 170, 1150, 340, 100), "START!", "start", C_ACCENT, 48)


func _draw_pause() -> void:
	draw_rect(Rect2(0, 0, W, H), Color(0, 0, 0, 0.7))
	buttons = []
	_ctext("PAUSED", Vector2(W / 2, 400), 90)
	_button(Rect2(W / 2 - 190, 500, 380, 100), "RESUME", "resume", C_ACCENT, 44)
	_button(Rect2(W / 2 - 190, 630, 380, 84), "RESTART", "restart", Color("4361ee"), 32)
	_button(Rect2(W / 2 - 190, 745, 380, 84), "QUIT", "levels", Color("6c757d"), 32)


func _draw_result() -> void:
	var t := result_t
	var win := result_stars > 0
	_ctext("TIME'S UP!" if win else "NOT ENOUGH...", Vector2(W / 2, 200), 70, C_GOLD if win else C_BAD)
	_ctext(lv["name"], Vector2(W / 2, 260), 30, Color(1, 1, 1, 0.7))
	var goals: Array = lv["goals"]
	for k in 3:
		var cx := W / 2 - 160 + k * 160
		var cy := 400.0 - (30.0 if k == 1 else 0.0)
		_star(Vector2(cx, cy), 62, Color(1, 1, 1, 0.12))
		var show_t: float = [0.8, 1.4, 2.0][k]
		if k < result_stars and t >= show_t:
			var sc := 1.0 + maxf(0.0, 0.6 - (t - show_t) * 2.0)
			_star(Vector2(cx, cy), 62.0 * sc, C_GOLD)
		_ctext(str(int(goals[k])), Vector2(cx, cy + 100), 24, Color(1, 1, 1, 0.6))
	var shown := int(minf(1.0, t / 0.8) * earned)
	_coin(Vector2(W / 2 - 110, 610), 26)
	_txt("+%d" % shown, Vector2(W / 2 - 70, 628), 64, C_GOLD)
	_ctext("Customers served: %d    Lost: %d" % [served, lost], Vector2(W / 2, 700), 28)
	_ctext("Best combo: x%d" % best_streak, Vector2(W / 2, 745), 28)
	if result_new_best and result_stars > 0:
		_ctext("NEW BEST!", Vector2(W / 2, 800 + sin(t * 8.0) * 4.0), 40, C_ACCENT)
	if level_unlocked_msg:
		_ctext("Next level unlocked!", Vector2(W / 2, 850), 30, C_GOOD)
	if t > 1.0:
		var can_next := result_stars > 0 and cur_level + 1 < Data.LEVELS.size()
		if can_next:
			_button(Rect2(W / 2 - 190, 920, 380, 100), "NEXT LEVEL", "next", C_ACCENT, 40)
		_button(Rect2(W / 2 - 190, 1040, 380, 80), "RETRY", "retry", Color("4361ee"), 32)
		_button(Rect2(W / 2 - 190, 1140, 180, 70), "LEVELS", "levels", Color("6c757d"), 24)
		_button(Rect2(W / 2 + 10, 1140, 180, 70), "UPGRADES", "shop", Color("2a9d8f"), 22)


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
		return "Tap the green VEG crate. Salad = 2 chopped veg"
	return ""


func _draw_game() -> void:
	_draw_kitchen()
	_draw_customers()
	_draw_chef_and_hud()
	if intro > 0.0:
		_draw_intro()
	elif banner_t > 0.0:
		var a := clampf(banner_t, 0.0, 1.0)
		var sc := 1.0 + (1.4 - banner_t) * 0.15
		_ctext(banner, Vector2(W / 2, 560), int(90 * sc), Color(C_GOLD.r, C_GOLD.g, C_GOLD.b, a))


func _draw_intro() -> void:
	draw_rect(Rect2(0, 0, W, H), Color(0, 0, 0, 0.45))
	# 3 seconds: 0-1s READY, 1-2s SET, 2-3s COOK
	var elapsed := 3.0 - intro
	var idx := clampi(int(elapsed), 0, 2)
	var texts := ["READY?", "SET...", "COOK!"]
	var cols := [Color("ffffff"), C_GOLD, C_ACCENT]
	var local := elapsed - float(idx)
	var sc := 1.0 + maxf(0.0, 0.5 - local * 1.5)
	_ctext(texts[idx], Vector2(W / 2, 620), int(130 * sc), cols[idx])
	_ctext("Level %d: %s" % [cur_level + 1, lv["name"]], Vector2(W / 2, 480), 34, Color(1, 1, 1, 0.8))


func _draw_kitchen() -> void:
	for y in rows:
		for x in cols:
			var kind: String = MAP[y][x]
			var rect := Rect2(ORIGIN + Vector2(x, y) * TILE, Vector2(TILE, TILE))
			_draw_tile(kind, rect, x, y)
	# machine progress + contents
	for key in stations:
		var c: Vector2i = key
		var s: Dictionary = stations[c]
		var kind: String = MAP[c.y][c.x]
		var ctr := _cell_center(c)
		var st: String = s["st"]
		if st == "idle":
			continue
		if st == "working":
			_draw_item(s["in"], ctr + Vector2(0, -2), 14)
			var frac := clampf(float(s["t"]) / _station_time(kind), 0.0, 1.0)
			draw_arc(ctr, 27, -PI / 2, -PI / 2 + TAU * frac, 24, Color("ffb703"), 5.0)
		else:
			_draw_item(s["out"], ctr + Vector2(0, -2 + sin(t_global * 6.0) * 1.5), 15)
			if st == "done":
				var rule: Dictionary = Data.RULES[kind]
				var burn: float = rule["burn"]
				var col := C_GOOD
				if burn > 0.0:
					var left: float = burn - float(s["t"])
					var frac2: float = clampf(left / (burn - _station_time(kind)), 0.0, 1.0)
					col = C_GOOD.lerp(C_BAD, 1.0 - frac2)
					draw_arc(ctr, 27, -PI / 2, -PI / 2 + TAU * frac2, 24, col, 5.0)
					if left < 2.5 and int(t_global * 6.0) % 2 == 0:
						_ctext("!", ctr + Vector2(0, -30), 30, C_BAD)
				else:
					draw_arc(ctr, 27, 0, TAU, 24, col, 5.0)
	# plate contents
	var pc := _cell_center(Vector2i(5, 3))
	if not plate.is_empty():
		var id := _recipe_for(plate)
		if id != "":
			_draw_dish(id, pc, 18)
			_star(pc + Vector2(18, -22), 9, C_GOLD)
		else:
			for i in plate.size():
				_draw_item(plate[i], pc + Vector2(-16 + i * 16, -3 + (i % 2) * 8), 9)


func _draw_tile(kind: String, rect: Rect2, x: int, y: int) -> void:
	var ctr := rect.position + rect.size / 2.0
	match kind:
		"#":
			draw_rect(rect, Color("2d2d44"))
			draw_rect(Rect2(rect.position, Vector2(TILE, 3)), Color(1, 1, 1, 0.06))
		".":
			draw_rect(rect, Color("f2e9d8") if (x + y) % 2 == 0 else Color("e8dcc4"))
		"q":
			draw_rect(rect, Color("4a3f6b") if (x + y) % 2 == 0 else Color("423860"))
		"X":
			draw_rect(rect, Color("f2e9d8") if (x + y) % 2 == 0 else Color("e8dcc4"))
			_rr(rect.grow(-3), Color("b08968"), 8, Color("8a6a4d"), 3)
		"T":
			var open := false
			for s in seats:
				if Vector2i(s) == Vector2i(x, y):
					open = true
			draw_rect(rect, Color("f2e9d8") if (x + y) % 2 == 0 else Color("e8dcc4"))
			_rr(rect.grow(-3), Color("9c6644") if open else Color("6b5a4a"), 8, Color("7f5539"), 3)
			if open:
				var glow := held.begins_with("dish:")
				_rr(Rect2(rect.position + Vector2(8, 14), Vector2(48, 36)), Color("ffffff") if not glow else Color("fff3b0"), 6)
		_:
			draw_rect(rect, Color("f2e9d8") if (x + y) % 2 == 0 else Color("e8dcc4"))
			_draw_station(kind, rect, ctr)


func _draw_station(kind: String, rect: Rect2, ctr: Vector2) -> void:
	var r := rect.grow(-3)
	match kind:
		"M":
			_rr(r, Color("b5838d"), 8, Color("6d597a"), 3)
			_draw_item("meat", ctr + Vector2(0, -4), 15)
		"V":
			_rr(r, Color("6a994e"), 8, Color("386641"), 3)
			_draw_item("veg", ctr + Vector2(0, -4), 15)
		"D":
			_rr(r, Color("e9c46a"), 8, Color("b08968"), 3)
			_draw_item("dough", ctr + Vector2(0, -4), 15)
		"C":
			_rr(r, Color("d9a066"), 8, Color("a0693a"), 3)
			draw_line(ctr + Vector2(-16, 14), ctr + Vector2(16, -14), Color("bfc0c0"), 5.0)
			draw_line(ctr + Vector2(-16, 14), ctr + Vector2(-10, 8), Color("6b4423"), 6.0)
		"S":
			_rr(r, Color("4a4e69"), 8, Color("22223b"), 3)
			draw_arc(ctr, 18, 0, TAU, 20, Color("c9ada7"), 3.0)
			draw_arc(ctr, 9, 0, TAU, 14, Color("c9ada7"), 3.0)
		"O":
			_rr(r, Color("8d99ae"), 8, Color("2b2d42"), 3)
			_rr(Rect2(r.position + Vector2(8, 14), r.size - Vector2(16, 24)), Color("ffb703").darkened(0.3), 6)
		"A":
			_rr(r, Color("cdb4db"), 8, Color("7b6d8d"), 3)
			draw_circle(ctr, 22, Color("ffffff"))
			draw_arc(ctr, 22, 0, TAU, 20, Color("c0c0c0"), 2.0)
		"B":
			_rr(r, Color("6d6875"), 8, Color("3d3a45"), 3)
			_rr(Rect2(r.position + Vector2(4, 6), Vector2(r.size.x - 8, 10)), Color("8d8a94"), 4)
			draw_line(ctr + Vector2(-10, 8), ctr + Vector2(-8, 22), Color("3d3a45"), 3.0)
			draw_line(ctr + Vector2(0, 8), ctr + Vector2(0, 22), Color("3d3a45"), 3.0)
			draw_line(ctr + Vector2(10, 8), ctr + Vector2(8, 22), Color("3d3a45"), 3.0)
	var label := ""
	match kind:
		"M": label = "MEAT"
		"V": label = "VEG"
		"D": label = "DOUGH"
		"C": label = "CHOP"
		"S": label = "PAN"
		"O": label = "OVEN"
		"A": label = "PLATE"
		"B": label = "BIN"
	if label != "":
		_txt(label, Vector2(rect.position.x, rect.position.y + TILE - 6), 12, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER, TILE)


func _draw_customers() -> void:
	for c in customers:
		var seat: Vector2i = c["seat"]
		var base := _cell_center(seat) + Vector2(0, TILE * 0.95)
		var st: String = c["st"]
		var t: float = c["t"]
		var slide := 0.0
		if st == "wait" and t < 0.5:
			slide = (1.0 - t / 0.5) * 140.0 * (1.0 if seat.x % 4 == 0 else -1.0)
		var bob := sin(t_global * 3.0 + seat.x) * 2.0
		var pos := base + Vector2(slide, bob)
		var skin: Color = c["skin"]
		# body
		_ell(pos + Vector2(0, 38), 26, 30, c["shirt"])
		# head
		draw_circle(pos, 22, skin)
		draw_circle(pos + Vector2(0, -10), 21, c["hair"])
		draw_circle(pos + Vector2(0, -2), 19, skin)
		draw_circle(pos + Vector2(-7, -2), 2.6, Color("222222"))
		draw_circle(pos + Vector2(7, -2), 2.6, Color("222222"))
		var frac: float = float(c["pat"]) / float(c["max"])
		var mood := 1.0 if (st == "happy") else (-1.0 if (st == "angry") else (frac - 0.45) * 2.0)
		if mood > 0.15:
			draw_arc(pos + Vector2(0, 5), 8, 0.3, PI - 0.3, 8, Color("7a1f1f"), 2.5)
		elif mood < -0.15:
			draw_arc(pos + Vector2(0, 16), 8, PI + 0.3, TAU - 0.3, 8, Color("7a1f1f"), 2.5)
			draw_line(pos + Vector2(-11, -9), pos + Vector2(-3, -6), Color("333333"), 2.5)
			draw_line(pos + Vector2(11, -9), pos + Vector2(3, -6), Color("333333"), 2.5)
		else:
			draw_line(pos + Vector2(-6, 11), pos + Vector2(6, 11), Color("7a1f1f"), 2.5)
		if st == "happy":
			_txt("<3", pos + Vector2(14, -34), 22, C_BAD)
		elif st == "angry":
			_txt("!!", pos + Vector2(14, -34), 24, C_BAD)
		# order bubble
		if st == "wait":
			var br := Rect2(pos.x - 54, pos.y + 56, 108, 88)
			var urgent := frac < 0.3
			var pulse := 1.0 + (sin(t_global * 12.0) * 0.04 if urgent else 0.0)
			_rr(br.grow(pulse * 2.0 - 2.0), Color("ffffff"), 16, C_BAD if urgent else Color("cfcfe6"), 3)
			_draw_dish(c["order"], br.position + Vector2(54, 38), 24)
			var bar := Rect2(br.position + Vector2(10, 72), Vector2(88, 8))
			_rr(bar, Color(0, 0, 0, 0.25), 4)
			var col := C_GOOD.lerp(C_BAD, 1.0 - clampf(frac * 1.4, 0.0, 1.0)) if frac < 0.7 else C_GOOD
			_rr(Rect2(bar.position, Vector2(bar.size.x * clampf(frac, 0.0, 1.0), bar.size.y)), col, 4)
			if held.begins_with("dish:") and held.substr(5) == c["order"]:
				draw_arc(pos + Vector2(0, 20), 54 + sin(t_global * 8.0) * 3.0, 0, TAU, 28, Color(C_GOLD.r, C_GOLD.g, C_GOLD.b, 0.8), 3.0)


func _draw_chef_and_hud() -> void:
	var bob := sin(t_global * 14.0) * 3.0 if chef_moving else sin(t_global * 3.0) * 1.5
	_draw_chef(chef_pos, chef_face, bob)
	if held != "":
		var hp := chef_pos + Vector2(0, -62 + bob)
		_rr(Rect2(hp - Vector2(24, 24), Vector2(48, 48)), Color(1, 1, 1, 0.85), 14, Color("cfcfe6"), 2)
		_draw_item(held, hp, 15)
	# top bar
	_rr(Rect2(10, 10, 220, 52), Color(0, 0, 0, 0.35), 26)
	_coin(Vector2(36, 36), 17)
	var goals: Array = lv["goals"]
	var nxt := int(goals[2])
	for g in goals:
		if earned < int(g):
			nxt = int(g)
			break
	_txt("%d / %d" % [earned, nxt], Vector2(62, 47), 28, C_GOLD)
	var secs := int(ceil(time_left))
	var tcol := Color.WHITE if time_left > 20.0 else (C_BAD if int(t_global * 4.0) % 2 == 0 else Color.WHITE)
	_ctext("%d:%02d" % [secs / 60, secs % 60], Vector2(W / 2 + 40, 52), 44, tcol)
	_button(Rect2(W - 80, 10, 66, 52), "II", "pause", Color("6c757d"), 26)
	# star progress bar
	var bar := Rect2(10, 72, W - 20, 10)
	_rr(bar, Color(0, 0, 0, 0.4), 5)
	var gmax := float(goals[2])
	_rr(Rect2(bar.position, Vector2(bar.size.x * clampf(earned / gmax, 0.0, 1.0), bar.size.y)), C_GOLD, 5)
	for k in 3:
		var sx := bar.position.x + bar.size.x * float(goals[k]) / gmax
		_star(Vector2(sx - 8 if k == 2 else sx, 77), 11, C_GOLD if earned >= int(goals[k]) else Color("8d99ae"))
	if streak >= 2:
		_rr(Rect2(W / 2 - 150, 18, 100, 36), C_ACCENT, 18)
		_ctext("x%d" % streak, Vector2(W / 2 - 100, 46), 26)
	# messages and tutorial
	var tut := _tutorial_text()
	if message_time > 0.0:
		_rr(Rect2(W / 2 - 280, 1070, 560, 44), Color(0, 0, 0, 0.55), 22)
		_ctext(message, Vector2(W / 2, 1101), 24, C_GOLD)
	elif tut != "" and intro <= 0.0:
		_rr(Rect2(W / 2 - 300, 1070, 600, 44), Color(0, 0, 0, 0.55), 22)
		_ctext(tut, Vector2(W / 2, 1101), 24, Color("ffffff"))
	# recipe strip
	draw_rect(Rect2(0, 1120, W, 160), Color("14142a"))
	var recs: Array = lv["recipes"]
	for k in recs.size():
		var id: String = recs[k]
		var rx := 10.0 + (k % 2) * 355.0
		var ry := 1128.0 + (k / 2) * 74.0
		_rr(Rect2(rx, ry, 345, 68), C_PANEL, 14)
		_draw_dish(id, Vector2(rx + 34, ry + 34), 17)
		_txt(Data.RECIPES[id]["name"], Vector2(rx + 66, ry + 28), 20, Color.WHITE)
		_txt(Data.RECIPES[id]["steps"], Vector2(rx + 66, ry + 54), 13, Color(1, 1, 1, 0.65), HORIZONTAL_ALIGNMENT_LEFT, 270)
