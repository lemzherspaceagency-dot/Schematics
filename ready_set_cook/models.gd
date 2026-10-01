class_name Models
extends RefCounted
# Procedural 3D models (everything is built from rounded primitives, no model files).
# Units: 1.0 = one kitchen tile. Models stand on y = 0 and face +Z (towards the camera).

static var _mats := {}
static var _meshes := {}
static var _tex := {}
static var _outline: ShaderMaterial = null


static func outline() -> ShaderMaterial:
	if _outline == null:
		_outline = ShaderMaterial.new()
		_outline.shader = load("res://outline.gdshader")
	return _outline


# characters get clean, smooth shading (no grunge) and a slimmer ink line
static var _clean := false
static var _outline_thin: ShaderMaterial


static func outline_thin() -> ShaderMaterial:
	if _outline_thin == null:
		_outline_thin = ShaderMaterial.new()
		_outline_thin.shader = load("res://outline.gdshader")
		_outline_thin.set_shader_parameter("width", 0.014)
	return _outline_thin


static func _paint(m: StandardMaterial3D, scale: float = 3.0) -> void:
	m.detail_enabled = true
	m.detail_albedo = Textures.grunge()
	m.detail_blend_mode = BaseMaterial3D.BLEND_MODE_MUL
	m.detail_uv_layer = BaseMaterial3D.DETAIL_UV_1
	m.uv1_scale = Vector3(1, 1, 1)


# ---------------------------------------------------------------- materials & meshes

static func mat(hex: String, rough: float = 0.55, metal: float = 0.0, emit: float = 0.0) -> StandardMaterial3D:
	var key := "%s_%.2f_%.2f_%.2f%s" % [hex, rough, metal, emit, "c" if _clean else ""]
	if _mats.has(key):
		return _mats[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(hex)
	m.roughness = rough
	m.metallic = metal
	if emit > 0.0:
		m.emission_enabled = true
		m.emission = Color(hex)
		m.emission_energy_multiplier = emit
	elif _clean:
		m.next_pass = outline_thin()
	else:
		_paint(m)
		m.next_pass = outline()
	_mats[key] = m
	return m


static func img_mat(tex: Texture2D, key: String, tint: Color = Color.WHITE, rough: float = 0.85) -> StandardMaterial3D:
	var k := "i_%s_%s" % [key, tint.to_html()]
	if _mats.has(k):
		return _mats[k]
	var m := StandardMaterial3D.new()
	m.albedo_texture = tex
	m.albedo_color = tint
	m.roughness = rough
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	_mats[k] = m
	return m


static func tex_mat(tex_name: String, tint: Color = Color.WHITE, rough: float = 0.8) -> StandardMaterial3D:
	var key := "t_%s_%s" % [tex_name, tint.to_html()]
	if _mats.has(key):
		return _mats[key]
	var m := StandardMaterial3D.new()
	m.albedo_texture = load("res://art/%s.svg" % tex_name)
	m.albedo_color = tint
	m.roughness = rough
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	_mats[key] = m
	return m


# rounded box: a subdivided cube pushed out to a box with round edges
static func rbox(size: Vector3, r: float, seg: int = 4) -> ArrayMesh:
	var key := "rb_%s_%.3f_%d" % [str(size), r, seg]
	if _meshes.has(key):
		return _meshes[key]
	r = minf(r, minf(size.x, minf(size.y, size.z)) / 2.0 - 0.001)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var inner := size / 2.0 - Vector3(r, r, r)
	var faces := [
		[Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)], [Vector3(-1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, -1)],
		[Vector3(0, 1, 0), Vector3(0, 0, 1), Vector3(1, 0, 0)], [Vector3(0, -1, 0), Vector3(0, 0, 1), Vector3(-1, 0, 0)],
		[Vector3(0, 0, 1), Vector3(1, 0, 0), Vector3(0, 1, 0)], [Vector3(0, 0, -1), Vector3(-1, 0, 0), Vector3(0, 1, 0)],
	]
	var n := seg * 2
	for f in faces:
		var nrm: Vector3 = f[0]
		var u: Vector3 = f[1]
		var v: Vector3 = f[2]
		var grid: Array = []
		for j in range(n + 1):
			var row: Array = []
			for i in range(n + 1):
				var a := float(i) / n * 2.0 - 1.0
				var b := float(j) / n * 2.0 - 1.0
				var q: Vector3 = (nrm + u * a + v * b) * (size / 2.0)
				var c := Vector3(clampf(q.x, -inner.x, inner.x), clampf(q.y, -inner.y, inner.y), clampf(q.z, -inner.z, inner.z))
				var d := q - c
				var nn := d.normalized() if d.length() > 0.0001 else nrm
				row.append([c + nn * r, nn, Vector2((a + 1.0) * 0.5, (b + 1.0) * 0.5)])
			grid.append(row)
		for j in range(n):
			for i in range(n):
				var a0: Array = grid[j][i]
				var a1: Array = grid[j][i + 1]
				var b0: Array = grid[j + 1][i]
				var b1: Array = grid[j + 1][i + 1]
				for t in [[a0, a1, b0], [a1, b1, b0]]:
					var p0: Vector3 = t[0][0]
					var p1: Vector3 = t[1][0]
					var p2: Vector3 = t[2][0]
					var order: Array = t
					if (p1 - p0).cross(p2 - p0).dot(nrm) > 0.0:
						order = [t[0], t[2], t[1]]       # Godot front faces are clockwise
					for e in order:
						st.set_normal(e[1])
						st.set_uv(e[2])
						st.add_vertex(e[0])
	var mesh := st.commit()
	_meshes[key] = mesh
	return mesh


static func mi(parent: Node, mesh: Mesh, material: Material, pos: Vector3 = Vector3.ZERO, rot_deg: Vector3 = Vector3.ZERO, scl: Vector3 = Vector3.ONE) -> MeshInstance3D:
	var m := MeshInstance3D.new()
	m.mesh = mesh
	m.material_override = material
	m.position = pos
	m.rotation_degrees = rot_deg
	m.scale = scl
	parent.add_child(m)
	return m


static func sphere(r: float, hemi: bool = false) -> SphereMesh:
	var key := "sp_%.3f_%s" % [r, hemi]
	if _meshes.has(key):
		return _meshes[key]
	var s := SphereMesh.new()
	s.radius = r
	s.height = r if hemi else r * 2.0
	s.is_hemisphere = hemi
	s.radial_segments = 24
	s.rings = 12
	_meshes[key] = s
	return s


static func cyl(rt: float, rb: float, h: float, seg: int = 24) -> CylinderMesh:
	var key := "cy_%.3f_%.3f_%.3f_%d" % [rt, rb, h, seg]
	if _meshes.has(key):
		return _meshes[key]
	var c := CylinderMesh.new()
	c.top_radius = rt
	c.bottom_radius = rb
	c.height = h
	c.radial_segments = seg
	c.rings = 1
	_meshes[key] = c
	return c


