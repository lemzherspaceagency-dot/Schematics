class_name KitchenView
extends Node3D
# The 3D kitchen. It never changes the game: it only looks at GameSim state every frame and moves models around.
# Kitchen coordinates: 1 tile = 1 unit, x to the right, z towards the camera, y up. Sim positions are in 2D pixels
# (64 px per tile, ORIGIN offset) and are converted with to3().

const TILE := 64.0
const ORIGIN_Y := 16.0

var g: GameSim
var vp: SubViewport
var cam: Camera3D
var sun: DirectionalLight3D
var level_root: Node3D
var dyn_root: Node3D
const CHAR := 0.9                  # chefs and customers are small next to the half-size kitchen
var round_cells := {}
var canvas_scale := 1.0              # canvas px per viewport px
var station_nodes := {}              # Vector2i -> Node3D
var plate_nodes := {}                # Vector2i -> {node, key}
var chef_nodes := {}                 # instance id -> dict
var cust_nodes := {}                 # key -> dict
var t := 0.0
var cam_base := Vector3.ZERO
var cam_target := Vector3.ZERO
var wall_mats := {}
var _blob_mat: StandardMaterial3D = null


# camera: almost straight down with a little perspective, like the real game's view
const CAM_FOV := 26.0
const CAM_PITCH := 66.0
const CAM_DIST := 20.6
const CAM_TARGET := Vector3(8.0, 0.0, 4.85)


func _ready() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color("14111c")
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.74, 0.7, 0.72)
	e.ambient_light_energy = 0.52
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.tonemap_exposure = 0.74
	e.adjustment_enabled = true
	e.adjustment_contrast = 1.22
	e.adjustment_saturation = 0.68
	e.adjustment_brightness = 0.96
	env.environment = e
	add_child(env)
	sun = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-72, -18, 0)
	sun.light_energy = 0.5
	sun.light_color = Color(1.0, 0.86, 0.66)
	sun.shadow_enabled = true
	sun.shadow_opacity = 0.65
	sun.shadow_blur = 2.2
	sun.shadow_bias = 0.05
	sun.directional_shadow_max_distance = 40.0
	add_child(sun)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-40, 160, 0)
	fill.light_energy = 0.2
	fill.light_color = Color(0.72, 0.8, 1.0)
	add_child(fill)
	cam = Camera3D.new()
	cam.fov = CAM_FOV
	cam.near = 1.0
	cam.far = 90.0
	add_child(cam)
	cam_target = CAM_TARGET
	var pitch := deg_to_rad(CAM_PITCH)
	cam_base = CAM_TARGET + Vector3(0, sin(pitch), cos(pitch)) * CAM_DIST
	cam.look_at_from_position(cam_base, cam_target, Vector3.UP)
	level_root = Node3D.new()
	level_root.name = "level"
	add_child(level_root)
	dyn_root = Node3D.new()
	dyn_root.name = "dynamic"
	add_child(dyn_root)


# ---------------------------------------------------------------- coordinate helpers

func to3(px: Vector2, h: float = 0.0) -> Vector3:
	return Vector3(px.x / TILE, h, (px.y - ORIGIN_Y) / TILE)


func from3(p: Vector3) -> Vector2:
	return Vector2(p.x * TILE, p.z * TILE + ORIGIN_Y)


# kitchen pixel position (+ height in tiles) -> canvas position (1280x720 space)
func project(px: Vector2, h: float = 0.0) -> Vector2:
	return cam.unproject_position(to3(px, h)) * canvas_scale


# canvas position -> kitchen pixel position on the floor
func unproject(canvas_pt: Vector2) -> Vector2:
	var p := canvas_pt / canvas_scale
	var o := cam.project_ray_origin(p)
	var d := cam.project_ray_normal(p)
	if absf(d.y) < 0.0001:
		return Vector2.ZERO
	var k := -o.y / d.y
	return from3(o + d * k)


