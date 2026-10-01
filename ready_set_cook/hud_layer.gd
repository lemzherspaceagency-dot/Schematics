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
	_nine("panel", Rect2(146, 8, 226, 58), C_DARK, 36.0, 36.0, 36.0)
	_spr("coin", Vector2(176, 37), 0.95 * (1.0 + g.hud_bump * 0.3))
	_txt("%d / %d" % [int(round(g.earned_shown)), nxt], Vector2(204, 48), 30, C_GOLD)
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
	_nine("panel", Rect2(1020, 8, 180, 58), C_DARK, 36.0, 36.0, 36.0)
	_spr("wall_clock", Vector2(1054, 37), 0.34, sin(t_global * 3.0) * 0.05 if urgent else 0.0)
	_xf_about(Vector2(1130, 37), tsc, tsc)
	_ctext("%d:%02d" % [secs / 60, secs % 60], Vector2(1132, 50), 34, tcol)
	_xf_reset()
	_icon_button(Rect2(1212, 10, 56, 50), "pause", "pause")
	var tut: String = g._tutorial_text()
	if tut != "" and g.intro <= 0.0:
		_nine("panel", Rect2(200, 600, 600, 48), C_DARK, 36.0, 36.0, 36.0)
		_ctext(tut, Vector2(500, 632), 22, Color.WHITE)
	# recipe cheat-sheet along the bottom
	var recs: Array = g.lv["recipes"]
	for k in recs.size():
		var id: String = recs[k]
		var rx := 14.0 + k * 178.0
		var ry := 668.0
		_nine("panel", Rect2(rx, ry, 172, 46), Color("5a4a7a"), 36.0, 36.0, 36.0)
		_draw_dish(id, Vector2(rx + 26, ry + 23), 11)
		_ingredient_icons(id, Vector2(rx + 70, ry + 23), 9, 34)


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
