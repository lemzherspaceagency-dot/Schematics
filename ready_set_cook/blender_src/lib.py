"""Blender helpers for building the game's 3D models with `python3 make_assets.py` (needs `pip install bpy`).
1 Blender unit = 1 kitchen tile. Models face -Y in Blender (= +Z in the glTF/Godot export), origin at the floor centre."""
import bpy, bmesh, math, random
from mathutils import Vector, noise

_mats = {}


def lin(c):
    return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92


def srgb(h):
    h = h.lstrip("#")
    return tuple(lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4)) + (1.0,)


def mat(hex, rough=0.6, metal=0.0, emit=0.0, name=None):
    key = (hex, rough, metal, emit)
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(name or ("m_%s" % hex))
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = srgb(hex)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit > 0:
        b.inputs["Emission Color"].default_value = srgb(hex)
        b.inputs["Emission Strength"].default_value = emit
    _mats[key] = m
    return m


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _mats.clear()


def _finish(o, m, bevel=0.0, smooth=True, seg=3, angle=40):
    if m is not None:
        o.data.materials.clear()
        o.data.materials.append(m)
    if bevel > 0:
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        md = o.modifiers.new("bevel", "BEVEL")
        md.width = bevel
        md.segments = seg
        md.limit_method = "ANGLE"
        md.angle_limit = math.radians(angle)
        bpy.ops.object.modifier_apply(modifier="bevel")
    if smooth:
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        try:
            bpy.ops.object.shade_smooth_by_angle(angle=math.radians(50))
        except Exception:
            bpy.ops.object.shade_smooth()
    o.select_set(False)
    return o


def box(size, loc=(0, 0, 0), m=None, bevel=0.04, rot=(0, 0, 0), name="box"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=[math.radians(r) for r in rot])
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    return _finish(o, m, bevel)


def cyl(r1, r2, h, loc=(0, 0, 0), m=None, verts=32, bevel=0.0, rot=(0, 0, 0), name="cyl"):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=h, location=loc, rotation=[math.radians(r) for r in rot])
    o = bpy.context.active_object
    o.name = name
    return _finish(o, m, bevel)


def sphere(r, loc=(0, 0, 0), m=None, scale=(1, 1, 1), seg=32, name="sphere", hemi=False):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=r, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    if hemi:
        bpy.context.view_layer.objects.active = o
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(loc[0], loc[1], loc[2]), plane_no=(0, 0, 1), clear_inner=True)
        cap = [e for e in bm.edges if e.is_boundary]
        if cap:
            bmesh.ops.holes_fill(bm, edges=cap)
        bm.to_mesh(o.data)
        bm.free()
    return _finish(o, m, 0.0)


def torus(major, minor, loc=(0, 0, 0), m=None, rot=(0, 0, 0), name="torus", scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=40, minor_segments=14, location=loc, rotation=[math.radians(r) for r in rot])
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    return _finish(o, m, 0.0)


def blob(r, loc=(0, 0, 0), m=None, scale=(1, 1, 1), amount=0.08, freq=2.5, seed=1, name="blob", subd=3):
    """organic lump: subdivided icosphere pushed around with noise (cabbages, dough, meat, lumps)"""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subd, radius=r, location=(0, 0, 0))
    o = bpy.context.active_object
    o.name = name
    for v in o.data.vertices:
        p = v.co.copy()
        n = noise.noise(p * freq + Vector((seed * 7.1, seed * 3.3, seed * 1.7)))
        v.co = p * (1.0 + amount * n)
    o.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    o.location = loc
    return _finish(o, m, 0.0)


def join(objs, name):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.active_object
    o.name = name
    o.select_set(False)
    return o


def empty(name, loc=(0, 0, 0)):
    o = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(o)
    o.location = loc
    return o


def parent(child, par):
    child.parent = par
    child.matrix_parent_inverse = par.matrix_world.inverted()


def export(path, objs=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in (objs if objs is not None else bpy.data.objects):
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
                              export_materials="EXPORT", export_lights=False, export_cameras=False)