static func capsule(r: float, h: float) -> CapsuleMesh:
	var key := "ca_%.3f_%.3f" % [r, h]
	if _meshes.has(key):
		return _meshes[key]
	var c := CapsuleMesh.new()
	c.radius = r
	c.height = h
	c.radial_segments = 20
	c.rings = 6
	_meshes[key] = c
	return c


static func torus(inner: float, outer: float) -> TorusMesh:
	var key := "to_%.3f_%.3f" % [inner, outer]
	if _meshes.has(key):
		return _meshes[key]
	var t := TorusMesh.new()
	t.inner_radius = inner
	t.outer_radius = outer
	t.rings = 24
	t.ring_segments = 10
	_meshes[key] = t
	return t


# optional drop-in model: res://assets/<name>.glb (see assets/README.md)
static func asset(asset_name: String) -> Node3D:
	var p := "res://assets/%s.glb" % asset_name
	if ResourceLoader.exists(p):
		var ps = load(p)
		if ps is PackedScene:
			var inst := (ps as PackedScene).instantiate()
			if inst is Node3D:
				_polish(inst)
				return inst
	return null


# give imported models the same look as the built-in ones: ink outline + grunge on every solid material
static func _polish(n: Node) -> void:
	if n is MeshInstance3D:
		var mi_ := n as MeshInstance3D
		if mi_.mesh != null:
			for i in mi_.mesh.get_surface_count():
				var src := mi_.mesh.surface_get_material(i)
				if src is StandardMaterial3D:
					var d := (src as StandardMaterial3D).duplicate() as StandardMaterial3D
					if not d.emission_enabled:
						if d.albedo_texture == null:
							_paint(d)
						else:
							d.albedo_color = Color(0.72, 0.66, 0.6)
						d.next_pass = outline()
					mi_.set_surface_override_material(i, d)
	for c in n.get_children():
		_polish(c)


# counter-top height of the stations (the KayKit counters are half size here)
const TOP := 0.75

const ASSET_NAMES := {"X": "counter", "T": "table", "M": "crate_meat", "V": "crate_veg", "D": "crate_dough",
	"C": "chop_board", "S": "stove", "O": "oven", "A": "plate_station", "B": "bin"}


static func node(parent: Node, node_name: String, pos: Vector3 = Vector3.ZERO) -> Node3D:
	var n := Node3D.new()
	n.name = node_name
	n.position = pos
	parent.add_child(n)
	return n


# a flat picture floating in space (faces, labels): unshaded + alpha
static func decal(parent: Node, tex_name: String, width: float, pos: Vector3, name_: String = "") -> Sprite3D:
	var s := Sprite3D.new()
	if _tex.has(tex_name):
		s.texture = _tex[tex_name]
	else:
		s.texture = load("res://art/%s.svg" % tex_name)
		_tex[tex_name] = s.texture
	s.pixel_size = width / float(s.texture.get_width())
	s.shaded = false
	s.transparent = true
	s.alpha_cut = SpriteBase3D.ALPHA_CUT_DISABLED
	s.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	s.position = pos
	if name_ != "":
		s.name = name_
	parent.add_child(s)
	return s


# ====================================================================
# Kitchen stations
# ====================================================================

const WOOD := "b57a3e"
const WOOD_DARK := "93582a"
const WOOD_LIGHT := "d9b57e"


static func counter_base(parent: Node, top_hex: String = "d99a4a", body_hex: String = WOOD_DARK, h: float = 0.8) -> void:
	mi(parent, rbox(Vector3(0.96, h, 0.96), 0.07), mat(body_hex, 0.7), Vector3(0, h / 2.0, 0))
	mi(parent, rbox(Vector3(1.0, 0.1, 1.0), 0.04), mat(top_hex, 0.45), Vector3(0, h + 0.03, 0))
	mi(parent, rbox(Vector3(0.9, 0.04, 0.02), 0.01), mat("8a5528", 0.8), Vector3(0, h * 0.5, 0.485))


static func station(kind: String) -> Node3D:
	var root := Node3D.new()
	root.name = "station_" + kind
	if ASSET_NAMES.has(kind):
		var custom := asset(str(ASSET_NAMES[kind]))
		if custom != null:
			# hoist the model's parts so named ones (pot, flames, glow) are direct children
			for c in custom.get_children():
				custom.remove_child(c)
				c.owner = null
				root.add_child(c)
			custom.free()
			return root
	match kind:
		"X":
			counter_base(root)
		"T":
			_table(root)
		"M", "V", "D":
			_crate(root, kind)
		"C":
			counter_base(root, "d9a066")
			mi(root, rbox(Vector3(0.82, 0.06, 0.64), 0.025), mat(WOOD_LIGHT, 0.5), Vector3(0, 0.9, 0))
			var knife := node(root, "knife", Vector3(-0.18, 0.95, 0.12))
			knife.rotation_degrees = Vector3(0, 30, 0)
			mi(knife, rbox(Vector3(0.34, 0.012, 0.08), 0.004), mat("dfe5ee", 0.2, 0.9), Vector3(0.12, 0, 0))
			mi(knife, rbox(Vector3(0.16, 0.03, 0.05), 0.012), mat("6b3f1d", 0.6), Vector3(-0.14, 0.005, 0))
			node(root, "item_slot", Vector3(0.1, 0.95, -0.02))
		"S":
			_stove(root)
		"O":
			_oven(root)
		"A":
			counter_base(root, "c9b6e0", "8a76a8")
			mi(root, cyl(0.34, 0.31, 0.04), mat("f4f6fb", 0.25), Vector3(0, 0.9, 0))
			mi(root, torus(0.30, 0.35), mat("dfe3ee", 0.3), Vector3(0, 0.915, 0))
			node(root, "dish_slot", Vector3(0, 0.93, 0))
		"B":
			mi(root, cyl(0.36, 0.28, 0.8), mat("7f8aa3", 0.5, 0.3), Vector3(0, 0.4, 0))
			mi(root, cyl(0.38, 0.38, 0.09), mat("9aa5bf", 0.4, 0.3), Vector3(0, 0.83, 0), Vector3(6, 0, 0))
			mi(root, torus(0.045, 0.1), mat("5b6580", 0.4, 0.3), Vector3(0, 0.9, 0))
			for i in 4:
				var a := i * PI / 2.0 + 0.4
				mi(root, rbox(Vector3(0.03, 0.55, 0.03), 0.01), mat("4d566c", 0.5), Vector3(cos(a) * 0.3, 0.38, sin(a) * 0.3 + 0.0), Vector3(0, 0, 0))
	return root


static func _table(root: Node3D) -> void:
	mi(root, cyl(0.07, 0.1, 0.66), mat("7b4a26", 0.7), Vector3(0, 0.33, 0))
	mi(root, cyl(0.3, 0.3, 0.05), mat("7b4a26", 0.7), Vector3(0, 0.03, 0))
	mi(root, rbox(Vector3(0.98, 0.07, 0.98), 0.035), mat("d9a35e", 0.55), Vector3(0, 0.7, 0))
	mi(root, rbox(Vector3(0.94, 0.02, 0.94), 0.01), mat("c0392b", 0.8), Vector3(0, 0.75, 0))
	mi(root, rbox(Vector3(0.46, 0.012, 0.46), 0.004), mat("f6f1e6", 0.8), Vector3(0, 0.763, 0), Vector3(0, 45, 0))
	mi(root, cyl(0.13, 0.11, 0.03), mat("f6f8fc", 0.25), Vector3(0, 0.78, 0.18))
	mi(root, cyl(0.05, 0.045, 0.1), mat("bfe3ef", 0.15), Vector3(0.3, 0.82, -0.28))


