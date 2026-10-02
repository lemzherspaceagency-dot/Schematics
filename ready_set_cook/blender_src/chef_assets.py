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


def build_base():
    reset()
    root = empty("chef", (0, 0, 0))
    parts = [root]

    def add(o, par):
        parent(o, par)
        parts.append(o)
        return o

    # feet + legs
    for sx, nm in ((-1, "foot_l"), (1, "foot_r")):
        f = empty(nm, (sx * 0.13, -0.05, 0.07))
        parts.append(f)
        parent(f, root)
        add(blob(0.15, (sx * 0.13, -0.05, 0.075), BLACK(), (0.78, 1.18, 0.55), 0.06, 2.2, 3 + sx, "shoe", 3), f)
        lg = empty("leg_l" if sx < 0 else "leg_r", (sx * 0.13, 0, 0.27))
        parts.append(lg)
        parent(lg, root)
        add(blob(0.1, (sx * 0.13, 0, 0.27), BLACK(), (1, 1, 1.5), 0.05, 2.0, 9 + sx, "leg", 3), lg)
    # body
    body = empty("body", (0, 0, 0.46))
    parts.append(body)
    parent(body, root)
    add(blob(0.32, (0, 0, 0.62), WHITE(), (1.0, 0.9, 1.12), 0.06, 1.6, 5, "jacket", 4), body)
    add(blob(0.22, (0, 0, 0.9), WHITE(), (1.25, 1.0, 0.45), 0.05, 2.4, 6, "collar", 3), body)
    for i in range(3):
        for sx in (-1, 1):
            add(sphere(0.034, (sx * 0.1, -0.28, 0.76 - i * 0.12), DARK(), name="button"), body)
    add(box((0.014, 0.02, 0.4), (0, -0.295, 0.62), mat("c2c6d2", 0.8), 0.006, name="seam"), body)
    for sx, nm in ((-1, "arm_l"), (1, "arm_r")):
        a = empty(nm, (sx * 0.36, 0, 0.84))
        parts.append(a)
        parent(a, body)
        add(blob(0.115, (sx * 0.39, 0, 0.67), WHITE(), (1, 1, 1.9), 0.05, 2.0, 11 + sx, "sleeve", 3), a)
        add(cyl(0.12, 0.125, 0.07, (sx * 0.41, 0, 0.5), WHITE(), 24, name="cuff"), a)
        add(blob(0.12, (sx * 0.43, -0.02, 0.44), skin_mat(), (1, 1, 1), 0.05, 2.2, 15 + sx, "hand", 3), a)
    # head
    head = empty("head", (0, 0, 1.02))
    parts.append(head)
    parent(head, root)
    add(blob(0.37, (0, 0, 1.02), skin_mat(), (1.04, 0.98, 0.95), 0.035, 1.8, 21, "skull", 4), head)
    for sx in (-1, 1):
        add(blob(0.075, (sx * 0.37, 0, 1.0), skin_mat(), (0.7, 0.9, 1.1), 0.05, 2.0, 22 + sx, "ear", 3), head)
    add(blob(0.09, (0, -0.35, 0.98), skin_mat(), (1, 0.95, 0.95), 0.05, 2.0, 31, "nose", 3), head)
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
    out = [cyl(0.29, 0.3, 0.16, (0, 0, 0.3), m, 36, name="band")]
    for (x, y, z, r, s) in [(-0.15, 0, 0.55, 0.24, 1), (0.15, 0, 0.55, 0.24, 2), (0, 0.1, 0.56, 0.22, 3), (0, -0.1, 0.56, 0.22, 4), (0, 0, 0.7, 0.27, 5)]:
        out.append(blob(r, (x, y, z), m, (1, 1, 0.95), 0.1, 2.2, s, "puff", 3))
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