# like unproject(), but prefers tall things: tapping the visible top of a counter or station picks that tile,
# not the floor hidden behind it
func pick(canvas_pt: Vector2) -> Vector2:
	var p := canvas_pt / canvas_scale
	var o := cam.project_ray_origin(p)
	var d := cam.project_ray_normal(p)
	if absf(d.y) < 0.0001:
		return Vector2.ZERO
	var hi := o + d * ((0.6 - o.y) / d.y)
	var cell := Vector2i(int(floor(hi.x)), int(floor(hi.z)))
	if cell.x >= 0 and cell.y >= 0 and cell.x < Data.COLS and cell.y < Data.ROWS:
		var kind: String = g.map[cell.y][cell.x]
		if kind in "MVDCSOABTc":
			return from3(Vector3(cell.x + 0.5, 0, cell.y + 0.5))
	# customers' heads are high: look at a plane at head height too
	var head := o + d * ((0.9 - o.y) / d.y)
	var hc := Vector2i(int(floor(head.x)), int(floor(head.z)))
	if hc.x >= 0 and hc.y >= 0 and hc.x < Data.COLS and hc.y < Data.ROWS and g.map[hc.y][hc.x] == "c":
		return from3(Vector3(hc.x + 0.5, 0, hc.y + 0.5))
	return unproject(canvas_pt)


# how many canvas px one kitchen tile is wide at this floor position
func px_scale(px: Vector2) -> float:
	var a := project(px)
	var b := project(px + Vector2(TILE, 0))
	return (b - a).length() / TILE


# ---------------------------------------------------------------- building a level

# per-world painted look: [kitchen floor kind, base, alt, dining floor kind, base, alt, wall base, wall mortar]
const LOOKS := [
	["diamond", "5d78b4", "7e98cf", "planks", "a8703a", "8f5a2c", "3f8294", "21404b"],
	["planks", "7a4a28", "5f3a1f", "carpet", "a63a3a", "7a2528", "b04a34", "4a1f18"],
	["tiles", "a99373", "7d6248", "planks", "7a4a28", "5f3a1f", "3e7a62", "d9b34a"],
]


func _floor_mat(world: int, dining: bool, checker: int) -> StandardMaterial3D:
	var L: Array = LOOKS[world]
	var o := 3 if dining else 0
	var kind: String = L[o]
	var tex := Textures.make(kind, Color(str(L[o + 1])), Color(str(L[o + 2])), checker)
	return Models.img_mat(tex, "f_%d_%s_%s" % [world, dining, checker], Color(0.66, 0.62, 0.6), 0.9)


func _wall_mat(world: int, h: float) -> StandardMaterial3D:
	var key := "%d_%.1f" % [world, h]
	if wall_mats.has(key):
		return wall_mats[key]
	var L: Array = LOOKS[world]
	var tex := Textures.make("bricks", Color(str(L[6])), Color(str(L[7])), world)
	var m := Models.img_mat(tex, "w_%d" % world, Color(0.88, 0.88, 0.9), 0.9).duplicate()
	m.uv1_scale = Vector3(1, h, 1)
	m.uv1_triplanar = false
	wall_mats[key] = m
	return m


func clear_level() -> void:
	round_cells.clear()
	for c in level_root.get_children():
		c.queue_free()
	for c in dyn_root.get_children():
		c.queue_free()
	station_nodes.clear()
	plate_nodes.clear()
	chef_nodes.clear()
	cust_nodes.clear()