# a diner chair: seat + back. Faces +Z (the sitter looks towards +Z), the back is at -Z.
static func chair() -> Node3D:
	var r := Node3D.new()
	r.name = "chair"
	var custom := asset("chair")
	if custom != null:
		r.add_child(custom)
		return r
	var wood := mat("b8402f", 0.6)
	mi(r, rbox(Vector3(0.62, 0.09, 0.6), 0.04), wood, Vector3(0, 0.44, 0))
	mi(r, rbox(Vector3(0.62, 0.5, 0.08), 0.04), wood, Vector3(0, 0.74, -0.28))
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			mi(r, cyl(0.035, 0.03, 0.42), mat("5a2a1e", 0.7), Vector3(sx * 0.25, 0.21, sz * 0.24))
	return r


static func _crate(root: Node3D, kind: String) -> void:
	mi(root, rbox(Vector3(0.9, 0.5, 0.9), 0.05), mat(WOOD, 0.75), Vector3(0, 0.25, 0))
	for y in [0.12, 0.3]:
		mi(root, rbox(Vector3(0.93, 0.05, 0.93), 0.02), mat("8d5629", 0.8), Vector3(0, y, 0))
	for sx in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			mi(root, rbox(Vector3(0.1, 0.52, 0.1), 0.03), mat("8d5629", 0.8), Vector3(sx * 0.42, 0.26, sz * 0.42))
	match kind:
		"M":
			mi(root, rbox(Vector3(0.78, 0.04, 0.78), 0.02), mat("4a2a1a", 0.9), Vector3(0, 0.5, 0))
			for p in [Vector3(-0.2, 0.58, -0.12), Vector3(0.18, 0.6, -0.15), Vector3(0.0, 0.6, 0.18), Vector3(-0.22, 0.6, 0.2), Vector3(0.24, 0.58, 0.2)]:
				mi(root, sphere(0.15), mat("e5707e", 0.35), p, Vector3(0, p.x * 90, 0), Vector3(1.0, 0.45, 0.8))
				mi(root, sphere(0.07), mat("ffe4e8", 0.4), p + Vector3(0.04, 0.05, 0.0), Vector3.ZERO, Vector3(1, 0.3, 1))
		"V":
			mi(root, rbox(Vector3(0.78, 0.04, 0.78), 0.02), mat("254a1e", 0.9), Vector3(0, 0.5, 0))
			mi(root, sphere(0.2), mat("86c04a", 0.5), Vector3(-0.18, 0.66, -0.1))
			mi(root, torus(0.12, 0.2), mat("5a9a3a", 0.5), Vector3(-0.18, 0.7, -0.1))
			mi(root, sphere(0.15), mat("e24a3a", 0.3), Vector3(0.2, 0.64, -0.12))
			mi(root, sphere(0.17), mat("9fd45c", 0.5), Vector3(0.0, 0.64, 0.2))
			for i in 3:
				mi(root, cyl(0.0, 0.05, 0.3), mat("f08a2a", 0.5), Vector3(0.24 + i * 0.05, 0.62, 0.18 - i * 0.07), Vector3(70, i * 20, 80))
		"D":
			mi(root, rbox(Vector3(0.78, 0.04, 0.78), 0.02), mat("6b5130", 0.9), Vector3(0, 0.5, 0))
			for p in [Vector3(-0.2, 0.64, -0.1), Vector3(0.18, 0.66, -0.12), Vector3(0.0, 0.62, 0.2)]:
				mi(root, sphere(0.2), mat("f6ead0", 0.7), p, Vector3.ZERO, Vector3(1, 0.85, 1))


static func _stove(root: Node3D) -> void:
	mi(root, rbox(Vector3(0.96, 0.8, 0.96), 0.07), mat("5b6078", 0.4, 0.4), Vector3(0, 0.4, 0))
	mi(root, rbox(Vector3(1.0, 0.08, 1.0), 0.03), mat("2a2c3a", 0.35, 0.3), Vector3(0, 0.82, 0))
	mi(root, torus(0.2, 0.34), mat("1b1c26", 0.4, 0.5), Vector3(0, 0.88, 0))
	mi(root, torus(0.08, 0.16), mat("1b1c26", 0.4, 0.5), Vector3(0, 0.885, 0))
	for i in 3:
		mi(root, cyl(0.045, 0.045, 0.06), mat("dfe3ee", 0.3, 0.8), Vector3(-0.28 + i * 0.28, 0.58, 0.49), Vector3(90, 0, 0))
	# the pot sits on the burner while something cooks
	var pot := node(root, "pot", Vector3(0, 0.9, 0))
	mi(pot, cyl(0.3, 0.27, 0.24), mat("b8bfd0", 0.3, 0.8), Vector3(0, 0.12, 0))
	mi(pot, torus(0.27, 0.32), mat("dfe5f2", 0.25, 0.8), Vector3(0, 0.24, 0))
	mi(pot, rbox(Vector3(0.14, 0.04, 0.05), 0.02), mat("4a4e63", 0.5), Vector3(0.38, 0.2, 0))
	mi(pot, rbox(Vector3(0.14, 0.04, 0.05), 0.02), mat("4a4e63", 0.5), Vector3(-0.38, 0.2, 0))
	mi(pot, sphere(0.3, true), mat("c9cfde", 0.25, 0.8), Vector3(0, 0.25, 0), Vector3.ZERO, Vector3(1, 0.5, 1))
	mi(pot, sphere(0.05), mat("4a4e63", 0.4), Vector3(0, 0.42, 0))
	pot.visible = false
	var flames := node(root, "flames", Vector3(0, 0.9, 0))
	for i in 8:
		var a := i * TAU / 8.0
		var f := mi(flames, cyl(0.0, 0.05, 0.16), mat("ff7a1f", 0.5, 0.0, 2.2), Vector3(cos(a) * 0.26, 0.05, sin(a) * 0.26))
		f.name = "flame%d" % i
	flames.visible = false


