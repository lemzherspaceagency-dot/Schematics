class_name HudLayer
extends DrawKit
# Everything that must NOT be tilted with the kitchen: HUD, intro, banners, pause / recipe book,
# flying coins, the vignette and the screen fade. Draws on top of main.gd's canvas.

var g: GameSim


func _ready() -> void:
	_init_fonts()


func _draw() -> void:
	buttons = []
	t_global = g.t_global
	state_t = g.state_t
	mouse_down = g.mouse_down
	hud_bump = g.hud_bump
	if g.state == GameSim.S.PLAY or g.state == GameSim.S.PAUSE:
		if g.view != null:
			_draw_world_overlays()
		_draw_fx_lists(g.particles, g.popups)
		_draw_hud()
		if g.intro > 0.0 and g.state == GameSim.S.PLAY:
			_draw_intro()
		elif g.banner_t > 0.0:
			var k := _ease_back((1.4 - g.banner_t) / 0.35)
			var a := clampf(g.banner_t * 2.0, 0.0, 1.0)
			_xf_about(Vector2(W / 2, 360), k, k)
			_ctext(g.banner, Vector2(W / 2, 360), 120, Color(C_GOLD.r, C_GOLD.g, C_GOLD.b, a))
			_xf_reset()
		if g.state == GameSim.S.PAUSE:
			_draw_pause()
	for q in g.coin_fx:
		_spr("coin", q["p"], 0.5 * (0.8 + 0.2 * sin(float(q["life"]) * 20.0)))
	_draw_grain()
	_draw_vignette()
	if g.fade > 0.0:
		draw_rect(Rect2(-20, -20, W + 40, H + 40), Color(0.12, 0.07, 0.1, g.fade))


func _ingredient_icons(id: String, c: Vector2, size: float, gap: float) -> void:
	var items: Array = (Data.RECIPES[id]["items"] as Array).duplicate()
	items.sort()
	for i in items.size():
		_draw_item(items[i], c + Vector2(i * gap, 0), size)


# square orange icon button like the real game's menu / help buttons
func _icon_button(rect: Rect2, id: String, kind: String) -> void:
	_button(rect, "", id, Color("ff9f1c"), 20)
	var c := rect.get_center() + Vector2(0, -3)
	if kind == "bars":
		for i in 3:
			_rr(Rect2(c + Vector2(-13, -12 + i * 10), Vector2(26, 6)), Color.WHITE, 3, C_OUTLINE, 2)
	elif kind == "pause":
		_rr(Rect2(c + Vector2(-12, -13), Vector2(8, 26)), Color.WHITE, 3, C_OUTLINE, 2)
		_rr(Rect2(c + Vector2(4, -13), Vector2(8, 26)), Color.WHITE, 3, C_OUTLINE, 2)
	else:
		_ctext("?", c + Vector2(0, 13), 38, Color.WHITE)


func _draw_hud() -> void:
	var goals := g._goals()
	var nxt := int(goals[2])
	for x in goals:
		if g.earned < int(x):
			nxt = int(x)
			break
	_icon_button(Rect2(12, 10, 56, 50), "pause", "bars")
	_icon_button(Rect2(78, 10, 56, 50), "recipes", "help")
	_spr("coin", Vector2(176, 37), 0.95 * (1.0 + g.hud_bump * 0.3))
	_txt("%d / %d" % [int(round(g.earned_shown)), nxt], Vector2(204, 50), 34, Color.WHITE)
	var gmax := float(goals[2])
	var bar := Rect2(410, 28, 440, 16)
	_bar(bar, g.earned_shown / gmax, C_GOLD)
	for k in 3:
		var sx := bar.position.x + bar.size.x * float(goals[k]) / gmax
		if k == 2:
			sx -= 12.0
		var on: bool = g.earned >= int(goals[k])
		_star(Vector2(sx, 36), 17 + (3.0 * sin(t_global * 6.0) if on else 0.0), on)
	if g.streak >= 2:
		var pulse := 1.0 + 0.08 * sin(t_global * 10.0)
		_xf_about(Vector2(905, 36), pulse, pulse)
		_nine("panel", Rect2(868, 12, 74, 50), Color("ff7a3d"), 36.0, 36.0, 36.0)
		_ctext("x%d" % g.streak, Vector2(905, 48), 30)
		_xf_reset()
	var secs := int(ceil(g.time_left))
	var urgent: bool = g.time_left < 20.0
	var tcol := Color.WHITE if not urgent else (C_BAD if int(t_global * 4.0) % 2 == 0 else Color.WHITE)
	var tsc := 1.0 + (sin(t_global * 8.0) * 0.05 if urgent else 0.0)
	_xf_about(Vector2(1120, 37), tsc, tsc)
	_ctext("%d:%02d" % [secs / 60, secs % 60], Vector2(1120, 52), 40, tcol)
	_xf_reset()
	_icon_button(Rect2(1212, 10, 56, 50), "pause", "pause")
	var tut: String = g._tutorial_text()
	if tut != "" and g.intro <= 0.0:
		_nine("panel", Rect2(200, 600, 600, 48), C_DARK, 36.0, 36.0, 36.0)
		_ctext(tut, Vector2(500, 632), 22, Color.WHITE)
	# recipe cheat-sheet along the bottom
	var recs: Array = g.lv["recipes"]
	draw_rect(Rect2(0, 664, W, 56), Color("2a6ba8"))
	draw_rect(Rect2(0, 664, W, 4), Color("6fa8d8"))
	draw_rect(Rect2(0, 716, W, 4), Color("17456f"))
	for k in recs.size():
		var id: String = recs[k]
		var rx := 14.0 + k * 200.0
		var ry := 668.0
		_nine("panel", Rect2(rx, ry, 192, 48), Color("17456f"), 36.0, 36.0, 36.0)
		_draw_dish(id, Vector2(rx + 28, ry + 24), 14)
		_ingredient_icons(id, Vector2(rx + 78, ry + 24), 9, 34)