func build_level() -> void:
	clear_level()
	var world := g.world
	var plane := PlaneMesh.new()
	plane.size = Vector2(1, 1)
	var L: Array = LOOKS[world]
	var cap_col := Color(str(L[6])).darkened(0.45).to_html(false)
	for y in Data.ROWS:
		for x in Data.COLS:
			var kind: String = g.map[y][x]
			var cpos := Vector3(x + 0.5, 0, y + 0.5)
			if kind == "#":
				var h := 2.0 if y == 0 else (0.35 if y == Data.ROWS - 1 else 1.5)
				Models.mi(level_root, Models.rbox(Vector3(1.0, h, 1.0), 0.03, 2), _wall_mat(world, h), Vector3(cpos.x, h / 2.0, cpos.z)).name = "wall"
				Models.mi(level_root, Models.rbox(Vector3(1.04, 0.1, 1.04), 0.04, 2), Models.mat(cap_col, 0.7), Vector3(cpos.x, h + 0.04, cpos.z))
				continue
			var checker := ((x * 3 + y * 5) % 4) if kind != "w" else (x + y) % 2
			var dining := kind in "wTc"
			var fl := Models.mi(level_root, plane, _floor_mat(world, dining, checker), cpos)
			fl.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			if kind == "c":
				var chair := Models.chair()
				chair.position = cpos
				var table := Vector2i(x, y)
				for t in g.chair_of:
					if g.chair_of[t] == table:
						var dv: Vector2i = (t as Vector2i) - table
						chair.rotation.y = atan2(float(dv.x), float(dv.y))
				level_root.add_child(chair)
				_blob(cpos, 0.62)
			elif Data.RULES.has(kind) or Data.CRATES.has(kind) or kind in "XABT":
				var st := Models.station(kind)
				if kind == "X":
					var rounded := _rounded_counter(x, y)
					if rounded != null:
						st = rounded
						round_cells[Vector2i(x, y)] = true
				st.position = cpos
				level_root.add_child(st)
				station_nodes[Vector2i(x, y)] = st
				_blob(cpos, 1.12)
	_grime()
	_side_walls()
	_decorate(world)
	_ambient_occlusion()
	for key in g.plates:
		plate_nodes[key] = {"node": null, "key": ""}


# a soft dark blob on the floor under a thing (the real game's "contact shadow")
func _blob(pos: Vector3, size: float) -> void:
	if _blob_mat == null:
		var grad := Gradient.new()
		grad.set_color(0, Color(0, 0, 0, 0.55))
		grad.set_color(1, Color(0, 0, 0, 0.0))
		var gt := GradientTexture2D.new()
		gt.gradient = grad
		gt.fill = GradientTexture2D.FILL_RADIAL
		gt.fill_from = Vector2(0.5, 0.5)
		gt.fill_to = Vector2(1.0, 0.5)
		gt.width = 64
		gt.height = 64
		_blob_mat = StandardMaterial3D.new()
		_blob_mat.albedo_texture = gt
		_blob_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_blob_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_blob_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	var q := PlaneMesh.new()
	q.size = Vector2(size * 1.5, size * 1.5)
	var m := MeshInstance3D.new()
	m.mesh = q
	m.material_override = _blob_mat
	m.position = Vector3(pos.x + 0.06, 0.012, pos.z + 0.08)
	m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	level_root.add_child(m)


func _decorate(world: int) -> void:
	var cols := Data.COLS
	# windows with sky glass in the north wall, pillars in between
	var sky := Gradient.new()
	sky.set_color(0, Color("bfe9ff"))
	sky.set_color(1, Color("5fb4e8"))
	var skyt := GradientTexture2D.new()
	skyt.gradient = sky
	skyt.fill_from = Vector2(0, 0)
	skyt.fill_to = Vector2(0, 1)
	skyt.width = 4
	skyt.height = 64
	var glass := StandardMaterial3D.new()
	glass.albedo_texture = skyt
	glass.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	# the pass wall: KayKit wall pieces (2 tiles wide), with open windows onto the sky
	for i in cols / 2:
		var is_win := i in [1, 3, 5]
		var piece := Models.asset("env_window" if is_win else "env_wall")
		if piece == null:
			continue
		piece.position = Vector3(1.0 + i * 2.0, 0, 1.0)
		level_root.add_child(piece)
		if is_win:
			var pane := Models.mi(level_root, PlaneMesh.new(), glass, Vector3(1.0 + i * 2.0, 1.1, 1.01), Vector3(90, 0, 0), Vector3(2.0, 1, 1.6))
			pane.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for px in [2.0, 6.0, 10.0, 14.0]:
		var pil := Models.asset("env_pillar")
		if pil != null:
			pil.position = Vector3(px, 0, 1.12)
			level_root.add_child(pil)
	# hanging lamps on long dark cords
	for lx in [4.7, 8.5, 12.3]:
		var l := Models.lamp(["ff8a5c", "ffd166", "7fd6c2"][world])
		l.position = Vector3(lx, 2.55, 3.3)
		level_root.add_child(l)
		l.get_child(1).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# a sign and a clock on the pass wall, plants, a bin of cutlery
	var clock := Models.clock()
	clock.position = Vector3(cols - 2.0, 1.5, 0.98)
	level_root.add_child(clock)
	for p in [Vector3(1.6, 0, 1.7), Vector3(cols - 1.6, 0, 1.7)]:
		var plant := Models.plant()
		plant.position = p
		level_root.add_child(plant)
		_blob(p, 0.6)
	var shelf := Models.shelf()
	shelf.position = Vector3(1.0, 1.4, 6.0)
	shelf.rotation_degrees = Vector3(0, 90, 0)
	level_root.add_child(shelf)


