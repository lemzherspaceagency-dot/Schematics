class_name DrawKit
extends Node2D
# Drawing toolbox: sprites, fonts, nine-slice panels, tweening helpers, faces, chefs, particles.
# Everything is authored at 2x in art/ and drawn at 0.5, so sc = 1 means "native".

const W := 1280.0
const H := 720.0
const TILE := 64
const ORIGIN := Vector2(0, 16)

const C_BG := Color("1b1b2f")
const C_PANEL := Color("2b2d4a")
const C_ACCENT := Color("ff7b54")
const C_GOLD := Color("ffd166")
const C_GOOD := Color("7bd389")
const C_BAD := Color("ef476f")
const C_OUTLINE := Color("3b2618")
const C_DARK := Color("3a2a4e")

var font: Font
var tex_cache := {}
var style_cache := {}
var xf := Transform2D.IDENTITY

var t_global := 0.0
var state_t := 0.0                 # seconds since the current screen appeared
var buttons: Array = []
var mouse_down := false

var particles: Array = []
var popups: Array = []
var hud_bump := 0.0
var coin_fx: Array = []             # screen-space coins flying to the HUD
var shake := 0.0


func _init_fonts() -> void:
	var base: Font = load("res://fonts/Fredoka.ttf")
	var fv := FontVariation.new()
	fv.base_font = base
	var ts := TextServerManager.get_primary_interface()
	if ts != null:
		fv.variation_opentype = {ts.name_to_tag("weight"): 700}
	font = fv


func _tex(tex_name: String) -> Texture2D:
	if not tex_cache.has(tex_name):
		tex_cache[tex_name] = load("res://art/%s.svg" % tex_name)
	return tex_cache[tex_name]


# ---------------------------------------------------------------- sprites

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


func _dark_panel(r: Rect2) -> void:
	_nine("panel", r, C_DARK, 36.0, 36.0, 36.0)


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


# ---------------------------------------------------------------- text

func _txt(s: String, pos: Vector2, size: int, col: Color = Color.WHITE, align: int = HORIZONTAL_ALIGNMENT_LEFT, w: float = -1.0) -> void:
	var ol := maxi(3, size / 5)
	draw_string(font, pos + Vector2(0, maxf(2.0, size / 14.0)), s, align, w, size, Color(0, 0, 0, 0.3))
	draw_string_outline(font, pos, s, align, w, size, ol, C_OUTLINE)
	draw_string(font, pos, s, align, w, size, col)


func _ctext(s: String, center: Vector2, size: int, col: Color = Color.WHITE) -> void:
	_txt(s, Vector2(center.x - 600.0, center.y), size, col, HORIZONTAL_ALIGNMENT_CENTER, 1200.0)


func _rtext(s: String, right: Vector2, size: int, col: Color = Color.WHITE) -> void:
	_txt(s, Vector2(right.x - 1200.0, right.y), size, col, HORIZONTAL_ALIGNMENT_RIGHT, 1200.0)


# ---------------------------------------------------------------- transforms and easing

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


# ---------------------------------------------------------------- shapes

func _ell(c: Vector2, rx: float, ry: float, col: Color) -> void:
	draw_set_transform_matrix(xf * Transform2D(Vector2(1.0, 0.0), Vector2(0.0, ry / rx), c))
	draw_circle(Vector2.ZERO, rx, col)
	draw_set_transform_matrix(xf)


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
	if enabled:
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


# small round arrow button used by the customiser / player slots
func _arrow_button(c: Vector2, left: bool, id: String, enabled: bool = true) -> void:
	var rect := Rect2(c - Vector2(24, 24), Vector2(48, 48))
	if enabled:
		buttons.append({"rect": rect, "id": id})
	var hover := rect.has_point(get_local_mouse_position()) and enabled
	var sc := 1.1 if hover else 1.0
	_xf_about(c, sc, sc)
	draw_circle(c + Vector2(0, 3), 24, Color(0, 0, 0, 0.3))
	draw_circle(c, 24, C_OUTLINE)
	draw_circle(c, 21, Color("ffd166") if enabled else Color("8a8da6"))
	var d := -1.0 if left else 1.0
	draw_colored_polygon(PackedVector2Array([c + Vector2(-7 * d, -11), c + Vector2(-7 * d, 11), c + Vector2(9 * d, 0)]), C_OUTLINE)
	_xf_reset()


# ---------------------------------------------------------------- food art

func _draw_item(id: String, c: Vector2, s: float) -> void:
	if id.begins_with("dish:"):
		_draw_dish(id.substr(5), c, s)
		return
	_spr("item_" + id, c, s / 22.0)