static func _oven(root: Node3D) -> void:
	mi(root, rbox(Vector3(0.96, 1.05, 0.9), 0.08), mat("c3c9d6", 0.3, 0.5), Vector3(0, 0.525, -0.02))
	mi(root, rbox(Vector3(0.64, 0.46, 0.04), 0.03), mat("23242e", 0.15, 0.2), Vector3(0, 0.46, 0.44))
	var glow := mi(root, rbox(Vector3(0.58, 0.4, 0.03), 0.02), mat("e86a1a", 0.4, 0.0, 1.6), Vector3(0, 0.46, 0.452))
	glow.name = "glow"
	glow.visible = false
	mi(root, cyl(0.025, 0.025, 0.66), mat("eef0f6", 0.2, 0.9), Vector3(0, 0.78, 0.5), Vector3(0, 0, 90))
	for i in 3:
		mi(root, cyl(0.05, 0.05, 0.06), mat("6b7288", 0.3, 0.6), Vector3(-0.28 + i * 0.28, 0.95, 0.46), Vector3(90, 0, 0))
	mi(root, rbox(Vector3(0.8, 0.02, 0.04), 0.01), mat("a0a8bb", 0.3, 0.6), Vector3(0, 0.2, 0.46))


# ====================================================================
# Food
# ====================================================================

static func item(id: String) -> Node3D:
	var r := Node3D.new()
	r.name = "item_" + id
	var custom := asset("item_" + id)
	if custom != null:
		r.add_child(custom)
		return r
	match id:
		"veg":
			mi(r, sphere(0.15), mat("86c04a", 0.5), Vector3(0, 0.15, 0))
			mi(r, torus(0.1, 0.16), mat("5a9a3a", 0.5), Vector3(0, 0.19, 0))
			mi(r, sphere(0.09), mat("b5e07a", 0.5), Vector3(-0.04, 0.24, 0.05))
		"meat":
			mi(r, sphere(0.17), mat("e5707e", 0.35), Vector3(0, 0.08, 0), Vector3.ZERO, Vector3(1.1, 0.5, 0.85))
			mi(r, sphere(0.07), mat("ffe4e8", 0.4), Vector3(0.08, 0.14, 0.04), Vector3.ZERO, Vector3(1, 0.35, 1))
		"dough":
			mi(r, sphere(0.16), mat("f6ead0", 0.7), Vector3(0, 0.13, 0), Vector3.ZERO, Vector3(1, 0.85, 1))
		"veg_chop":
			var cols := ["7bc043", "f7a541", "e84f3d", "7bc043", "f7a541", "9fd45c"]
			for i in 6:
				var a := i * 1.1
				mi(r, rbox(Vector3(0.1, 0.08, 0.1), 0.02), mat(cols[i], 0.5), Vector3(cos(a) * 0.1, 0.05 + (i % 2) * 0.05, sin(a) * 0.1), Vector3(0, i * 25, 0))
		"meat_chop":
			for i in 7:
				var a := i * 0.95
				mi(r, sphere(0.06), mat("e5707e", 0.4), Vector3(cos(a) * 0.09, 0.05 + (i % 3) * 0.035, sin(a) * 0.09))
		"veg_cook":
			mi(r, sphere(0.2, true), mat("c9cfde", 0.3, 0.6), Vector3(0, 0.2, 0), Vector3(180, 0, 0))
			mi(r, cyl(0.19, 0.19, 0.02), mat("d98a2f", 0.25), Vector3(0, 0.17, 0))
			for i in 4:
				mi(r, sphere(0.05), mat("7bc043", 0.4), Vector3(cos(i * 1.6) * 0.08, 0.2, sin(i * 1.6) * 0.08))
		"meat_cooked":
			mi(r, sphere(0.17), mat("8a5a2b", 0.55), Vector3(0, 0.08, 0), Vector3.ZERO, Vector3(1.1, 0.5, 0.85))
			for i in 3:
				mi(r, rbox(Vector3(0.012, 0.01, 0.2), 0.004), mat("3a1f0e", 0.6), Vector3(-0.08 + i * 0.08, 0.158, 0), Vector3(0, 25, 0))
		"patty":
			mi(r, cyl(0.15, 0.15, 0.05), mat("6f4518", 0.7), Vector3(0, 0.04, 0))
			mi(r, torus(0.12, 0.16), mat("5a3318", 0.7), Vector3(0, 0.05, 0))
		"bun":
			mi(r, sphere(0.17, true), mat("e0983a", 0.45), Vector3(0, 0.03, 0), Vector3.ZERO, Vector3(1, 0.8, 1))
			for i in 6:
				var a := i * 1.05
				mi(r, sphere(0.015), mat("fff1c1", 0.4), Vector3(cos(a) * 0.08, 0.15, sin(a) * 0.08), Vector3.ZERO, Vector3(1.4, 0.7, 0.9))
		"burnt":
			mi(r, sphere(0.15), mat("1a1a1a", 0.9), Vector3(0, 0.1, 0), Vector3.ZERO, Vector3(1.1, 0.7, 0.9))
			mi(r, sphere(0.08), mat("2b2b2b", 0.9), Vector3(0.1, 0.12, 0.05))
	return r


static func _plate(root: Node3D) -> void:
	mi(root, cyl(0.3, 0.26, 0.035), mat("f6f8fc", 0.2), Vector3(0, 0.02, 0))
	mi(root, torus(0.27, 0.32), mat("e3e7f2", 0.25), Vector3(0, 0.04, 0))


static func dish(id: String) -> Node3D:
	var r := Node3D.new()
	r.name = "dish_" + id
	var custom := asset("dish_" + id)
	if custom != null:
		r.add_child(custom)
		return r
	match id:
		"salad":
			_plate(r)
			for p in [Vector3(-0.1, 0.1, 0), Vector3(0.1, 0.1, 0.05), Vector3(0, 0.15, -0.1), Vector3(0.0, 0.12, 0.12), Vector3(-0.14, 0.09, 0.12)]:
				mi(r, sphere(0.11), mat("86c04a" if p.x < 0 else "6aae35", 0.5), p)
			for p in [Vector3(0.05, 0.2, 0.0), Vector3(-0.1, 0.17, 0.1), Vector3(0.13, 0.15, 0.1)]:
				mi(r, sphere(0.05), mat("e24a3a", 0.3), p)
		"steak":
			_plate(r)
			mi(r, sphere(0.2), mat("8a5a2b", 0.5), Vector3(-0.04, 0.1, 0), Vector3.ZERO, Vector3(1.15, 0.5, 0.9))
			for i in 3:
				mi(r, rbox(Vector3(0.012, 0.01, 0.24), 0.004), mat("3a1f0e", 0.6), Vector3(-0.14 + i * 0.09, 0.18, 0), Vector3(0, 25, 0))
			for p in [Vector3(0.2, 0.08, 0.12), Vector3(0.24, 0.08, 0.0), Vector3(0.18, 0.08, -0.12)]:
				mi(r, sphere(0.055), mat("6aae35", 0.5), p)
		"soup":
			mi(r, sphere(0.28, true), mat("ff8a5a", 0.35), Vector3(0, 0.28, 0), Vector3(180, 0, 0))
			mi(r, cyl(0.26, 0.26, 0.02), mat("e08a2f", 0.2), Vector3(0, 0.22, 0))
			mi(r, torus(0.25, 0.3), mat("ffa070", 0.35), Vector3(0, 0.28, 0))
			for i in 4:
				mi(r, sphere(0.045), mat("7bc043", 0.4), Vector3(cos(i * 1.7) * 0.12, 0.23, sin(i * 1.7) * 0.12))
		"stew":
			mi(r, sphere(0.28, true), mat("6f8fe0", 0.35), Vector3(0, 0.28, 0), Vector3(180, 0, 0))
			mi(r, cyl(0.26, 0.26, 0.02), mat("7a4a26", 0.3), Vector3(0, 0.22, 0))
			mi(r, torus(0.25, 0.3), mat("8aa6ee", 0.35), Vector3(0, 0.28, 0))
			for p in [Vector3(-0.1, 0.25, -0.05), Vector3(0.1, 0.25, 0.0), Vector3(0.0, 0.25, 0.1)]:
				mi(r, rbox(Vector3(0.1, 0.07, 0.1), 0.02), mat("a86a38", 0.5), p, Vector3(0, p.x * 200, 0))
			mi(r, sphere(0.04), mat("7bc043", 0.4), Vector3(0.12, 0.26, 0.1))
		"burger":
			_plate(r)
			mi(r, sphere(0.22, true), mat("e0983a", 0.45), Vector3(0, 0.04, 0), Vector3(180, 0, 0), Vector3(1, 0.4, 1))
			mi(r, cyl(0.22, 0.22, 0.1), mat("6f4518", 0.7), Vector3(0, 0.1, 0))
			mi(r, cyl(0.25, 0.25, 0.025), mat("7bc043", 0.5), Vector3(0, 0.17, 0))
			mi(r, rbox(Vector3(0.4, 0.02, 0.4), 0.005), mat("ffd23f", 0.4), Vector3(0, 0.2, 0), Vector3(0, 45, 0))
			mi(r, sphere(0.23, true), mat("e0983a", 0.45), Vector3(0, 0.21, 0), Vector3.ZERO, Vector3(1, 0.85, 1))
			for i in 6:
				var a := i * 1.05
				mi(r, sphere(0.015), mat("fff1c1", 0.4), Vector3(cos(a) * 0.11, 0.38, sin(a) * 0.11), Vector3.ZERO, Vector3(1.4, 0.7, 0.9))
	return r