# hand-painted dirt: stains, spills, scratches and doodles so nothing looks factory fresh
func _decal(kind: String, v: int, pos: Vector3, size: float, yaw: float, alpha: float = 1.0) -> void:
	var m := StandardMaterial3D.new()
	m.albedo_texture = Textures.grime(kind, v)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.albedo_color = Color(1, 1, 1, alpha)
	m.roughness = 1.0
	var p := PlaneMesh.new()
	p.size = Vector2(size, size)
	var mi_ := MeshInstance3D.new()
	mi_.mesh = p
	mi_.material_override = m
	mi_.position = pos
	mi_.rotation.y = yaw
	mi_.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	level_root.add_child(mi_)


func _grime() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 4242 + g.world * 77
	for y in Data.ROWS:
		for x in Data.COLS:
			var kind: String = g.map[y][x]
			var c := Vector3(x + 0.5, 0, y + 0.5)
			if kind == "#":
				continue
			if kind in "XCAMVDSO":
				# counter-style tops get scratches and the odd stain or doodle
				var top := Models.TOP + 0.012
				if kind in "MVD":
					continue
				if kind in "XCA" and not round_cells.has(Vector2i(x, y)):
					_decal("tan", rng.randi() % 3, Vector3(c.x, top - 0.002, c.z), 0.98, 0.0)
				_decal("scratch", rng.randi() % 4, Vector3(c.x, top, c.z), 0.95, rng.randf() * TAU, 0.9)
				if kind == "X" and rng.randf() < 0.55:
					_decal("squiggle" if rng.randf() < 0.5 else "stain", rng.randi() % 3, Vector3(c.x + rng.randf_range(-0.1, 0.1), top + 0.002, c.z), 0.8, rng.randf() * TAU)
				if kind == "C":
					_decal("cut", rng.randi() % 2, Vector3(c.x, top + 0.07, c.z), 0.62, 0.0)
				continue
			# floor
			var r := rng.randf()
			var kitchen := kind in ".M"
			if r < 0.3:
				_decal("stain", rng.randi() % 4, Vector3(c.x, 0.014, c.z), rng.randf_range(0.7, 1.3), rng.randf() * TAU, 0.8)
			elif r < 0.42 and kitchen:
				_decal("spill", rng.randi() % 3, Vector3(c.x, 0.016, c.z), rng.randf_range(0.6, 1.0), rng.randf() * TAU)
			elif r < 0.62:
				_decal("scuff", rng.randi() % 3, Vector3(c.x, 0.015, c.z), 1.0, rng.randf() * TAU)
			if rng.randf() < 0.35:
				_decal("dirt", rng.randi() % 3, Vector3(c.x, 0.017, c.z), 1.0, rng.randf() * TAU, 0.8)


