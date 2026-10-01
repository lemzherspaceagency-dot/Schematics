class_name Textures
extends RefCounted
# Painted-looking textures generated in code (wood planks, tiles, brick, carpet) plus a grunge map
# that every model material multiplies in so flat colours get a hand-painted, worn feel.

static var _cache := {}
static var _noise: FastNoiseLite = null


static func _n() -> FastNoiseLite:
	if _noise == null:
		_noise = FastNoiseLite.new()
		_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		_noise.frequency = 0.05
		_noise.seed = 7
	return _noise


static func grunge() -> ImageTexture:
	if _cache.has("grunge"):
		return _cache["grunge"]
	var img := Image.create(128, 128, false, Image.FORMAT_RGB8)
	var n := _n()
	for y in 128:
		for x in 128:
			var v := 0.5 + 0.5 * n.get_noise_2d(x * 1.6, y * 1.6)
			var f := 0.5 + 0.5 * n.get_noise_2d(x * 4.0 + 90.0, y * 4.0)
			var k := clampf(0.74 + 0.2 * v + 0.1 * f, 0.0, 1.0)
			img.set_pixel(x, y, Color(k, k * 0.99, k * 0.97))
	img.generate_mipmaps()
	var t := ImageTexture.create_from_image(img)
	_cache["grunge"] = t
	return t


static func _shade(c: Color, k: float) -> Color:
	return Color(clampf(c.r * k, 0, 1), clampf(c.g * k, 0, 1), clampf(c.b * k, 0, 1), 1.0)


# kind: planks | tiles | bricks | carpet ; v = variant 0/1 (so neighbouring tiles differ)
static func make(kind: String, base: Color, alt: Color, v: int) -> ImageTexture:
	var key := "%s_%s_%s_%d" % [kind, base.to_html(false), alt.to_html(false), v]
	if _cache.has(key):
		return _cache[key]
	var S := 128
	var img := Image.create(S, S, false, Image.FORMAT_RGB8)
	var n := _n()
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(key)
	match kind:
		"planks":
			var plank_tone: Array = []
			var seam: Array = []
			for i in 4:
				plank_tone.append(rng.randf_range(0.82, 1.12))
				seam.append(rng.randi_range(16, 112))
			for y in S:
				var pi := y / 32
				var py := y % 32
				for x in S:
					var tone: float = plank_tone[pi]
					var grain := 0.5 + 0.5 * n.get_noise_2d(x * 0.9 + pi * 40.0 + v * 30.0, y * 7.0)
					var c := _shade(base if (pi + v) % 2 == 0 else alt, tone * (0.84 + 0.3 * grain))
					# soft darker edge on every plank
					var edge := minf(float(py), 31.0 - float(py))
					if edge < 4.0:
						c = _shade(c, 0.78 + edge * 0.05)
					if py < 2:
						c = _shade(c, 0.38)
					var sx := absi(x - int(seam[pi]))
					if sx < 2:
						c = _shade(c, 0.4)
					# scuffs
					if n.get_noise_2d(x * 3.0 + 300.0, y * 3.0 + v * 50.0) > 0.62:
						c = _shade(c, 1.22)
					img.set_pixel(x, y, c)
		"tiles":
			for y in S:
				for x in S:
					var cx := x / 64
					var cy := y / 64
					var tx := x % 64
					var ty := y % 64
					var c := base if (cx + cy + v) % 2 == 0 else alt
					var edge := minf(minf(tx, 63 - tx), minf(ty, 63 - ty))
					var m := 0.5 + 0.5 * n.get_noise_2d(x * 1.2 + v * 50.0, y * 1.2)
					var k := 0.86 + 0.22 * m
					if edge < 3.0:
						k *= 0.28 + edge * 0.08       # grout
					elif edge < 9.0:
						k *= 0.9 + (edge - 3.0) * 0.016
					# diagonal highlight, like a glazed tile
					if absf(float(tx) - float(ty) - 6.0) < 3.0 and edge > 6.0:
						k *= 1.12
					if n.get_noise_2d(x * 2.4 + 500.0, y * 2.4) > 0.6:
						k *= 0.82
					img.set_pixel(x, y, _shade(c, k))
		"diamond":
			# one diamond per tile: the corners of 4 neighbours join into the second colour
			for y in S:
				for x in S:
					var dx := absf(float(x) + 0.5 - 64.0) / 64.0
					var dy := absf(float(y) + 0.5 - 64.0) / 64.0
					var d := dx + dy
					var c := base if d < 1.0 else alt
					var edge := absf(d - 1.0) * 64.0
					var m := 0.5 + 0.5 * n.get_noise_2d(x * 1.2 + v * 70.0, y * 1.2)
					# hand-painted look: big uneven washes + brush streaks, each variant different
					var wash := 0.5 + 0.5 * n.get_noise_2d(x * 0.35 + v * 13.0, y * 0.35 + v * 7.0)
					var streak := 0.5 + 0.5 * n.get_noise_2d(x * 0.15 + v * 5.0, y * 2.6)
					var k := 0.78 + 0.16 * m + 0.2 * wash + 0.08 * streak
					if edge < 2.0:
						k *= 0.55 + edge * 0.2
					if n.get_noise_2d(x * 2.4 + 500.0, y * 2.4) > 0.62:
						k *= 0.9
					img.set_pixel(x, y, _shade(c, k))
		"bricks":
			for y in S:
				var row := y / 21
				var off := 0 if row % 2 == 0 else 20
				for x in S:
					var bx := (x + off) % 40
					var by := y % 21
					var brick_id := ((x + off) / 40) + row * 5
					var tone := 0.82 + 0.3 * float((brick_id * 37 + v * 11) % 17) / 17.0
					var c := _shade(base, tone * (0.88 + 0.2 * (0.5 + 0.5 * n.get_noise_2d(x * 1.5, y * 1.5 + v * 40.0))))
					if bx < 2 or by < 2:
						c = _shade(alt, 0.8)
					elif bx > 36 or by > 18:
						c = _shade(c, 0.78)
					if n.get_noise_2d(x * 2.2 + 700.0, y * 2.2) > 0.55:
						c = _shade(c, 1.2)
					img.set_pixel(x, y, c)
		_:   # carpet
			for y in S:
				for x in S:
					var m := 0.5 + 0.5 * n.get_noise_2d(x * 2.0 + v * 20.0, y * 2.0)
					var c := _shade(base, 0.82 + 0.3 * m)
					var dx := absi((x % 64) - 32)
					var dy := absi((y % 64) - 32)
					if dx + dy < 14:
						c = _shade(alt, 0.9 + 0.2 * m)
					elif dx + dy < 17:
						c = _shade(c, 0.6)
					img.set_pixel(x, y, c)
	img.generate_mipmaps()
	var t := ImageTexture.create_from_image(img)
	_cache[key] = t
	return t