func _draw_intro() -> void:
	draw_rect(Rect2(0, 0, W, H), Color(0.1, 0.05, 0.12, 0.5))
	var elapsed: float = 3.0 - g.intro
	var idx := clampi(int(elapsed), 0, 2)
	var texts := ["READY?", "SET...", "COOK!"]
	var cols := [Color("ffffff"), C_GOLD, Color("ff5a36")]
	var local := elapsed - float(idx)
	var k := _ease_back(local / 0.4)
	var out_a := clampf((1.0 - local) * 5.0, 0.0, 1.0)
	var col: Color = cols[idx]
	col.a = out_a
	_xf_about(Vector2(W / 2, 340), k, k, sin(local * 6.0) * 0.05)
	_ctext(texts[idx], Vector2(W / 2, 370), 170, col)
	_xf_reset()
	_ctext("%s  -  Level %d: %s" % [str(Data.WORLDS[g.world]["name"]), g.cur_level + 1, str(g.lv["name"])], Vector2(W / 2, 200), 36, Color(1, 1, 1, 0.95))


func _draw_pause() -> void:
	draw_rect(Rect2(0, 0, W, H), Color(0.1, 0.05, 0.12, 0.72))
	buttons = []
	if g.show_recipes:
		_draw_recipe_book()
		return
	_ctext("PAUSED", Vector2(W / 2, 220), 110)
	_button(Rect2(W / 2 - 190, 270, 380, 100), "RESUME", "resume", Color("ff6b3d"), 44)
	if g.net_mode != 2:
		_button(Rect2(W / 2 - 190, 400, 380, 84), "RESTART", "restart", Color("4c8bf5"), 32)
	_button(Rect2(W / 2 - 190, 510, 380, 84), "QUIT", "levels", Color("8d99ae"), 32)


func _draw_recipe_book() -> void:
	_ctext("Recipe book", Vector2(W / 2, 80), 64)
	var recs: Array = g.lv["recipes"]
	for n in recs.size():
		var id: String = recs[n]
		var r := Rect2(100 + (n % 2) * 560, 110 + (n / 2) * 150, 520, 136)
		_panel(r, Color("c99a6b"))
		_draw_dish(id, r.position + Vector2(68, 68), 28)
		_txt("%s  (%d coins)" % [str(Data.RECIPES[id]["name"]), int(Data.RECIPES[id]["price"])], r.position + Vector2(130, 48), 28, Color.WHITE)
		_ingredient_icons(id, r.position + Vector2(160, 92), 15, 58)
		_txt(str(Data.RECIPES[id]["steps"]), r.position + Vector2(130, 126), 15, Color(1, 1, 1, 0.85), HORIZONTAL_ALIGNMENT_LEFT, 380)
	_button(Rect2(W / 2 - 150, 620, 300, 70), "BACK TO COOKING", "resume", Color("ff6b3d"), 26)


# ---------------------------------------------------------------- overlays pinned to things in the 3D kitchen