# ====================================================================
# Characters
# ====================================================================

static func _hex(list: Array, idx: int) -> String:
	return str(list[clampi(idx, 0, list.size() - 1)])


# A chef. Children worth animating: body, head, arm_l, arm_r, foot_l, foot_r, held (anchor above the head)
static func chef(look: Dictionary) -> Node3D:
	_clean = true
	var r: Node3D = _kay_chef(look) if USE_KAY else null
	if r == null:
		r = _chef(look)
	_clean = false
	return r


# ---- rigged chefs: KayKit Adventurers (CC0) + the Rig_Medium animation set ----
const USE_KAY := false   # the rigged KayKit chefs are in assets/chars; off because the procedural chibi chefs read better from above
const CHAR_FILES := ["Knight", "Barbarian", "Mage", "Ranger", "Rogue", "Rogue_Hooded"]
const KAY_HIDE := ["Helmet", "HelmetVisor", "Cape", "Hat", "BearHat", "Quiver", "Mask"]
const KAY_SCALE := 0.63          # head centre ends up at y = 1.1 like the old procedural chef
static var _anim_lib: AnimationLibrary


static func _kay_lib() -> AnimationLibrary:
	if _anim_lib == null:
		_anim_lib = AnimationLibrary.new()
		for f in ["Rig_Medium_General", "Rig_Medium_MovementBasic"]:
			var inst := (load("res://assets/chars/%s.glb" % f) as PackedScene).instantiate()
			var ap := inst.find_child("AnimationPlayer", true, false) as AnimationPlayer
			for a in ap.get_animation_list():
				if a == "T-Pose" or _anim_lib.has_animation(a):
					continue
				var an := ap.get_animation(a).duplicate() as Animation
				if a.begins_with("Idle") or a.begins_with("Walking") or a.begins_with("Running"):
					an.loop_mode = Animation.LOOP_LINEAR
				_anim_lib.add_animation(a, an)
			inst.free()
	return _anim_lib


static func _kay_chef(look: Dictionary) -> Node3D:
	var idx: int = int(look.get("skin", 0)) % CHAR_FILES.size()
	var path: String = "res://assets/chars/%s.glb" % CHAR_FILES[idx]
	if not ResourceLoader.exists(path) or not ResourceLoader.exists("res://assets/chars/Rig_Medium_General.glb"):
		return null
	var root := Node3D.new()
	root.name = "chef"
	var model := (load(path) as PackedScene).instantiate() as Node3D
	model.name = "model"
	model.scale = Vector3.ONE * KAY_SCALE
	root.add_child(model)
	for mi_ in model.find_children("*", "MeshInstance3D"):
		var mesh_i := mi_ as MeshInstance3D
		for h in KAY_HIDE:
			if str(mesh_i.name).ends_with("_" + h):
				mesh_i.visible = false
		for s in mesh_i.mesh.get_surface_count():
			var src := mesh_i.mesh.surface_get_material(s)
			if src is StandardMaterial3D:
				var d := (src as StandardMaterial3D).duplicate() as StandardMaterial3D
				d.next_pass = outline_thin()
				d.roughness = 0.8
				mesh_i.set_surface_override_material(s, d)
	# stand-in nodes so the old rig code (menus, sync) still finds its named parts
	var body := node(root, "body", Vector3(0, 0.46, 0))
	node(body, "arm_l")
	node(body, "arm_r")
	var head := node(root, "head", Vector3(0, 1.1, 0))
	for nm in ["eyes", "mouth"]:
		var sp := Sprite3D.new()
		sp.name = nm
		sp.visible = false
		head.add_child(sp)
	for nm in ["foot_l", "foot_r", "leg_l", "leg_r"]:
		node(root, nm)
	node(root, "held", Vector3(0, 1.95, 0))
	# chef hat on the head bone, apron on the chest
	var sk := model.find_child("Skeleton3D", true, false) as Skeleton3D
	var hat_style := str(Data.HATS[clampi(int(look.get("hat", 0)), 0, Data.HATS.size() - 1)])
	var hb := BoneAttachment3D.new()
	hb.bone_name = "head"
	sk.add_child(hb)
	var hh := node(hb, "hat", Vector3(0, 0.56, 0.0))
	hh.scale = Vector3.ONE * 1.9
	_hat(hh, hat_style, _hex(Data.COLORS, int(look.get("hat_col", 0))))
	var cb := BoneAttachment3D.new()
	cb.bone_name = "chest"
	sk.add_child(cb)
	var ap_col := _hex(Data.COLORS, int(look.get("apron", 0)))
	mi(cb, rbox(Vector3(0.5, 0.56, 0.1), 0.05), mat(ap_col, 0.65), Vector3(0, -0.14, 0.34), Vector3(6, 0, 0))
	mi(cb, rbox(Vector3(0.24, 0.14, 0.04), 0.02), mat(ap_col, 0.65), Vector3(0, -0.3, 0.4))
	var ap := AnimationPlayer.new()
	ap.name = "anim"
	root.add_child(ap)
	ap.root_node = NodePath("../model")
	ap.add_animation_library("", _kay_lib())
	ap.play("Idle_A")
	ap.advance(randf() * 1.0)
	root.set_meta("kay", true)
	return root