# counters that end (or turn a corner) get a rounded shape, like the curved counters in the real game
func _rounded_counter(x: int, y: int) -> Node3D:
	var dirs := [Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0), Vector2i(0, -1)]
	var solid: Array = []
	for d in dirs:
		var c: Vector2i = Vector2i(x, y) + (d as Vector2i)
		if c.x < 0 or c.y < 0 or c.x >= Data.COLS or c.y >= Data.ROWS:
			return null
		var ch: String = g.map[c.y][c.x]
		if ch == "#":
			return null
		solid.append(ch in "XCSOAMVDB")
	var n := 0
	for s in solid:
		if s:
			n += 1
	# yaw so the neighbour (end) or neighbours (corner) land on +x (+z)
	if n == 1:
		for i in 4:
			if solid[i]:
				# direction i rotated onto +x: dirs go +x, +z, -x, -z
				return Models.counter_round("end", [0.0, 90.0, 180.0, 270.0][i])
	if n == 2:
		for i in 4:
			if solid[i] and solid[(i + 1) % 4]:
				return Models.counter_round("corner", [0.0, 90.0, 180.0, 270.0][i])
	return null


# KayKit wall pieces on the inner face of the left and right walls
func _side_walls() -> void:
	for side in 2:
		for i in 4:
			var piece := Models.asset("env_window" if i == 1 else "env_wall")
			if piece == null:
				continue
			var left := side == 0
			piece.position = Vector3(0.9 if left else Data.COLS - 0.9, 0, 2.0 + i * 2.0)
			piece.rotation_degrees = Vector3(0, 90 if left else -90, 0)
			level_root.add_child(piece)


func _ambient_occlusion() -> void:
	# soft dark gradients where walls meet the floor
	var grad := Gradient.new()
	grad.set_color(0, Color(0, 0, 0, 0.5))
	grad.set_color(1, Color(0, 0, 0, 0.0))
	var gt := GradientTexture2D.new()
	gt.gradient = grad
	gt.fill_from = Vector2(0, 0)
	gt.fill_to = Vector2(0, 1)
	gt.width = 4
	gt.height = 32
	var m := StandardMaterial3D.new()
	m.albedo_texture = gt
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	var quad := PlaneMesh.new()
	quad.size = Vector2(1, 1)
	var w := float(Data.COLS)
	var h := float(Data.ROWS)
	_ao_strip(quad, m, Vector3(w / 2.0, 0.013, 1.5), Vector2(w - 2.0, 1.0), 0.0)
	_ao_strip(quad, m, Vector3(1.5, 0.013, h / 2.0), Vector2(1.0, h - 2.0), 90.0)
	_ao_strip(quad, m, Vector3(w - 1.5, 0.013, h / 2.0), Vector2(1.0, h - 2.0), -90.0)
	_ao_strip(quad, m, Vector3(w / 2.0, 0.013, h - 1.5), Vector2(w - 2.0, 1.0), 180.0)


func _ao_strip(mesh: Mesh, m: Material, pos: Vector3, size: Vector2, yaw: float) -> void:
	var n := MeshInstance3D.new()
	n.mesh = mesh
	n.material_override = m
	n.position = pos
	n.rotation_degrees = Vector3(0, yaw, 0)
	n.scale = Vector3(size.x, 1, size.y)
	n.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	level_root.add_child(n)


# ====================================================================
# Per-frame sync
# ====================================================================

func _process(delta: float) -> void:
	if g == null or not visible:
		return
	t += delta
	_fit_viewport()
	_sync_camera()
	_sync_stations(delta)
	_sync_chefs(delta)
	_sync_customers(delta)


func _fit_viewport() -> void:
	if vp == null:
		return
	canvas_scale = 1280.0 / float(maxi(1, vp.size.x))


func _sync_camera() -> void:
	var sh: float = g.shake * 0.02
	var off := Vector3(randf_range(-1, 1), randf_range(-1, 1), 0) * sh if g.shake > 0.0 else Vector3.ZERO
	cam.look_at_from_position(cam_base + off, cam_target + off, Vector3.UP)


func _set_slot_item(slot: Node3D, id: String, as_dish: bool, scale_f: float = 1.0) -> void:
	for c in slot.get_children():
		c.queue_free()
	if id == "":
		return
	var m: Node3D = Models.dish(id) if as_dish else Models.item(id)
	m.scale = Vector3.ONE * scale_f
	slot.add_child(m)


