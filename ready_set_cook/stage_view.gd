class_name StageView
extends Node3D
# A transparent 3D layer drawn over the 2D menus. Screens "request" a chef at a screen position every frame
# (see Main._stage_chef / _stage_bust) and this node places real 3D models there.
# Orthographic camera: 1 world unit = 160 canvas px, so screen positions map 1:1.

const UNIT := 160.0

var cam: Camera3D
var t := 0.0
var items := {}      # id -> {node, look_key, kind, stamp}
var reqs := {}       # id -> request dict
var vp: SubViewport
var canvas_scale := 1.0


func _ready() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_CLEAR_COLOR
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.95, 0.95, 1.0)
	e.ambient_light_energy = 0.5
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.tonemap_exposure = 0.8
	e.adjustment_enabled = true
	e.adjustment_contrast = 1.12
	env.environment = e
	add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-40, -25, 0)
	sun.light_energy = 0.8
	sun.light_color = Color(1.0, 0.96, 0.88)
	add_child(sun)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-20, 150, 0)
	fill.light_energy = 0.3
	fill.light_color = Color(0.75, 0.82, 1.0)
	add_child(fill)
	cam = Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = 720.0 / UNIT
	cam.near = 0.1
	cam.far = 60.0
	add_child(cam)
	cam.look_at_from_position(Vector3(0, 2.2, 14.0), Vector3(0, 0.0, 0), Vector3.UP)


# kind: "chef" or "bust"; anim: idle / dance / run / turn
func request(id: String, kind: String, look: Dictionary, pos: Vector2, scale_f: float, anim: String = "idle", face: String = "happy") -> void:
	reqs[id] = {"kind": kind, "look": look, "pos": pos, "scale": scale_f, "anim": anim, "face": face, "stamp": Engine.get_frames_drawn()}


func _screen_to_world(p: Vector2) -> Vector3:
	var q := p / canvas_scale
	var o := cam.project_ray_origin(q)
	var d := cam.project_ray_normal(q)
	if absf(d.z) < 0.0001:
		return Vector3.ZERO
	var k := -o.z / d.z
	return o + d * k


func _look_key(look: Dictionary) -> String:
	return str(look)


func _process(delta: float) -> void:
	t += delta
	var now := Engine.get_frames_drawn()
	# drop whatever wasn't requested recently
	for id in items.keys():
		var r: Dictionary = reqs.get(id, {})
		if r.is_empty() or now - int(r["stamp"]) > 3:
			(items[id]["node"] as Node3D).queue_free()
			items.erase(id)
			reqs.erase(id)
	for id in reqs:
		var r: Dictionary = reqs[id]
		var lk := _look_key(r["look"]) + str(r["kind"])
		var it: Dictionary = items.get(id, {})
		if it.is_empty() or it["look_key"] != lk:
			if not it.is_empty():
				(it["node"] as Node3D).queue_free()
			var n: Node3D = Models.chef(r["look"])
			if str(r["kind"]) == "bust":
				_make_bust(n)
			add_child(n)
			it = {"node": n, "look_key": lk, "face": ""}
			items[id] = it
		_place(it, r)


func _make_bust(n: Node3D) -> void:
	for nm in ["foot_l", "foot_r", "leg_l", "leg_r"]:
		(n.get_node(nm) as Node3D).visible = false
	if n.has_meta("kay"):
		for lg in n.get_node("model").find_children("*Leg*", "MeshInstance3D"):
			lg.visible = false
		return
	var body: Node3D = n.get_node("body")
	body.get_node("arm_l").visible = false
	body.get_node("arm_r").visible = false
	body.scale = Vector3(1.05, 0.5, 1.05)
	body.position = Vector3(0, 0.82, 0)


func _place(it: Dictionary, r: Dictionary) -> void:
	var n: Node3D = it["node"]
	var pos: Vector2 = r["pos"]
	var sc: float = r["scale"]
	var anim: String = r["anim"]
	var wp := _screen_to_world(pos)
	var bust := str(r["kind"]) == "bust"
	var bounce := 0.0
	var yaw := 0.0
	var swing := 0.0
	match anim:
		"dance":
			bounce = absf(sin(t * 4.0 + pos.x * 0.01)) * 0.18
			swing = sin(t * 8.0 + pos.x * 0.01)
			yaw = sin(t * 2.0 + pos.x * 0.01) * 0.35
		"run":
			bounce = absf(sin(t * 14.0)) * 0.08
			swing = sin(t * 14.0)
			yaw = 0.0
		"turn":
			yaw = sin(t * 0.9) * 0.9
			bounce = sin(t * 3.0) * 0.015
		_:
			bounce = sin(t * 3.0 + pos.x * 0.01) * 0.02
			yaw = sin(t * 0.7 + pos.x * 0.02) * 0.25
	n.scale = Vector3.ONE * sc
	if bust:
		# the head (y = 1.1) sits on the requested point
		n.position = wp - Vector3(0, 1.24 * sc, 0) + Vector3(0, bounce * sc * 0.5 - 0.22 * sc, 0)
		n.rotation.y = yaw * 0.7
	else:
		n.position = wp + Vector3(0, bounce * sc, 0)
		n.rotation.y = yaw
	var body: Node3D = n.get_node("body")
	var head: Node3D = n.get_node("head")
	if n.has_meta("kay"):
		Models.kay_play(n, "Running_A" if anim == "run" else ("Idle_B" if anim == "dance" else "Idle_A"), 1.0)
	if not bust:
		(body.get_node("arm_l") as Node3D).rotation.x = swing * 0.9 if anim != "dance" else -2.4 - swing * 0.4
		(body.get_node("arm_r") as Node3D).rotation.x = -swing * 0.9 if anim != "dance" else -2.4 + swing * 0.4
		(n.get_node("foot_l") as Node3D).position = Vector3(-0.12, 0.06 + maxf(0.0, swing) * 0.1, 0.03 + swing * 0.12 * (1.0 if anim == "run" else 0.0))
		(n.get_node("foot_r") as Node3D).position = Vector3(0.12, 0.06 + maxf(0.0, -swing) * 0.1, 0.03 - swing * 0.12 * (1.0 if anim == "run" else 0.0))
		body.rotation.x = 0.2 if anim == "run" else 0.0
	head.rotation.z = sin(t * 2.0 + pos.y) * 0.04
	var fk: String = str(r["face"]) + str(fmod(t, 3.6) > 3.45)
	if fk != it["face"] and not n.has_meta("kay"):
		it["face"] = fk
		var blink := fmod(t, 3.6) > 3.45
		var eyes := "eyes_closed" if blink else "eyes_open"
		var mouth := "mouth_smile"
		if str(r["face"]) == "happy":
			eyes = "eyes_closed" if blink else "eyes_happy"
			mouth = "mouth_grin"
		(head.get_node("eyes") as Sprite3D).texture = load("res://art/%s.svg" % eyes)
		(head.get_node("mouth") as Sprite3D).texture = load("res://art/%s.svg" % mouth)
		(head.get_node("eyes") as Sprite3D).pixel_size = 0.42 / float((head.get_node("eyes") as Sprite3D).texture.get_width())
		(head.get_node("mouth") as Sprite3D).pixel_size = 0.14 / float((head.get_node("mouth") as Sprite3D).texture.get_width())
	(n.get_node("held") as Node3D).visible = false