# play a looping animation (one-shots like PickUp finish first)
static func kay_play(n: Node3D, anim: String, speed: float = 1.0) -> void:
	var ap := n.get_node_or_null("anim") as AnimationPlayer
	if ap == null:
		return
	if ap.current_animation in ["PickUp", "Interact", "Use_Item"] and ap.is_playing():
		return
	ap.speed_scale = speed
	if ap.current_animation != anim or not ap.is_playing():
		ap.play(anim, 0.15)


static func kay_once(n: Node3D, anim: String) -> void:
	var ap := n.get_node_or_null("anim") as AnimationPlayer
	if ap != null:
		ap.speed_scale = 1.4
		ap.play(anim, 0.1)


static func _chef(look: Dictionary) -> Node3D:
	var root := Node3D.new()
	root.name = "chef"
	var skin := _hex(Data.SKINS, int(look.get("skin", 0)))
	var jacket := _hex(Data.COLORS, int(look.get("jacket", 0)))
	var hat_col := _hex(Data.COLORS, int(look.get("hat_col", 0)))
	var black := "26262e"
	mi(root, cyl(0.2, 0.2, 0.01), mat("000000", 1.0), Vector3(0, 0.0, 0)).visible = false
	mi(root, rbox(Vector3(0.2, 0.13, 0.3), 0.06), mat(black, 0.5), Vector3(-0.13, 0.065, 0.04)).name = "foot_l"
	mi(root, rbox(Vector3(0.2, 0.13, 0.3), 0.06), mat(black, 0.5), Vector3(0.13, 0.065, 0.04)).name = "foot_r"
	for sx in [-1.0, 1.0]:
		mi(root, capsule(0.09, 0.4), mat(black, 0.7), Vector3(sx * 0.13, 0.28, 0.01)).name = "leg_l" if sx < 0 else "leg_r"
	var body := node(root, "body", Vector3(0, 0.46, 0))
	mi(body, capsule(0.31, 0.66), mat(jacket, 0.65), Vector3(0, 0.2, 0), Vector3.ZERO, Vector3(1.0, 1.0, 0.9))
	# double-breasted front: two plackets crossing, two columns of buttons, a white collar
	for i in 3:
		for sx in [-1.0, 1.0]:
			mi(body, sphere(0.024), mat("8d96aa", 0.35), Vector3(sx * 0.115, 0.34 - i * 0.12, 0.245))
	mi(body, torus(0.12, 0.2), mat("eef1f7", 0.6), Vector3(0, 0.46, 0.0), Vector3.ZERO, Vector3(1, 0.5, 0.9))
	for sx in [-1.0, 1.0]:
		var arm := node(body, "arm_l" if sx < 0 else "arm_r", Vector3(sx * 0.35, 0.4, 0))
		mi(arm, capsule(0.095, 0.4), mat(jacket, 0.65), Vector3(sx * 0.03, -0.17, 0), Vector3(0, 0, sx * 14))
		mi(arm, cyl(0.1, 0.1, 0.06), mat("eef1f7", 0.6), Vector3(sx * 0.08, -0.33, 0.0))
		mi(arm, sphere(0.105), mat(skin, 0.5), Vector3(sx * 0.1, -0.42, 0.03))
	var head := node(root, "head", Vector3(0, 1.1, 0))
	head.scale = Vector3.ONE * 0.84
	mi(head, sphere(0.34), mat(skin, 0.45), Vector3.ZERO, Vector3.ZERO, Vector3(1.0, 0.94, 0.96))
	for sx in [-1.0, 1.0]:
		mi(head, sphere(0.07), mat(skin, 0.45), Vector3(sx * 0.33, -0.01, 0.0))
	mi(head, sphere(0.075), mat(skin, 0.4).duplicate(), Vector3(0, -0.05, 0.32))
	decal(head, "eyes_open", 0.5, Vector3(0, 0.04, 0.345), "eyes")
	decal(head, "mouth_smile", 0.17, Vector3(0, -0.14, 0.325), "mouth")
	var gear := node(head, "gear", Vector3(0, 0.0, 0.05))
	gear.scale = Vector3.ONE * 1.18
	_accessory(gear, str(Data.ACCS[clampi(int(look.get("acc", 0)), 0, Data.ACCS.size() - 1)]))
	var hatn := node(head, "hat", Vector3(0, 0.0, 0))
	hatn.scale = Vector3.ONE * 0.92
	_hat(hatn, str(Data.HATS[clampi(int(look.get("hat", 0)), 0, Data.HATS.size() - 1)]), hat_col)
	node(root, "held", Vector3(0, 1.95, 0))
	return root


static func _accessory(head: Node3D, acc: String) -> void:
	match acc:
		"glasses":
			for sx in [-1.0, 1.0]:
				mi(head, torus(0.062, 0.085), mat("2a1a12", 0.4), Vector3(sx * 0.095, 0.03, 0.265), Vector3(90, 0, 0))
			mi(head, rbox(Vector3(0.05, 0.015, 0.015), 0.005), mat("2a1a12", 0.4), Vector3(0, 0.04, 0.268))
		"sunglasses":
			for sx in [-1.0, 1.0]:
				mi(head, rbox(Vector3(0.15, 0.1, 0.03), 0.025), mat("14141c", 0.15, 0.2), Vector3(sx * 0.095, 0.03, 0.272))
			mi(head, rbox(Vector3(0.06, 0.02, 0.02), 0.008), mat("14141c", 0.3), Vector3(0, 0.05, 0.275))
		"mustache":
			for sx in [-1.0, 1.0]:
				mi(head, capsule(0.03, 0.15), mat("4a2e1a", 0.6), Vector3(sx * 0.06, -0.075, 0.272), Vector3(0, 0, 90 + sx * 12))
		"beard":
			mi(head, sphere(0.2), mat("4a2e1a", 0.7), Vector3(0, -0.14, 0.05), Vector3.ZERO, Vector3(1.0, 0.8, 0.9))