func _draw_world_overlays() -> void:
	var v: KitchenView = g.view
	# progress badges above machines
	for key in g.stations:
		var c: Vector2i = key
		var s: Dictionary = g.stations[c]
		var st: String = s["st"]
		if st == "idle":
			continue
		var kind: String = g.map[c.y][c.x]
		var sc := clampf(v.px_scale(g._cell_center(c)), 0.7, 1.3)
		var badge: Vector2 = v.station_top(c, 1.05 if kind != "O" else 1.35)
		var bsc := 1.0
		var ring := C_GOOD
		var frac := 1.0
		var rule: Dictionary = Data.RULES[kind]
		var burn: float = rule["burn"]
		if st == "working":
			frac = clampf(float(s["t"]) / g._station_time(kind), 0.0, 1.0)
			ring = Color("ffb703")
		elif st == "done":
			bsc = 1.0 + sin(t_global * 8.0) * 0.07
			if burn > 0.0:
				var left: float = burn - float(s["t"])
				frac = clampf(left / (burn - g._station_time(kind)), 0.0, 1.0)
				ring = C_GOOD.lerp(C_BAD, 1.0 - frac)
				if left < 2.5:
					badge += Vector2(sin(t_global * 60.0) * 1.8, 0)
					bsc = 1.1 + sin(t_global * 14.0) * 0.1
		elif st == "burnt":
			ring = C_BAD
			bsc = 1.0 + sin(t_global * 10.0) * 0.08
		_xf_about(badge, bsc * sc, bsc * sc)
		draw_circle(badge + Vector2(0, 2), 23, Color(0, 0, 0, 0.3))
		draw_circle(badge, 23, C_OUTLINE)
		draw_circle(badge, 20, Color.WHITE if st != "burnt" else Color("ffd0d0"))
		draw_arc(badge, 16, -PI / 2, -PI / 2 + TAU * frac, 28, ring, 4.5)
		var icon: String = s["in"] if st == "working" else s["out"]
		_draw_item(icon, badge + Vector2(0, 1), 10)
		_xf_reset()
		if st == "done" and burn > 0.0 and float(s["t"]) > burn - 2.5 and int(t_global * 6.0) % 2 == 0:
			_ctext("!", badge + Vector2(0, -28 * sc), int(36 * sc), C_BAD)
	# customers' orders
	for c in g.customers:
		if c["st"] != "wait":
			continue
		var seat: Vector2i = c["seat"]
		var cpx: Vector2 = g._customer_pos(seat)
		var t: float = c["t"]
		var bk := _ease_back((t - 0.6) / 0.4)
		if bk <= 0.0:
			continue
		var sc2 := clampf(v.px_scale(cpx), 0.7, 1.3)
		var head: Vector2 = v.project(cpx, 1.25)
		var frac: float = float(c["pat"]) / float(c["max"])
		var urgent := frac < 0.3
		var bpos: Vector2 = head + Vector2(98 * sc2 + (sin(t_global * 40.0) * 2.0 if urgent else 0.0), 8 * sc2)
		_xf_about(bpos, bk * sc2 * 0.85, bk * sc2 * 0.85)
		_spr("bubble", bpos, 1.0, -PI / 2.0, Color(1, 0.85, 0.85) if urgent else Color.WHITE)
		var dish_id: String = c["order"]
		var matches := false
		for ch in g.chefs:
			if ch.held.begins_with("dish:") and ch.held.substr(5) == dish_id:
				matches = true
		_draw_dish(dish_id, bpos + Vector2(5, -8), 20.0 + (2.0 * sin(t_global * 8.0) if matches else 0.0))
		var bar_col := C_GOOD if frac > 0.5 else (C_GOLD if frac > 0.25 else C_BAD)
		_bar(Rect2(bpos + Vector2(-32, 36), Vector2(76, 9)), frac, bar_col)
		_xf_reset()
		if matches:
			draw_arc(head + Vector2(0, 14 * sc2), 52 * sc2 + sin(t_global * 8.0) * 3.0, 0, TAU, 32, Color(C_GOLD.r, C_GOLD.g, C_GOLD.b, 0.85), 4.0)
	# who is who
	if g.chefs.size() > 1:
		for ch in g.chefs:
			var pc := Color(Data.PLAYER_COLORS[ch.id % 4])
			var lp: Vector2 = v.project(ch.pos + Vector2(0, 30))
			var label := "P%d" % (ch.id + 1) if g.net_mode == 0 else ch.name.substr(0, 8)
			_rr(Rect2(lp - Vector2(28, 11), Vector2(56, 22)), pc, 11, C_OUTLINE, 2)
			_ctext(label, lp + Vector2(0, 5), 15, Color("2a1a12"))
