"""Assemble the game's models from the CC0 packs (KayKit Restaurant Bits, Kenney Food Kit) into GLBs under ../assets/.
Set PACKS to the folder that holds the unzipped packs. Everything is scaled by 0.5 so KayKit's 2x2 pieces fit one tile."""
import os, sys, glob, math
import bpy
from lib import reset, export, mat, box, cyl, sphere, torus, empty, parent

PACKS = os.environ.get("PACKS", "/tmp/packs")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
S = 0.5
SZ = (0.5, 0.5, 0.75)   # stations: half size on the floor, but a bit taller so they read chunky from above

KAY = glob.glob(os.path.join(PACKS, "KayKit*", "*", "Assets", "gltf"))[0]
KEN = glob.glob(os.path.join(PACKS, "kenney_food-kit", "Models", "GLB*"))[0]


def imp(path, name, loc=(0, 0, 0), rot_z=0.0, scale=S):
    """import a gltf/glb and put all its objects under one empty named `name`"""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    root = empty(name, loc)
    root.rotation_euler = (0, 0, math.radians(rot_z))
    root.scale = scale if isinstance(scale, tuple) else (scale, scale, scale)
    for o in new:
        if o.parent is None or o.parent not in new:
            o.parent = root
    return root


def kay(model, name=None, loc=(0, 0, 0), rot_z=0.0, scale=S):
    return imp(os.path.join(KAY, model + ".gltf"), name or model, loc, rot_z, scale)


def ken(model, name=None, loc=(0, 0, 0), rot_z=0.0, scale=S):
    return imp(os.path.join(KEN, model + ".glb"), name or model, loc, rot_z, scale)


def objs_all():
    return [o for o in bpy.data.objects]


def save(name):
    export(os.path.join(OUT, name + ".glb"), objs_all())
    print("wrote", name)


def bounds(root):
    """world-space bounding box (min, max) of all meshes under root"""
    from mathutils import Vector
    bpy.context.view_layer.update()
    pts = []
    stack = [root]
    while stack:
        o = stack.pop()
        stack.extend(o.children)
        if o.type == 'MESH':
            for c in o.bound_box:
                pts.append(o.matrix_world @ Vector(c))
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def fit(root, size, loc=(0, 0, 0), rot_z=0.0):
    """scale so the footprint's longest side == size, centre it on x/y and rest it on z = loc[2]"""
    root.scale = (1, 1, 1)
    root.location = (0, 0, 0)
    mn, mx = bounds(root)
    s = size / max(mx[0] - mn[0], mx[1] - mn[1])
    root.scale = (s, s, s)
    root.location = (loc[0] - (mn[0] + mx[0]) / 2 * s, loc[1] - (mn[1] + mx[1]) / 2 * s, loc[2] - mn[2] * s)
    return root