static func _hat(head: Node3D, style: String, hex: String) -> void:
	var m := mat(hex, 0.6)
	match style:
		"toque":
			mi(head, cyl(0.225, 0.215, 0.15), m, Vector3(0, 0.27, 0))
			mi(head, sphere(0.2), m, Vector3(-0.1, 0.46, 0.0))
			mi(head, sphere(0.2), m, Vector3(0.1, 0.46, 0.0))
			mi(head, sphere(0.23), m, Vector3(0, 0.52, 0.0))
		"cap":
			mi(head, sphere(0.295, true), m, Vector3(0, 0.07, 0), Vector3.ZERO, Vector3(1.0, 0.95, 1.0))
			mi(head, rbox(Vector3(0.34, 0.03, 0.2), 0.015), m, Vector3(0, 0.1, 0.33), Vector3(-8, 0, 0))
			mi(head, sphere(0.035), m, Vector3(0, 0.32, 0))
		"beanie":
			mi(head, sphere(0.3, true), m, Vector3(0, 0.07, 0), Vector3.ZERO, Vector3(1.0, 1.05, 1.0))
			mi(head, torus(0.26, 0.31), m, Vector3(0, 0.1, 0), Vector3.ZERO, Vector3(1, 1.3, 1))
			mi(head, sphere(0.09), m, Vector3(0, 0.38, 0))
		"bandana":
			mi(head, sphere(0.292, true), m, Vector3(0, 0.07, 0), Vector3.ZERO, Vector3(1.0, 0.7, 1.0))
			mi(head, rbox(Vector3(0.1, 0.1, 0.05), 0.02), m, Vector3(0.27, 0.14, -0.1), Vector3(0, 0, 45))
		"tall":
			mi(head, cyl(0.2, 0.2, 0.5), m, Vector3(0, 0.38, 0))
			mi(head, cyl(0.205, 0.205, 0.07), mat("000000", 0.7), Vector3(0, 0.22, 0)).material_override = mat(hex, 0.7)
		_:
			mi(head, sphere(0.3, true), m, Vector3(0, 0.07, 0), Vector3(0, 0, 0), Vector3(1.0, 1.0, 1.0))
			mi(head, rbox(Vector3(0.5, 0.1, 0.12), 0.04), m, Vector3(0, 0.15, 0.2), Vector3(-15, 0, 0))


static func stool() -> Node3D:
	var r := Node3D.new()
	r.name = "stool"
	mi(r, cyl(0.2, 0.2, 0.07), mat("c0392b", 0.5), Vector3(0, 0.62, 0))
	mi(r, cyl(0.04, 0.04, 0.58), mat("9aa3b8", 0.3, 0.8), Vector3(0, 0.3, 0))
	mi(r, torus(0.17, 0.21), mat("9aa3b8", 0.3, 0.8), Vector3(0, 0.05, 0))
	return r


# customer on a bar stool (looks 0..5); the origin is the stool's position on the floor
const CUST_SKIN := ["ffd5b5", "f1c27d", "a8714a", "d9a066", "7a4a2d", "ffe0c8"]
const CUST_HAIR := ["3b2f2f", "f4d35e", "1f1f24", "a0522d", "1f1f24", "8338ec"]
const CUST_SHIRT := ["ef476f", "06d6a0", "118ab2", "ffd166", "9b5de5", "ff9f1c"]


static func customer(look: int, vip: bool) -> Node3D:
	_clean = true
	var r := _customer(look, vip)
	_clean = false
	return r


static func _customer(look: int, vip: bool) -> Node3D:
	var root := Node3D.new()
	root.name = "customer"
	var skin: String = CUST_SKIN[look % 6]
	var hair: String = CUST_HAIR[look % 6]
	var shirt: String = CUST_SHIRT[look % 6]
	for sx in [-1.0, 1.0]:
		mi(root, capsule(0.085, 0.42), mat("3b4466", 0.7), Vector3(sx * 0.13, 0.46, 0.16), Vector3(90, 0, 0))
		mi(root, capsule(0.075, 0.38), mat("3b4466", 0.7), Vector3(sx * 0.13, 0.22, 0.36))
	var body := node(root, "body", Vector3(0, 0.52, 0))
	mi(body, capsule(0.25, 0.6), mat(shirt, 0.65), Vector3(0, 0.22, 0), Vector3.ZERO, Vector3(1.0, 1.0, 0.9))
	for sx in [-1.0, 1.0]:
		var arm := node(body, "arm_l" if sx < 0 else "arm_r", Vector3(sx * 0.27, 0.4, 0))
		mi(arm, capsule(0.08, 0.34), mat(shirt, 0.65), Vector3(sx * 0.02, -0.12, 0.08), Vector3(-50, 0, sx * 6))
		mi(arm, sphere(0.09), mat(skin, 0.5), Vector3(sx * 0.04, -0.27, 0.2))
	var head := node(root, "head", Vector3(0, 1.22, 0))
	mi(head, sphere(0.285), mat(skin, 0.45), Vector3.ZERO, Vector3.ZERO, Vector3(1.0, 0.94, 0.96))
	for sx in [-1.0, 1.0]:
		mi(head, sphere(0.06), mat(skin, 0.45), Vector3(sx * 0.28, -0.01, 0.0))
	mi(head, sphere(0.045), mat(skin, 0.4), Vector3(0, -0.04, 0.27))
	decal(head, "eyes_open", 0.42, Vector3(0, 0.03, 0.29), "eyes")
	decal(head, "mouth_smile", 0.14, Vector3(0, -0.115, 0.275), "mouth")
	var hm := mat(hair, 0.55)
	match look % 6:
		0:   # short hair with a fringe
			mi(head, sphere(0.3, true), hm, Vector3(0, 0.05, -0.02), Vector3.ZERO, Vector3(1.0, 1.0, 1.0))
			mi(head, rbox(Vector3(0.4, 0.07, 0.1), 0.03), hm, Vector3(0.0, 0.17, 0.22), Vector3(-20, 0, 8))
		1:   # top bun
			mi(head, sphere(0.3, true), hm, Vector3(0, 0.05, -0.02))
			mi(head, sphere(0.13), hm, Vector3(0, 0.37, -0.02))
		2:   # long hair
			mi(head, sphere(0.3, true), hm, Vector3(0, 0.05, -0.02))
			mi(head, capsule(0.27, 0.6), hm, Vector3(0, -0.15, -0.14), Vector3.ZERO, Vector3(1.0, 1.0, 0.7))
		3:   # red cap
			mi(head, sphere(0.3, true), mat("ef476f", 0.5), Vector3(0, 0.06, 0))
			mi(head, rbox(Vector3(0.3, 0.03, 0.22), 0.015), mat("d63a5c", 0.5), Vector3(0, 0.1, 0.32), Vector3(-6, 0, 0))
		4:   # afro
			mi(head, sphere(0.4), hm, Vector3(0, 0.12, -0.08), Vector3.ZERO, Vector3(1.0, 0.95, 0.95))
		_:   # spiky
			mi(head, sphere(0.3, true), hm, Vector3(0, 0.05, -0.02))
			for i in 5:
				var a := (i - 2) * 0.5
				mi(head, cyl(0.0, 0.06, 0.2), hm, Vector3(sin(a) * 0.22, 0.34 - absf(a) * 0.05, -0.04), Vector3(0, 0, -a * 50))
	if vip:
		mi(head, cyl(0.2, 0.2, 0.12), mat("ffd23f", 0.25, 0.7), Vector3(0, 0.38, 0))
		for i in 5:
			var a := i * TAU / 5.0
			mi(head, cyl(0.0, 0.05, 0.12), mat("ffd23f", 0.25, 0.7), Vector3(cos(a) * 0.17, 0.5, sin(a) * 0.17))
		mi(head, sphere(0.04), mat("ef476f", 0.3, 0.0, 0.8), Vector3(0, 0.4, 0.21))
	return root


# ====================================================================
# Decoration
# ====================================================================