func _draw_dish(id: String, c: Vector2, s: float) -> void:
	_spr("dish_" + id, c, s / 22.0)


# ---------------------------------------------------------------- faces

# c = centre of the head; mood -1 angry .. 0 flat .. 1 happy; spacing*size = eye offset
func _draw_face(c: Vector2, look: float, mood: float, blink: float, spacing: float = 9.0, size: float = 1.0) -> void:
	var ink := Color("2a1a12")
	for sx in [-1.0, 1.0]:
		var e: Vector2 = c + Vector2(sx * spacing * size + look * 2.0, -1.0 * size)
		if mood > 0.85:
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


# ---------------------------------------------------------------- chefs

func _look_color(list: Array, idx: int) -> Color:
	return Color(str(list[clampi(idx, 0, list.size() - 1)]))


# Head only: skin, blush, face, accessory and hat. hc = centre of the head circle, hs = head sprite scale.
func _draw_head_look(look: Dictionary, hc: Vector2, hs: float, lookx: float, mood: float, blink: float) -> void:
	var skin := _look_color(Data.SKINS, int(look.get("skin", 0)))
	var sprite_c := hc - Vector2(0, 8.0 * 0.5 * hs)
	_spr("chef_skin", sprite_c, hs, 0.0, skin)
	_spr("chef_blush", sprite_c, hs)
	_draw_face(hc, lookx, mood, blink, 9.0, hs)
	var acc: String = Data.ACCS[clampi(int(look.get("acc", 0)), 0, Data.ACCS.size() - 1)]
	if acc != "none":
		_spr("acc_" + acc, sprite_c, hs)
	var hat: String = Data.HATS[clampi(int(look.get("hat", 0)), 0, Data.HATS.size() - 1)]
	_spr("hat_" + hat, hc + Vector2(0, -70.0 * 0.5 * hs), hs, 0.0, _look_color(Data.COLORS, int(look.get("hat_col", 0))))


func _draw_head_icon(look: Dictionary, c: Vector2, size: float) -> void:
	# round avatar used in lists: size is the circle radius in pixels
	draw_circle(c, size + 4, C_OUTLINE)
	draw_circle(c, size, Color("9bd1ff"))
	var hs := size / 36.0
	_draw_head_look(look, c + Vector2(0, size * 0.34), hs, 0.0, 0.8, 1.0)


# c = tile centre; feet sit ~24px below it. Squash/lean pivot around the feet.
func _draw_chef_look(look: Dictionary, c: Vector2, face: float, bob: float, scale_f: float, lean: float, sq: float, phase: float, mood: float, vel_x: float, running: bool) -> void:
	var feet := c + Vector2(0, 24 * scale_f)
	var cs := 0.7 * scale_f
	_xf_set(Transform2D(Vector2(1, 0), Vector2(0, 0.32), feet + Vector2(0, 1)))
	draw_circle(Vector2.ZERO, 24 * scale_f, Color(0, 0, 0, 0.3))
	var t := Transform2D(lean, Vector2(cs * (1.0 - sq * 0.5), cs * (1.0 + sq)), 0.0, feet)
	_xf_set(t)
	var step := sin(phase)
	var up := (-absf(step) * 3.0 if running else 0.0) + bob
	var skin := _look_color(Data.SKINS, int(look.get("skin", 0)))
	var shoe := Color("4a4f7a")
	_spr("shoe", Vector2(-14, -8 - maxf(0.0, step) * 8.0), 1.4, 0.0, shoe)
	_spr("shoe", Vector2(14, -8 - maxf(0.0, -step) * 8.0), 1.4, 0.0, shoe)
	var body_c := Vector2(0, -34 + up * 0.6)
	_spr("chef_jacket", body_c, 1.5, 0.0, _look_color(Data.COLORS, int(look.get("jacket", 0))))
	_spr("chef_jacket_line", body_c, 1.5)
	_spr("chef_apron", body_c, 1.5, 0.0, _look_color(Data.COLORS, int(look.get("apron", 0))))
	_spr("chef_scarf", body_c, 1.5, 0.0, _look_color(Data.COLORS, int(look.get("scarf", 0))))
	_spr("hand", Vector2(-40, -26 + step * 7.0 + up * 0.6), 1.4, 0.0, skin)
	_spr("hand", Vector2(40, -26 - step * 7.0 + up * 0.6), 1.4, 0.0, skin)
	# head lags behind the body a little for a bouncy feel
	var head_tilt := clampf(vel_x / 260.0, -1.0, 1.0) * 0.1 + sin(t_global * 2.0) * 0.015
	_xf_set(t * Transform2D(head_tilt, Vector2.ONE, 0.0, Vector2.ZERO))
	var blink := 0.15 if fmod(t_global, 3.6) > 3.45 else 1.0
	_draw_head_look(look, Vector2(0, -92 + up), 1.5, face, mood, blink)
	_xf_reset()


