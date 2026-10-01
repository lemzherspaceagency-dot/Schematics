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
					var m := 0.5 + 0.5 * n.get_noise_2d(x * 1.2, y * 1.2)
					var k := 0.9 + 0.16 * m
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