static func plant() -> Node3D:
	var r := Node3D.new()
	mi(r, cyl(0.22, 0.17, 0.3), mat("c2603a", 0.6), Vector3(0, 0.15, 0))
	for i in 7:
		var a := i * TAU / 7.0
		mi(r, sphere(0.16), mat("4f9a3a" if i % 2 == 0 else "6ab84a", 0.5), Vector3(cos(a) * 0.14, 0.45 + (i % 3) * 0.07, sin(a) * 0.14))
	mi(r, sphere(0.2), mat("5faa42", 0.5), Vector3(0, 0.6, 0))
	return r


static func table_and_chairs() -> Node3D:
	var r := Node3D.new()
	mi(r, cyl(0.04, 0.04, 0.6), mat("8d5629", 0.6), Vector3(0, 0.3, 0))
	mi(r, cyl(0.5, 0.5, 0.06), mat("e4b27c", 0.4), Vector3(0, 0.63, 0))
	mi(r, cyl(0.48, 0.48, 0.02), mat("ffffff", 0.6), Vector3(0, 0.665, 0))
	mi(r, cyl(0.22, 0.22, 0.04), mat("c0392b", 0.5), Vector3(0, 0.685, 0))
	for i in 2:
		var s := -1.0 if i == 0 else 1.0
		var c := node(r, "chair", Vector3(s * 0.72, 0, 0))
		c.rotation_degrees = Vector3(0, 90 * s, 0)
		mi(c, rbox(Vector3(0.4, 0.06, 0.4), 0.03), mat("a8693a", 0.6), Vector3(0, 0.38, 0))
		mi(c, rbox(Vector3(0.4, 0.4, 0.05), 0.03), mat("a8693a", 0.6), Vector3(0, 0.62, -0.19))
		for sx in [-1.0, 1.0]:
			for sz in [-1.0, 1.0]:
				mi(c, cyl(0.025, 0.025, 0.36), mat("8d5629", 0.7), Vector3(sx * 0.16, 0.18, sz * 0.16))
	return r


static func lamp(hex: String = "ff8a5c") -> Node3D:
	var r := Node3D.new()
	mi(r, cyl(0.014, 0.014, 3.4), mat("1c1c26", 0.5), Vector3(0, 1.7, 0))
	mi(r, sphere(0.2, true), mat(hex, 0.4), Vector3(0, -0.02, 0), Vector3.ZERO, Vector3(1, 0.9, 1))
	mi(r, sphere(0.09), mat("fff1c0", 0.3, 0.0, 3.0), Vector3(0, -0.04, 0))
	return r


static func shelf() -> Node3D:
	var r := Node3D.new()
	mi(r, rbox(Vector3(1.2, 0.06, 0.28), 0.02), mat(WOOD, 0.7), Vector3(0, 0, 0))
	for i in 3:
		var col: String = ["ef476f", "ffd166", "7bc043"][i]
		mi(r, cyl(0.09, 0.09, 0.22), mat(col, 0.3), Vector3(-0.38 + i * 0.38, 0.14, 0))
		mi(r, cyl(0.07, 0.07, 0.05), mat("dfe5f2", 0.3, 0.6), Vector3(-0.38 + i * 0.38, 0.27, 0))
	return r


static func hanging_pan() -> Node3D:
	var r := Node3D.new()
	mi(r, cyl(0.2, 0.17, 0.07), mat("4a5268", 0.35, 0.7), Vector3(0, 0, 0), Vector3(90, 0, 0))
	mi(r, rbox(Vector3(0.05, 0.04, 0.34), 0.015), mat("8d5629", 0.7), Vector3(0, 0, 0.4), Vector3(0, 0, 0))
	return r


static func clock() -> Node3D:
	var r := Node3D.new()
	mi(r, cyl(0.26, 0.26, 0.05), mat("dfe3ee", 0.3), Vector3(0, 0, 0), Vector3(90, 0, 0))
	mi(r, cyl(0.22, 0.22, 0.06), mat("f8fafc", 0.4), Vector3(0, 0, 0.005), Vector3(90, 0, 0))
	mi(r, rbox(Vector3(0.02, 0.15, 0.015), 0.005), mat("2a2c3a", 0.4), Vector3(0, 0.06, 0.04))
	mi(r, rbox(Vector3(0.13, 0.02, 0.015), 0.005), mat("2a2c3a", 0.4), Vector3(0.05, 0, 0.045))
	return r


# ---- curved counters: rounded counter ends and corners (a 2D shape extruded) ----
static func _extrude(poly: PackedVector2Array, y0: float, y1: float) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var c := Vector2.ZERO
	for p in poly:
		c += p
	c /= float(poly.size())
	for i in poly.size():
		var a := poly[i]
		var b := poly[(i + 1) % poly.size()]
		# top (the material is double sided, so winding does not matter)
		st.set_normal(Vector3.UP)
		st.add_vertex(Vector3(c.x, y1, c.y))
		st.add_vertex(Vector3(a.x, y1, a.y))
		st.add_vertex(Vector3(b.x, y1, b.y))
		# side
		var n := Vector3(b.y - a.y, 0, -(b.x - a.x)).normalized()
		st.set_normal(n)
		st.add_vertex(Vector3(a.x, y0, a.y))
		st.add_vertex(Vector3(a.x, y1, a.y))
		st.add_vertex(Vector3(b.x, y1, b.y))
		st.add_vertex(Vector3(a.x, y0, a.y))
		st.add_vertex(Vector3(b.x, y1, b.y))
		st.add_vertex(Vector3(b.x, y0, b.y))
	return st.commit()


static func counter_round(shape: String, yaw_deg: float) -> Node3D:
	var poly := PackedVector2Array()
	if shape == "end":      # neighbour on +x, rounded bullnose at the other end
		poly.append(Vector2(0.5, -0.5))
		poly.append(Vector2(0.5, 0.5))
		poly.append(Vector2(0.0, 0.5))
		for i in range(1, 12):
			var a := PI / 2.0 + PI * float(i) / 12.0
			poly.append(Vector2(cos(a) * 0.5, sin(a) * 0.5))
		poly.append(Vector2(0.0, -0.5))
	else:                   # corner: neighbours on +x and +z, quarter-disc outside corner
		poly.append(Vector2(0.5, 0.5))
		for i in range(0, 13):
			var a := PI + (PI / 2.0) * float(i) / 12.0
			poly.append(Vector2(0.5 + cos(a), 0.5 + sin(a)))
	var root := Node3D.new()
	root.name = "station_X"
	var body_m := mat("bfc4cf", 0.6).duplicate() as StandardMaterial3D
	body_m.cull_mode = BaseMaterial3D.CULL_DISABLED
	var top_m := mat("c9985a", 0.6).duplicate() as StandardMaterial3D
	top_m.cull_mode = BaseMaterial3D.CULL_DISABLED
	var body := mi(root, _extrude(poly, 0.0, TOP - 0.06), body_m)
	var top := mi(root, _extrude(poly, TOP - 0.06, TOP), top_m)
	body.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	root.rotation_degrees.y = yaw_deg
	return root