# ---------------------------------------------------------------- fx

func _burst(p: Vector2, col: Color, n: int, speed: float) -> void:
	p = _project(p) + (Vector2(0, -34) if _tilted() else Vector2.ZERO)
	for i in n:
		var a := randf() * TAU
		var v := Vector2(cos(a), sin(a)) * randf_range(0.3, 1.0) * speed
		particles.append({"p": p, "v": v, "g": 260.0, "life": 0.7, "max": 0.7, "col": col, "r": randf_range(4, 8), "tex": "spark"})


func _puff(p: Vector2, col: Color) -> void:
	p = _project(p) + (Vector2(0, -50) if _tilted() else Vector2.ZERO)
	particles.append({"p": p, "v": Vector2(randf_range(-10, 10), -50), "g": -10.0, "life": 0.9, "max": 0.9, "col": col, "r": randf_range(10, 16), "tex": "puff"})


func _popup(p: Vector2, text: String, col: Color, size: int) -> void:
	p = _project(p)
	popups.append({"p": p, "text": text, "life": 1.3, "col": col, "size": size})


# world -> screen position (main.gd overrides this when the kitchen is tilted)
func _project(p: Vector2) -> Vector2:
	return p


func _tilted() -> bool:
	return false


func _coin_fly(from: Vector2, to: Vector2, n: int) -> void:
	var start := _project(from)
	for i in n:
		var a := randf() * TAU
		coin_fx.append({"p": start, "v": Vector2(cos(a), sin(a) - 1.0) * randf_range(90, 220), "life": 1.4, "age": 0.0, "tgt": to})


func _update_fx(delta: float) -> void:
	for i in range(coin_fx.size() - 1, -1, -1):
		var q: Dictionary = coin_fx[i]
		q["life"] = float(q["life"]) - delta
		q["age"] = float(q["age"]) + delta
		if float(q["life"]) <= 0.0:
			coin_fx.remove_at(i)
			continue
		if float(q["age"]) > 0.45:
			q["p"] = Vector2(q["p"]).lerp(Vector2(q["tgt"]), 1.0 - exp(-9.0 * delta))
			if Vector2(q["p"]).distance_to(Vector2(q["tgt"])) < 22.0:
				hud_bump = 1.0
				coin_fx.remove_at(i)
		else:
			var v0: Vector2 = q["v"]
			v0.y += 500.0 * delta
			q["v"] = v0
			q["p"] = Vector2(q["p"]) + v0 * delta
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
	position = Vector2(randf_range(-1, 1), randf_range(-1, 1)) * shake if shake > 0.0 else Vector2.ZERO


func _draw_particles() -> void:
	_draw_fx_lists(particles, popups)


func _draw_fx_lists(plist: Array, ulist: Array) -> void:
	for q in plist:
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
		else:
			col.a *= a
			draw_circle(q["p"], r * (0.5 + a * 0.5), col)
	for q in ulist:
		var a: float = clampf(float(q["life"]) * 2.0, 0.0, 1.0)
		var col: Color = q["col"]
		col.a = a
		var age: float = 1.3 - float(q["life"])
		var sc := 1.0 + 0.6 * maxf(0.0, 1.0 - age * 5.0)
		_ctext(q["text"], q["p"], int(float(q["size"]) * sc), col)


func _draw_vignette() -> void:
	var c0 := Color(0, 0, 0, 0.45)
	var c1 := Color(0, 0, 0, 0)
	draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(W, 0), Vector2(W, 100), Vector2(0, 100)]), PackedColorArray([c0, c0, c1, c1]))
	draw_polygon(PackedVector2Array([Vector2(0, H - 100), Vector2(W, H - 100), Vector2(W, H), Vector2(0, H)]), PackedColorArray([c1, c1, c0, c0]))
	draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(90, 0), Vector2(90, H), Vector2(0, H)]), PackedColorArray([c0, c1, c1, c0]))
	draw_polygon(PackedVector2Array([Vector2(W - 90, 0), Vector2(W, 0), Vector2(W, H), Vector2(W - 90, H)]), PackedColorArray([c1, c0, c0, c1]))
