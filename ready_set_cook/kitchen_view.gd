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
var canvas_scale := 1.0              # canvas px per viewport px
var station_nodes := {}              # Vector2i -> Node3D
var plate_nodes := {}                # Vector2i -> {node, key}
var chef_nodes := {}                 # instance id -> dict
var cust_nodes := {}                 # key -> dict
var t := 0.0
var cam_base := Vector3.ZERO
var cam_target := Vector3.ZERO
var wall_mats := {}


func _ready() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color("14111c")
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.62, 0.66, 0.82)
	e.ambient_light_energy = 0.5
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.tonemap_exposure = 0.78
	e.adjustment_enabled = true
	e.adjustment_contrast = 1.18
	e.adjustment_saturation = 0.96
	env.environment = e
	add_child(env)
	sun = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-62, -32, 0)
	sun.light_energy = 0.95
	sun.light_color = Color(1.0, 0.86, 0.68)
	sun.shadow_enabled = true
	sun.shadow_blur = 1.6
	sun.shadow_bias = 0.04
	sun.directional_shadow_max_distance = 40.0
	add_child(sun)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-35, 150, 0)
	fill.light_energy = 0.12
	fill.light_color = Color(0.7, 0.8, 1.0)
	add_child(fill)
	cam = Camera3D.new()
	cam.fov = 35.0
	cam.near = 0.5
	cam.far = 80.0
	add_child(cam)
	cam_target = Vector3(10.0, 0.0, 5.5)
	cam_base = Vector3(10.0, 13.6, 13.0)
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
	var hi := o + d * ((0.85 - o.y) / d.y)
	var cell := Vector2i(int(floor(hi.x)), int(floor(hi.z)))
	if cell.x >= 0 and cell.y >= 0 and cell.x < Data.COLS and cell.y < Data.ROWS:
		var kind: String = g.map[cell.y][cell.x]
		if kind in "MVDCSOABT":
			return from3(Vector3(cell.x + 0.5, 0, cell.y + 0.5))
	return unproject(canvas_pt)


# how many canvas px one kitchen tile is wide at this floor position
func px_scale(px: Vector2) -> float:
	var a := project(px)
	var b := project(px + Vector2(TILE, 0))
	return (b - a).length() / TILE


# ---------------------------------------------------------------- building a level

# per-world painted look: [kitchen floor kind, base, alt, dining floor kind, base, alt, wall base, wall mortar]
const LOOKS := [
	["tiles", "6f86a6", "566b8c", "planks", "a8703a", "8f5a2c", "3f8294", "21404b"],
	["planks", "7a4a28", "5f3a1f", "carpet", "a63a3a", "7a2528", "b04a34", "4a1f18"],
	["tiles", "b79a74", "8f6a4c", "planks", "7a4a28", "5f3a1f", "3e7a62", "d9b34a"],
]


func _floor_mat(world: int, dining: bool, checker: bool) -> StandardMaterial3D:
	var L: Array = LOOKS[world]
	var o := 3 if dining else 0
	var kind: String = L[o]
	var tex := Textures.make(kind, Color(str(L[o + 1])), Color(str(L[o + 2])), 0 if checker else 1)
	return Models.img_mat(tex, "f_%d_%s_%s" % [world, dining, checker], Color(0.9, 0.9, 0.9), 0.8)


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
	for y in Data.ROWS:
		for x in Data.COLS:
			var kind: String = g.map[y][x]
			var cpos := Vector3(x + 0.5, 0, y + 0.5)
			if kind == "#":
				var h := 1.8
				if y == Data.ROWS - 1 and x < 14:
					h = 0.5
				var wall := Models.mi(level_root, Models.rbox(Vector3(1.0, h, 1.0), 0.02, 2), _wall_mat(world, h), Vector3(cpos.x, h / 2.0, cpos.z))
				wall.name = "wall"
				continue
			var checker := (x + y) % 2 == 0
			var fl := Models.mi(level_root, plane, _floor_mat(world, kind == "q", checker), cpos)
			fl.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			if Data.RULES.has(kind) or Data.CRATES.has(kind) or kind in "XABT":
				var st := Models.station(kind)
				st.position = cpos
				level_root.add_child(st)
				station_nodes[Vector2i(x, y)] = st
	# stools for the open seats
	for s in g.seats:
		var sc: Vector2i = s
		var stool := Models.stool()
		stool.position = to3(g._customer_pos(sc))
		level_root.add_child(stool)
	_decorate(world)
	_ambient_occlusion()
	for key in g.stations:
		_prep_station(key)
	for key in g.plates:
		plate_nodes[key] = {"node": null, "key": ""}