func _sync_stations(delta: float) -> void:
	for key in g.stations:
		var c: Vector2i = key
		var node: Node3D = station_nodes.get(c)
		if node == null:
			continue
		var s: Dictionary = g.stations[c]
		var kind: String = g.map[c.y][c.x]
		var st: String = s["st"]
		var k := 0.0
		if g.pops.has(c):
			k = sin(float(g.pops[c]) / 0.3 * PI) * 0.12
		node.scale = Vector3(1.0 + k, 1.0 - k, 1.0 + k)
		match kind:
			"S":
				var pot: Node3D = node.get_node_or_null("pot")
				var flames: Node3D = node.get_node_or_null("flames")
				if pot != null:
					pot.visible = st != "idle"
					if not pot.has_meta("y0"):
						pot.set_meta("y0", pot.position.y)
					pot.position.y = float(pot.get_meta("y0")) + (sin(t * 25.0) * 0.004 if st == "working" else 0.0)
				if flames != null:
					flames.visible = st != "idle"
					if flames.visible:
						for i in 8:
							var f: Node3D = flames.get_node_or_null("flame%d" % i)
							if f != null:
								f.scale = Vector3(1, 0.8 + sin(t * 18.0 + i * 1.7) * 0.3, 1)
			"O":
				var glow: Node3D = node.get_node_or_null("glow")
				if glow != null:
					glow.visible = st != "idle" and st != "burnt"
			"C":
				var slot: Node3D = node.get_node_or_null("slot_live")
				if slot == null:
					slot = Models.node(node, "slot_live", Vector3(0.1, Models.TOP + 0.08, -0.02))
					slot.set_meta("key", "")
				var want := ""
				if st == "working":
					want = str(s["in"])
				elif st != "idle":
					want = str(s["out"])
				if str(slot.get_meta("key")) != want:
					slot.set_meta("key", want)
					_set_slot_item(slot, want, false, 0.9)
				slot.position.y = Models.TOP + 0.08 + (sin(t * 45.0) * 0.012 if st == "working" else 0.0)
	# plates
	for key in g.plates:
		var pc: Vector2i = key
		var items: Array = g.plates[pc]
		var pkey := str(items)
		var info: Dictionary = plate_nodes.get(pc, {"node": null, "key": ""})
		if info["key"] != pkey:
			info["key"] = pkey
			if info["node"] != null:
				(info["node"] as Node3D).queue_free()
				info["node"] = null
			if not items.is_empty():
				var holder := Node3D.new()
				holder.position = Vector3(pc.x + 0.5, Models.TOP + 0.02, pc.y + 0.5)
				level_root.add_child(holder)
				var did: String = g._recipe_for(items)
				if did != "":
					holder.add_child(Models.dish(did))
				else:
					for i in items.size():
						var it := Models.item(str(items[i]))
						it.position = Vector3(-0.15 + i * 0.15, 0.03, (i % 2) * 0.08 - 0.04)
						it.scale = Vector3.ONE * 0.8
						holder.add_child(it)
				info["node"] = holder
			plate_nodes[pc] = info
		if info["node"] != null:
			var hn: Node3D = info["node"]
			if g._recipe_for(items) != "":
				hn.rotation.y = t * 0.8
				hn.position.y = Models.TOP + 0.02 + sin(t * 4.0) * 0.012


func _chef_entry(ch: Chef) -> Dictionary:
	var id := ch.get_instance_id()
	if chef_nodes.has(id):
		return chef_nodes[id]
	var n := Models.chef(ch.look)
	dyn_root.add_child(n)
	var ring := Models.mi(n, Models.torus(0.34, 0.42), Models.mat(str(Data.PLAYER_COLORS[ch.id % 4]), 0.4, 0.0, 1.2), Vector3(0, 0.01, 0), Vector3.ZERO, Vector3(1, 0.2, 1))
	ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	ring.visible = g.chefs.size() > 1
	var e := {"node": n, "yaw": 0.0, "held": "", "face": ""}
	chef_nodes[id] = e
	return e