# ---------------------------------------------------------------------------
# hand-painted dirt decals (transparent): scratches, stains, spills, scribbles, knife cuts
# ---------------------------------------------------------------------------
static func _blend(img: Image, x: int, y: int, col: Color) -> void:
	if x < 0 or y < 0 or x >= img.get_width() or y >= img.get_height():
		return
	var o := img.get_pixel(x, y)
	var a := col.a + o.a * (1.0 - col.a)
	if a <= 0.0:
		return
	var rgb := (Vector3(col.r, col.g, col.b) * col.a + Vector3(o.r, o.g, o.b) * o.a * (1.0 - col.a)) / a
	img.set_pixel(x, y, Color(rgb.x, rgb.y, rgb.z, a))


static func _line(img: Image, a: Vector2, b: Vector2, col: Color, w: float = 1.0) -> void:
	var n := int(a.distance_to(b)) + 1
	for i in n + 1:
		var p := a.lerp(b, float(i) / float(maxi(1, n)))
		for dx in range(-int(w), int(w) + 1):
			for dy in range(-int(w), int(w) + 1):
				if Vector2(dx, dy).length() <= w + 0.3:
					_blend(img, int(p.x) + dx, int(p.y) + dy, col)


static func grime(kind: String, v: int) -> ImageTexture:
	var key := "grime_%s_%d" % [kind, v]
	if _cache.has(key):
		return _cache[key]
	var S := 128
	var img := Image.create(S, S, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(key)
	var n := _n()
	var ink := Color(0.1, 0.06, 0.04, 0.75)
	match kind:
		"scratch":
			for i in rng.randi_range(4, 8):
				var p := Vector2(rng.randf_range(10, 118), rng.randf_range(10, 118))
				var d := Vector2.from_angle(rng.randf_range(0, TAU)) * rng.randf_range(8, 34)
				_line(img, p, p + d, Color(0.1, 0.06, 0.04, rng.randf_range(0.25, 0.6)), 0.6)
			for i in 14:
				_blend(img, rng.randi_range(4, 123), rng.randi_range(4, 123), Color(0.1, 0.06, 0.04, 0.6))
		"stain":
			# a coffee-ring blotch: darker rim, lighter middle
			var c := Vector2(rng.randf_range(44, 84), rng.randf_range(44, 84))
			var r := rng.randf_range(16, 34)
			for y in S:
				for x in S:
					var d := Vector2(x, y).distance_to(c)
					var wob := 1.0 + 0.28 * n.get_noise_2d(x * 2.2 + v * 31.0, y * 2.2)
					var k := d / (r * wob)
					if k < 1.0:
						var rim := smoothstep(0.55, 1.0, k)
						_blend(img, x, y, Color(0.33, 0.2, 0.1, 0.1 + rim * 0.3))
		"squiggle":
			# the little ink doodles on the real counters
			var p := Vector2(rng.randf_range(34, 94), rng.randf_range(34, 94))
			var prev := p
			var ang := rng.randf_range(0, TAU)
			for i in 40:
				ang += rng.randf_range(-0.9, 0.9) + 0.35
				var np := prev + Vector2.from_angle(ang) * 3.2
				_line(img, prev, np, ink, 0.8)
				prev = np
		"spill":
			var c := Vector2(64, 64)
			var r := rng.randf_range(22, 40)
			for y in S:
				for x in S:
					var d := Vector2(x, y).distance_to(c)
					var wob := 1.0 + 0.4 * n.get_noise_2d(x * 1.6 + v * 17.0, y * 1.6)
					if d < r * wob:
						_blend(img, x, y, Color(0.6, 0.78, 0.95, 0.38))
						if d > r * wob - 3.0:
							_blend(img, x, y, Color(0.2, 0.35, 0.55, 0.45))
			_line(img, c + Vector2(-8, -6), c + Vector2(4, -10), Color(1, 1, 1, 0.55), 1.4)
		"dirt":
			for i in 40:
				var p := Vector2(rng.randf_range(6, 122), rng.randf_range(6, 122))
				var rr := rng.randf_range(0.8, 2.6)
				for dx in range(-3, 4):
					for dy in range(-3, 4):
						if Vector2(dx, dy).length() <= rr:
							_blend(img, int(p.x) + dx, int(p.y) + dy, Color(0.12, 0.08, 0.06, rng.randf_range(0.2, 0.5)))
		"tan":
			# painted counter top: warm tan with uneven washes, a hand-drawn dark border
			for y in S:
				for x in S:
					var w := 0.5 + 0.5 * n.get_noise_2d(x * 0.4 + v * 20.0, y * 0.4)
					var s := 0.5 + 0.5 * n.get_noise_2d(x * 0.1 + v * 9.0, y * 3.0)
					var k := 0.86 + 0.18 * w + 0.08 * s
					img.set_pixel(x, y, Color(0.8 * k, 0.62 * k, 0.42 * k, 1.0))
		"scuff":
			for i in 3:
				var p := Vector2(rng.randf_range(20, 90), rng.randf_range(20, 108))
				var d := Vector2.from_angle(rng.randf_range(-0.5, 0.5)) * rng.randf_range(20, 44)
				for j in 4:
					_line(img, p + Vector2(0, j * 2.0), p + d + Vector2(0, j * 2.0), Color(0.08, 0.05, 0.04, 0.16), 0.9)
		"cut":
			# knife marks on the chopping board
			for i in 2:
				var o := Vector2(rng.randf_range(-4, 4), rng.randf_range(-4, 4))
				_line(img, Vector2(40, 38) + o, Vector2(86, 90) + o, ink, 1.4)
				_line(img, Vector2(86, 38) + o, Vector2(40, 90) + o, ink, 1.4)
	var tex := ImageTexture.create_from_image(img)
	_cache[key] = tex
	return tex