func _prep_station(key: Vector2i) -> void:
	pass


func _decorate(world: int) -> void:
	# things on the walls and in the dining room, so it feels like a place
	var xs := [3.0, 6.5, 11.0]
	for i in 3:
		var l := Models.lamp(["ff8a5c", "ffd166", "7fd6c2"][world])
		l.position = Vector3(xs[i] + 0.5, 1.28, 1.7)
		level_root.add_child(l)
		l.get_child(1).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var shelf := Models.shelf()
	shelf.position = Vector3(8.2, 1.35, 1.14)
	level_root.add_child(shelf)
	var clock := Models.clock()
	clock.position = Vector3(5.6, 1.35, 1.04)
	level_root.add_child(clock)
	var pan := Models.hanging_pan()
	pan.position = Vector3(13.0, 1.2, 1.1)
	pan.rotation_degrees = Vector3(0, 0, 0)
	level_root.add_child(pan)
	var plant := Models.plant()
	plant.position = Vector3(18.4, 0, 1.6)
	level_root.add_child(plant)
	var plant2 := Models.plant()
	plant2.position = Vector3(14.5, 0, 10.4)
	level_root.add_child(plant2)
	var table := Models.table_and_chairs()
	table.position = Vector3(17.2, 0, 10.2)
	level_root.add_child(table)