func _sync_chefs(delta: float) -> void:
	var alive := {}
	for ch in g.chefs:
		alive[ch.get_instance_id()] = true
		var e := _chef_entry(ch)
		var n: Node3D = e["node"]
		n.position = to3(ch.pos)
		var spd := ch.vel.length()
		var yaw: float = e["yaw"]
		var target_yaw := 0.0
		if spd > 25.0:
			target_yaw = atan2(ch.vel.x, ch.vel.y)
		yaw = lerp_angle(yaw, target_yaw, 1.0 - exp(-12.0 * delta))
		e["yaw"] = yaw
		n.rotation.y = yaw
		n.scale = Vector3(1.0 - ch.sq * 0.5, 1.0 + ch.sq, 1.0 - ch.sq * 0.5) * CHAR
		var body: Node3D = n.get_node("body")
		var head: Node3D = n.get_node("head")
		var swing := sin(ch.walk) if spd > 25.0 else 0.0
		if n.has_meta("kay"):
			Models.kay_play(n, "Running_A" if spd > 25.0 else "Idle_A", clampf(spd / 170.0, 0.7, 1.5) if spd > 25.0 else 1.0)
		(body.get_node("arm_l") as Node3D).rotation.x = swing * 0.9
		(body.get_node("arm_r") as Node3D).rotation.x = -swing * 0.9
		(n.get_node("foot_l") as Node3D).position = Vector3(-0.12, 0.06 + maxf(0.0, swing) * 0.08, 0.03 + swing * 0.1)
		(n.get_node("foot_r") as Node3D).position = Vector3(0.12, 0.06 + maxf(0.0, -swing) * 0.08, 0.03 - swing * 0.1)
		var bob := absf(swing) * 0.03 if spd > 25.0 else sin(t * 3.0 + ch.id) * 0.008
		body.position.y = 0.46 + bob
		body.rotation.x = clampf(spd / 260.0, 0.0, 1.0) * 0.18
		head.position = Vector3(0, 1.24 + bob * 1.3, 0.0)
		head.rotation = Vector3(-0.2, -yaw * 0.35, clampf(ch.vel.x / 260.0, -1.0, 1.0) * -0.08 + sin(t * 2.0) * 0.015)
		var hat_n := head.get_node_or_null("hat") as Node3D
		if hat_n != null:
			hat_n.rotation.x = 0.14
			hat_n.position = Vector3(0, -0.03, -0.02)
		# face
		var blink := fmod(t + ch.id * 0.9, 3.6) > 3.45
		var face_key := "%s_%s" % [blink, ch.bump > 0.2]
		if face_key != e["face"] and not n.has_meta("kay"):
			e["face"] = face_key
			_set_face(head, "eyes_closed" if blink else ("eyes_worried" if ch.bump > 0.2 else "eyes_open"), "mouth_o" if ch.bump > 0.2 else "mouth_smile")
		# carried item floats above the head
		var held_anchor: Node3D = n.get_node("held")
		if e["held"] != ch.held:
			e["held"] = ch.held
			if n.has_meta("kay") and ch.held != "":
				Models.kay_once(n, "PickUp")
			_set_slot_item(held_anchor, ch.held.substr(5) if ch.held.begins_with("dish:") else ch.held, ch.held.begins_with("dish:"), 0.62)
		held_anchor.position.y = 1.95 + sin(t * 4.0 + ch.id) * 0.04
		held_anchor.rotation.y = t * 1.2 - yaw
		var pop := 1.0 + 0.3 * ch.held_pop
		held_anchor.scale = Vector3.ONE * pop
	for id in chef_nodes.keys():
		if not alive.has(id):
			(chef_nodes[id]["node"] as Node3D).queue_free()
			chef_nodes.erase(id)


func _set_face(head: Node3D, eyes_tex: String, mouth_tex: String) -> void:
	var eyes: Sprite3D = head.get_node("eyes")
	var mouth: Sprite3D = head.get_node("mouth")
	eyes.texture = load("res://art/%s.svg" % eyes_tex)
	mouth.texture = load("res://art/%s.svg" % mouth_tex)
	eyes.pixel_size = 0.42 / float(eyes.texture.get_width())
	mouth.pixel_size = 0.14 / float(mouth.texture.get_width())


