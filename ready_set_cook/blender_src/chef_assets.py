"""Clay-style chunky chefs, modelled in Blender. Run: python3 chef_assets.py
Writes ../assets/chef_base.glb and ../assets/hat_<style>.glb.
Node names are the rig the game animates (body, arm_l/r, head, foot_l/r, leg_l/r). Materials named
'skin' and 'hatcol' are recoloured per player in the game. Blender: front = -Y, up = +Z."""
import os, math
import bpy
from lib import *

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")


def named(m, name):
    m.name = name
    return m


def skin_mat():
    return named(mat("ffd5b5", 0.8), "skin")


def hat_mat():
    return named(mat("fefefe", 0.85), "hatcol")


WHITE = lambda: mat("f4f4f8", 0.9)
BLACK = lambda: mat("2a2a33", 0.7)
DARK = lambda: mat("30303a", 0.5)


def sc(o, s):
    """scale an object and bake it in"""
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    o.scale = s
    bpy.ops.object.transform_apply(scale=True)
    o.select_set(False)
    return o


def build_base():
    reset()
    root = empty("chef", (0, 0, 0))
    parts = [root]

    def add(o, par):
        parent(o, par)
        parts.append(o)
        return o

    WH, BK, DK, SK = WHITE(), BLACK(), DARK(), skin_mat()
    SOLE = mat("e8e2d4", 0.8)
    BROW = mat("4a2e1c", 0.8)
    # ---- feet (chunky clog with a sole) and baggy trousers
    for sx, nm in ((-1, "foot_l"), (1, "foot_r")):
        f = empty(nm, (sx * 0.14, -0.06, 0.07))
        parts.append(f)
        parent(f, root)
        add(box((0.2, 0.36, 0.13), (sx * 0.14, -0.08, 0.085), BK, 0.055, name="shoe"), f)
        add(sphere(0.105, (sx * 0.14, -0.2, 0.09), BK, (1.0, 1.0, 0.8), name="toe"), f)
        add(box((0.215, 0.4, 0.035), (sx * 0.14, -0.08, 0.018), SOLE, 0.012, name="sole"), f)
        lg = empty("leg_l" if sx < 0 else "leg_r", (sx * 0.14, 0, 0.27))
        parts.append(lg)
        parent(lg, root)
        add(cyl(0.115, 0.15, 0.34, (sx * 0.14, 0, 0.3), BK, 24, 0.02, name="trouser"), lg)
    # ---- torso: broad shoulders, flared jacket hem, collar, double-breasted front
    body = empty("body", (0, 0, 0.46))
    parts.append(body)
    parent(body, root)
    add(sc(cyl(0.34, 0.4, 0.55, (0, 0, 0.7), WH, 28, 0.05, name="jacket"), (1.0, 0.82, 1.0)), body)
    add(sc(cyl(0.43, 0.37, 0.14, (0, 0, 0.42), WH, 28, 0.04, name="hem"), (1.0, 0.84, 1.0)), body)
    add(cyl(0.12, 0.13, 0.1, (0, 0, 1.0), SK, 20, name="neck"), body)
    add(sc(torus(0.17, 0.065, (0, 0, 0.97), WH, name="collar"), (1.0, 0.85, 0.9)), body)
    for sx in (-1, 1):
        add(box((0.2, 0.035, 0.46), (sx * 0.1, -0.285, 0.72), mat("e4e7ef", 0.8), 0.015, (0, 0, sx * -9), "lapel"), body)
        for i in range(3):
            add(sphere(0.034, (sx * 0.13, -0.312, 0.88 - i * 0.14), DK, name="button"), body)
    # arms: sleeves with turned-up cuffs and mitten hands with a thumb
    for sx, nm in ((-1, "arm_l"), (1, "arm_r")):
        a = empty(nm, (sx * 0.4, 0, 0.9))
        parts.append(a)
        parent(a, body)
        add(cyl(0.12, 0.105, 0.42, (sx * 0.43, 0, 0.69), WH, 22, 0.03, (0, sx * 7, 0), "sleeve"), a)
        add(cyl(0.125, 0.125, 0.07, (sx * 0.455, 0, 0.5), mat("e4e7ef", 0.8), 22, 0.02, (0, sx * 7, 0), "cuff"), a)
        add(blob(0.115, (sx * 0.465, -0.02, 0.43), SK, (1, 1, 0.95), 0.03, 2.0, 15 + sx, "mitt", 3), a)
        add(blob(0.05, (sx * 0.4, -0.1, 0.45), SK, (1, 1.3, 1), 0.02, 2.0, 17 + sx, "thumb", 2), a)
    # ---- head: a big squarish head with a jaw, ears, brow, a long nose
    HZ = 1.24
    head = empty("head", (0, 0, HZ))
    parts.append(head)
    parent(head, root)
    add(sc(sphere(0.37, (0, 0, HZ), SK, name="skull"), (1.05, 0.98, 0.94)), head)
    add(sc(sphere(0.27, (0, -0.04, HZ - 0.14), SK, name="jaw"), (1.1, 1.0, 0.8)), head)
    for sx in (-1, 1):
        add(sc(sphere(0.085, (sx * 0.385, 0.0, HZ - 0.02), SK, name="ear"), (0.45, 0.9, 1.1)), head)
        add(box((0.17, 0.05, 0.055), (sx * 0.12, -0.34, HZ + 0.15), BROW, 0.02, (0, sx * 12, 0), "brow"), head)
        add(sphere(0.075, (sx * 0.2, -0.27, HZ - 0.2), SK, name="cheek"), head)
    add(cyl(0.08, 0.045, 0.18, (0, -0.35, HZ - 0.05), SK, 18, 0.02, (90, 0, 0), "nose"), head)
    add(sphere(0.065, (0, -0.45, HZ - 0.06), SK, name="nose_tip"), head)
    export(os.path.join(OUT, "chef_base.glb"), parts)
    print("wrote chef_base")