func _ambient_occlusion() -> void:
	# soft dark gradients where walls meet the floor (cheap ambient occlusion)
	var grad := Gradient.new()
	grad.set_color(0, Color(0, 0, 0, 0.42))
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
	# north wall: gradient runs from the wall (z=1) into the room
	_ao_strip(quad, m, Vector3(10.0, 0.012, 1.45), Vector2(20, 0.9), 0.0)
	_ao_strip(quad, m, Vector3(0.5 + 0.45, 0.012, 5.5), Vector2(0.9, 9.0), 90.0)
	_ao_strip(quad, m, Vector3(19.5 - 0.45, 0.012, 5.5), Vector2(0.9, 9.0), -90.0)
	_ao_strip(quad, m, Vector3(7.0, 0.012, 9.55), Vector2(14, 0.9), 180.0)
	_ao_strip(quad, m, Vector3(14.45, 0.012, 5.5), Vector2(0.9, 9.0), -90.0)


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
				var pot: Node3D = node.get_node("pot")
				var flames: Node3D = node.get_node("flames")
				pot.visible = st != "idle"
				flames.visible = st != "idle"
				pot.position.y = 0.9 + (sin(t * 25.0) * 0.004 if st == "working" else 0.0)
				if flames.visible:
					for i in 8:
						var f: Node3D = flames.get_node("flame%d" % i)
						var fl := 0.8 + sin(t * 18.0 + i * 1.7) * 0.3
						f.scale = Vector3(1, fl, 1)
			"O":
				var glow: Node3D = node.get_node("glow")
				glow.visible = st != "idle" and st != "burnt"
			"C":
				var slot: Node3D = node.get_node_or_null("slot_live")
				if slot == null:
					slot = Models.node(node, "slot_live", Vector3(0.12, 0.95, -0.02))
					slot.set_meta("key", "")
				var want := ""
				if st == "working":
					want = str(s["in"])
				elif st != "idle":
					want = str(s["out"])
				if str(slot.get_meta("key")) != want:
					slot.set_meta("key", want)
					_set_slot_item(slot, want, false, 0.9)
				slot.position.y = 0.95 + (sin(t * 45.0) * 0.012 if st == "working" else 0.0)
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
				holder.position = Vector3(pc.x + 0.5, 0.93, pc.y + 0.5)
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
				hn.position.y = 0.93 + sin(t * 4.0) * 0.012


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
		n.scale = Vector3(1.0 - ch.sq * 0.5, 1.0 + ch.sq, 1.0 - ch.sq * 0.5)
		var body: Node3D = n.get_node("body")
		var head: Node3D = n.get_node("head")
		var swing := sin(ch.walk) if spd > 25.0 else 0.0
		(body.get_node("arm_l") as Node3D).rotation.x = swing * 0.9
		(body.get_node("arm_r") as Node3D).rotation.x = -swing * 0.9
		(n.get_node("foot_l") as Node3D).position = Vector3(-0.12, 0.06 + maxf(0.0, swing) * 0.08, 0.03 + swing * 0.1)
		(n.get_node("foot_r") as Node3D).position = Vector3(0.12, 0.06 + maxf(0.0, -swing) * 0.08, 0.03 - swing * 0.1)
		var bob := absf(swing) * 0.03 if spd > 25.0 else sin(t * 3.0 + ch.id) * 0.008
		body.position.y = 0.46 + bob
		body.rotation.x = clampf(spd / 260.0, 0.0, 1.0) * 0.18
		head.position.y = 1.1 + bob * 1.3
		head.rotation = Vector3(0, -yaw * 0.35, clampf(ch.vel.x / 260.0, -1.0, 1.0) * -0.08 + sin(t * 2.0) * 0.015)
		# face
		var blink := fmod(t + ch.id * 0.9, 3.6) > 3.45
		var face_key := "%s_%s" % [blink, ch.bump > 0.2]
		if face_key != e["face"]:
			e["face"] = face_key
			_set_face(head, "eyes_closed" if blink else ("eyes_worried" if ch.bump > 0.2 else "eyes_open"), "mouth_o" if ch.bump > 0.2 else "mouth_smile")
		# carried item floats above the head
		var held_anchor: Node3D = n.get_node("held")
		if e["held"] != ch.held:
			e["held"] = ch.held
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
		var slide := 0.0
		var hop := 0.0
		var scl := 1.0
		var wiggle := 0.0
		if ct < 0.8:
			var k := 1.0 - (1.0 - clampf(ct / 0.8, 0.0, 1.0)) * (1.0 - clampf(ct / 0.8, 0.0, 1.0)) * (1.0 - clampf(ct / 0.8, 0.0, 1.0))
			slide = (1.0 - k) * 3.0
			hop = absf(sin(ct * 16.0)) * 0.1 * (1.0 - k)
		if st == "happy":
			hop = absf(sin(ct * 9.0)) * 0.16 * maxf(0.0, 1.0 - ct * 0.8)
			if ct > 0.7:
				var e2 := (ct - 0.7) / 0.5
				slide = e2 * e2 * 3.0
				scl = maxf(0.01, 1.0 - e2 * 0.9)
		elif st == "angry":
			wiggle = sin(ct * 40.0) * 0.06 * maxf(0.0, 1.0 - ct)
			if ct > 0.7:
				var e3 := (ct - 0.7) / 0.5
				slide = e3 * e3 * 3.0
				scl = maxf(0.01, 1.0 - e3 * 0.9)
		var base := to3(g._customer_pos(seat))
		n.position = base + Vector3(slide, hop, 0)
		n.rotation.y = deg_to_rad(-48.0) + wiggle
		n.scale = Vector3.ONE * scl
		var frac: float = float(c["pat"]) / float(c["max"])
		var body: Node3D = n.get_node("body")
		body.position.y = 0.68 + sin(t * 2.2 + seat.y) * 0.008
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
		if fk != e["face"]:
			e["face"] = fk
			_set_face(head, eyes, mouth)
	for key in cust_nodes.keys():
		if not alive.has(key):
			(cust_nodes[key]["node"] as Node3D).queue_free()
			cust_nodes.erase(key)


# screen anchors for HUD overlays
func station_top(cell: Vector2i, h: float = 1.15) -> Vector2:
	return cam.unproject_position(Vector3(cell.x + 0.5, h, cell.y + 0.5)) * canvas_scale