func _back(x: float) -> float:
	var q := clampf(x, 0.0, 1.0)
	return 1.0 + 2.70158 * pow(q - 1.0, 3.0) + 1.70158 * pow(q - 1.0, 2.0)


func _cust_key(c: Dictionary) -> String:
	var seat: Vector2i = c["seat"]
	return "%d_%d_%d_%s_%s" % [seat.x, seat.y, int(c["look"]), str(c["order"]), str(c["vip"])]


func _sync_customers(delta: float) -> void:
	var alive := {}
	for c in g.customers:
		var key := _cust_key(c)
		alive[key] = true
		var e: Dictionary
		if cust_nodes.has(key):
			e = cust_nodes[key]
		else:
			var n := Models.customer(int(c["look"]), bool(c["vip"]))
			dyn_root.add_child(n)
			e = {"node": n, "face": ""}
			cust_nodes[key] = e
			if bool(c["vip"]):
				var ring := Models.mi(n, Models.torus(0.42, 0.52), Models.mat("ffd23f", 0.3, 0.0, 1.6), Vector3(0, 0.02, 0), Vector3.ZERO, Vector3(1, 0.2, 1))
				ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var n: Node3D = e["node"]
		var seat: Vector2i = c["seat"]
		var st: String = c["st"]
		var ct: float = c["t"]
		var hop := 0.0
		var scl := 1.0
		var wiggle := 0.0
		if ct < 0.6:
			scl = maxf(0.01, _back(ct / 0.5))
			hop = absf(sin(ct * 14.0)) * 0.08 * (1.0 - ct / 0.6)
		if st == "happy":
			hop = absf(sin(ct * 9.0)) * 0.14 * maxf(0.0, 1.0 - ct * 0.8)
			if ct > 0.7:
				scl = maxf(0.01, 1.0 - (ct - 0.7) / 0.5)
		elif st == "angry":
			wiggle = sin(ct * 40.0) * 0.06 * maxf(0.0, 1.0 - ct)
			if ct > 0.7:
				scl = maxf(0.01, 1.0 - (ct - 0.7) / 0.5)
		var base := to3(g._customer_pos(seat))
		var toward: Vector2i = seat - (g.chair_of.get(seat, seat) as Vector2i)
		base += Vector3(toward.x, 0, toward.y) * 0.12
		n.position = base + Vector3(0, hop, 0)
		var chair_cell: Vector2i = g.chair_of.get(seat, seat)
		var dv: Vector2i = seat - chair_cell
		n.rotation.y = atan2(float(dv.x), float(dv.y)) + wiggle
		n.scale = Vector3.ONE * scl * CHAR
		var frac: float = float(c["pat"]) / float(c["max"])
		var body: Node3D = n.get_node("body")
		body.position.y = 0.52 + sin(t * 2.2 + seat.y) * 0.008
		var head: Node3D = n.get_node("head")
		var blink := fmod(t + seat.y * 0.7, 4.0) > 3.85
		var eyes := "eyes_open"
		var mouth := "mouth_smile"
		if st == "happy":
			eyes = "eyes_happy"
			mouth = "mouth_grin"
		elif st == "angry":
			eyes = "eyes_angry"
			mouth = "mouth_frown"
		elif frac < 0.3:
			eyes = "eyes_worried"
			mouth = "mouth_frown"
		elif frac < 0.55:
			mouth = "mouth_flat"
		if blink and eyes == "eyes_open":
			eyes = "eyes_closed"
		var fk := eyes + mouth
		if n.has_meta("kay"):
			Models.kay_play(n, "Hit_B" if st == "angry" else ("Idle_B" if st == "happy" else "Idle_A"), 1.0)
		elif fk != e["face"]:
			e["face"] = fk
			_set_face(head, eyes, mouth)
	for key in cust_nodes.keys():
		if not alive.has(key):
			(cust_nodes[key]["node"] as Node3D).queue_free()
			cust_nodes.erase(key)


# screen anchors for HUD overlays
func station_top(cell: Vector2i, h: float = 1.15) -> Vector2:
	return cam.unproject_position(Vector3(cell.x + 0.5, h, cell.y + 0.5)) * canvas_scale