def hat(name, builder):
    reset()
    h = empty("hat", (0, 0, 0))
    parts = [h]
    for o in builder():
        parent(o, h)
        parts.append(o)
    export(os.path.join(OUT, "hat_%s.glb" % name), parts)
    print("wrote hat", name)


def toque():
    m = hat_mat()
    out = [cyl(0.31, 0.32, 0.17, (0, 0, 0.27), m, 14, 0.02, name="band"),
           cyl(0.3, 0.36, 0.2, (0, 0, 0.45), m, 14, 0.015, name="pleats"),
           sc(sphere(0.42, (0, 0, 0.58), m, name="puff"), (1.0, 1.0, 0.55))]
    for (x, y, s) in [(-0.2, 0.05, 1), (0.2, -0.03, 2), (0.0, 0.2, 3)]:
        out.append(blob(0.15, (x, y, 0.66), m, (1, 1, 0.8), 0.12, 2.2, s, "fold", 3))
    return out


def cap():
    m = hat_mat()
    return [blob(0.4, (0, 0, 0.08), m, (1, 1, 0.78), 0.03, 1.8, 7, "dome", 4),
            box((0.42, 0.28, 0.035), (0, -0.4, 0.14), m, 0.015, name="brim"),
            sphere(0.04, (0, 0, 0.4), m, name="button")]


def beanie():
    m = hat_mat()
    return [blob(0.4, (0, 0, 0.12), m, (1, 1, 0.85), 0.04, 2.0, 8, "dome", 4),
            torus(0.33, 0.07, (0, 0, 0.1), m, name="roll", scale=(1, 1, 1.1)),
            blob(0.1, (0, 0, 0.5), m, (1, 1, 1), 0.1, 2.5, 9, "pom", 3)]


def bandana():
    m = hat_mat()
    return [blob(0.385, (0, 0, 0.1), m, (1, 1, 0.55), 0.03, 1.8, 10, "wrap", 4),
            blob(0.1, (0, 0.38, 0.15), m, (1.3, 0.6, 0.9), 0.1, 2.0, 11, "knot", 3)]


def tall():
    m = hat_mat()
    return [cyl(0.25, 0.26, 0.72, (0, 0, 0.58), m, 36, 0.03, name="stack"),
            cyl(0.265, 0.265, 0.08, (0, 0, 0.3), mat("2a2a33", 0.8), 36, name="band")]


def hair():
    m = hat_mat()
    return [blob(0.39, (0, 0.02, 0.1), m, (1.05, 1.0, 0.8), 0.07, 2.4, 12, "mop", 4),
            blob(0.16, (-0.05, -0.3, 0.3), m, (1.4, 0.8, 0.9), 0.1, 2.5, 13, "fringe", 3)]


if __name__ == "__main__":
    build_base()
    for n, f in [("toque", toque), ("cap", cap), ("beanie", beanie), ("bandana", bandana), ("tall", tall), ("hair", hair)]:
        hat(n, f)
