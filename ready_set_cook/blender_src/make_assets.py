"""Builds the game's GLB models into ../assets/. Run: python3 make_assets.py [name ...]"""
import os, sys, math
import bpy
from lib import *

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
os.makedirs(OUT, exist_ok=True)
MODELS = {}


def model(fn):
    MODELS[fn.__name__] = fn
    return fn


def finish(name, parts):
    path = os.path.join(OUT, name + ".glb")
    export(path, parts)
    print("wrote", name, len(parts), "parts")


WOOD, WOOD_DARK, WOOD_LIGHT = "b57a3e", "93582a", "d9b57e"


def counter_parts(top="d99a4a", body=WOOD_DARK, h=0.8):
    p = []
    p.append(box((0.96, 0.96, h), (0, 0, h / 2), mat(body, 0.75), 0.07, name="body"))
    p.append(box((1.0, 1.0, 0.1), (0, 0, h + 0.03), mat(top, 0.45), 0.045, name="top"))
    # drawer front and handle
    p.append(box((0.8, 0.02, 0.28), (0, -0.485, h * 0.55), mat("7a4620", 0.8), 0.02, name="drawer"))
    p.append(box((0.22, 0.03, 0.03), (0, -0.505, h * 0.62), mat("e9edf5", 0.25, 0.9), 0.012, name="handle"))
    return p


def drawer_counter(top, body, h=0.8):
    return counter_parts(top, body, h)


@model
def counter():
    finish("counter", counter_parts())


@model
def table():
    p = []
    wood = mat("7b4a26", 0.7)
    p.append(cyl(0.3, 0.3, 0.05, (0, 0, 0.03), wood, 40, 0.01, name="foot"))
    p.append(cyl(0.07, 0.1, 0.66, (0, 0, 0.36), wood, 24, 0.01, name="stem"))
    p.append(box((0.98, 0.98, 0.07), (0, 0, 0.7), mat("d9a35e", 0.55), 0.04, name="top"))
    p.append(box((0.94, 0.94, 0.025), (0, 0, 0.745), mat("c0392b", 0.85), 0.012, name="cloth"))
    p.append(box((0.46, 0.46, 0.012), (0, 0, 0.76), mat("f6f1e6", 0.85), 0.004, rot=(0, 0, 45), name="napkin"))
    p.append(cyl(0.13, 0.11, 0.025, (0, -0.18, 0.775), mat("f6f8fc", 0.25), 32, 0.005, name="plate"))
    p.append(cyl(0.05, 0.045, 0.1, (0.3, 0.28, 0.82), mat("bfe3ef", 0.15), 20, 0.004, name="glass"))
    p.append(box((0.03, 0.2, 0.012), (-0.2, -0.18, 0.766), mat("dfe5f2", 0.2, 0.9), 0.004, name="fork"))
    finish("table", p)


@model
def chair():
    p = []
    red = mat("b8402f", 0.6)
    leg = mat("5a2a1e", 0.7)
    p.append(box((0.62, 0.6, 0.09), (0, 0, 0.44), red, 0.04, name="seat"))
    p.append(box((0.54, 0.5, 0.04), (0, -0.02, 0.5), mat("d8573f", 0.7), 0.02, name="cushion"))
    p.append(box((0.62, 0.08, 0.5), (0, 0.28, 0.74), red, 0.04, name="back"))
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.append(cyl(0.035, 0.03, 0.42, (sx * 0.25, sy * 0.24, 0.21), leg, 12, name="leg"))
    finish("chair", p)


def crate_body(fill_hex):
    p = []
    wood = mat(WOOD, 0.8)
    dark = mat("8d5629", 0.85)
    p.append(box((0.9, 0.9, 0.5), (0, 0, 0.25), wood, 0.05, name="box"))
    for z in (0.12, 0.3):
        p.append(box((0.94, 0.94, 0.05), (0, 0, z), dark, 0.02, name="slat"))
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.append(box((0.1, 0.1, 0.52), (sx * 0.42, sy * 0.42, 0.26), dark, 0.03, name="post"))
    p.append(box((0.78, 0.78, 0.04), (0, 0, 0.5), mat(fill_hex, 0.95), 0.02, name="fill"))
    return p


@model
def crate_veg():
    p = crate_body("254a1e")
    p.append(blob(0.2, (-0.18, 0.1, 0.68), mat("86c04a", 0.5), (1, 1, 0.92), 0.07, 3.0, 1, "cabbage"))
    p.append(blob(0.12, (-0.22, 0.12, 0.76), mat("a8d870", 0.5), (1, 1, 0.8), 0.06, 4.0, 2, "cabbage_top"))
    p.append(blob(0.15, (0.2, 0.12, 0.64), mat("e24a3a", 0.3), (1, 1, 0.9), 0.03, 2.0, 3, "tomato"))
    p.append(blob(0.17, (0.0, -0.2, 0.65), mat("9fd45c", 0.5), (1, 1, 0.9), 0.07, 3.0, 4, "cabbage2"))
    for i in range(3):
        p.append(cyl(0.05, 0.0, 0.32, (0.26 + i * 0.05, -0.14 + i * 0.07, 0.62), mat("f08a2a", 0.5), 16, rot=(70, i * 20, 80), name="carrot"))
    finish("crate_veg", p)


@model
def crate_meat():
    p = crate_body("4a2a1a")
    spots = [(-0.2, 0.12, 0.6, -18), (0.18, 0.15, 0.62, 12), (0.0, -0.18, 0.62, 6), (-0.22, -0.2, 0.6, 20), (0.26, -0.18, 0.6, -10)]
    for i, (x, y, z, r) in enumerate(spots):
        p.append(blob(0.17, (x, y, z), mat("e5707e", 0.35), (1.15, 0.85, 0.42), 0.05, 2.5, i + 1, "steak"))
        p.append(blob(0.07, (x + 0.05, y - 0.02, z + 0.06), mat("ffe4e8", 0.4), (1.2, 1, 0.4), 0.04, 3.0, i + 9, "fat"))
    finish("crate_meat", p)


@model
def crate_dough():
    p = crate_body("6b5130")
    for i, (x, y, z, r) in enumerate([(-0.2, 0.1, 0.66, 0.2), (0.18, 0.14, 0.68, 0.22), (0.0, -0.2, 0.65, 0.2)]):
        p.append(blob(r, (x, y, z), mat("f6ead0", 0.75), (1, 1, 0.85), 0.05, 2.0, i + 3, "dough"))
    p.append(box((0.5, 0.3, 0.012), (0.1, 0.0, 0.502), mat("ffffff", 0.9), 0.004, rot=(0, 0, 15), name="flour"))
    finish("crate_dough", p)


@model
def chop_board():
    p = counter_parts("d9a066", WOOD_DARK)
    p.append(box((0.82, 0.64, 0.06), (0, 0, 0.9), mat(WOOD_LIGHT, 0.5), 0.025, name="board"))
    for i in range(3):
        p.append(box((0.7, 0.012, 0.012), (0, -0.2 + i * 0.2, 0.935), mat("b98350", 0.7), 0.004, name="groove"))
    p.append(box((0.34, 0.08, 0.012), (0.12 - 0.18, 0.12, 0.95), mat("dfe5ee", 0.2, 0.9), 0.004, rot=(0, 0, 30), name="blade"))
    p.append(box((0.16, 0.05, 0.03), (-0.3, 0.2, 0.96), mat("6b3f1d", 0.6), 0.012, rot=(0, 0, 30), name="handle"))
    for i, c in enumerate(["7bc043", "f7a541", "e84f3d"]):
        p.append(cyl(0.05, 0.05, 0.015, (0.28 + i * 0.05, -0.2 + i * 0.03, 0.94), mat(c, 0.5), 20, name="slice"))
    finish("chop_board", p)


@model
def stove():
    p = []
    p.append(box((0.96, 0.96, 0.8), (0, 0, 0.4), mat("5b6078", 0.4, 0.4), 0.07, name="body"))
    p.append(box((1.0, 1.0, 0.08), (0, 0, 0.82), mat("2a2c3a", 0.35, 0.3), 0.03, name="top"))
    p.append(torus(0.27, 0.05, (0, 0, 0.88), mat("1b1c26", 0.4, 0.5), name="ring"))
    p.append(torus(0.12, 0.04, (0, 0, 0.885), mat("1b1c26", 0.4, 0.5), name="ring2"))
    for r in (0, 90):
        p.append(box((0.66, 0.045, 0.05), (0, 0, 0.93), mat("22232e", 0.4, 0.5), 0.015, rot=(0, 0, r), name="grate"))
    for i in range(3):
        p.append(cyl(0.05, 0.05, 0.06, (-0.28 + i * 0.28, -0.49, 0.58), mat("dfe3ee", 0.3, 0.8), 20, rot=(90, 0, 0), name="knob"))
    p.append(box((0.8, 0.02, 0.22), (0, -0.485, 0.3), mat("3f4357", 0.5, 0.3), 0.02, name="panel"))
    pot = empty("pot", (0, 0, 0.9))
    parts = [cyl(0.3, 0.27, 0.24, (0, 0, 0.12), mat("b8bfd0", 0.3, 0.8), 40, 0.012, name="pot_body"),
             torus(0.3, 0.025, (0, 0, 0.24), mat("dfe5f2", 0.25, 0.8), name="rim"),
             box((0.14, 0.05, 0.04), (0.38, 0, 0.2), mat("4a4e63", 0.5), 0.015, name="handle_r"),
             box((0.14, 0.05, 0.04), (-0.38, 0, 0.2), mat("4a4e63", 0.5), 0.015, name="handle_l"),
             sphere(0.3, (0, 0, 0.25), mat("c9cfde", 0.25, 0.8), (1, 1, 0.45), 32, "lid", hemi=True),
             sphere(0.05, (0, 0, 0.4), mat("4a4e63", 0.4), name="knob_lid")]
    for q in parts:
        parent(q, pot)
    flames = empty("flames", (0, 0, 0.9))
    fl = []
    for i in range(8):
        a = i * math.tau / 8
        c = cyl(0.05, 0.0, 0.16, (math.cos(a) * 0.26, math.sin(a) * 0.26, 0.05), mat("ff7a1f", 0.5, 0.0, 2.2), 12, name="flame%d" % i)
        parent(c, flames)
        fl.append(c)
    finish("stove", p + [pot, flames] + parts + fl)


@model
def oven():
    p = []
    p.append(box((0.96, 0.9, 1.05), (0, 0.02, 0.525), mat("c3c9d6", 0.3, 0.5), 0.08, name="body"))
    p.append(box((0.64, 0.04, 0.46), (0, -0.44, 0.46), mat("23242e", 0.15, 0.2), 0.03, name="door_glass"))
    p.append(box((0.7, 0.05, 0.52), (0, -0.425, 0.46), mat("8d96ab", 0.3, 0.6), 0.03, name="door_frame"))
    p.append(cyl(0.025, 0.025, 0.66, (0, -0.5, 0.78), mat("eef0f6", 0.2, 0.9), 16, rot=(0, 90, 0), name="handle"))
    for i in range(3):
        p.append(cyl(0.05, 0.05, 0.06, (-0.28 + i * 0.28, -0.46, 0.95), mat("6b7288", 0.3, 0.6), 20, rot=(90, 0, 0), name="knob"))
    p.append(box((0.8, 0.02, 0.04), (0, -0.46, 0.2), mat("a0a8bb", 0.3, 0.6), 0.01, name="vent"))
    glow = box((0.58, 0.03, 0.4), (0, -0.46, 0.46), mat("e86a1a", 0.4, 0.0, 1.6), 0.02, name="glow")
    finish("oven", p + [glow])


@model
def plate_station():
    p = counter_parts("c9b6e0", "8a76a8")
    for i in range(5):
        p.append(cyl(0.34, 0.31, 0.03, (0, 0, 0.9 + i * 0.03), mat("f4f6fb", 0.25), 40, 0.005, name="plate"))
        p.append(torus(0.32, 0.02, (0, 0, 0.912 + i * 0.03), mat("dfe3ee", 0.3), name="rim"))
    finish("plate_station", p)


@model
def bin():
    p = []
    p.append(cyl(0.28, 0.36, 0.8, (0, 0, 0.4), mat("7f8aa3", 0.5, 0.3), 40, 0.01, name="body"))
    for i in range(6):
        a = i * math.tau / 6
        p.append(box((0.03, 0.03, 0.55), (math.cos(a) * 0.33, math.sin(a) * 0.33, 0.38), mat("4d566c", 0.5), 0.01, rot=(0, 0, math.degrees(a)), name="rib"))
    p.append(cyl(0.38, 0.38, 0.09, (0, 0, 0.84), mat("9aa5bf", 0.4, 0.3), 40, 0.02, rot=(4, 0, 0), name="lid"))
    p.append(torus(0.1, 0.035, (0, 0, 0.92), mat("5b6580", 0.4, 0.3), name="handle"))
    finish("bin", p)


# ------------------------------------------------------------------ food (origin on the floor of the model)

@model
def item_veg():
    p = [blob(0.15, (0, 0, 0.15), mat("86c04a", 0.5), (1, 1, 0.95), 0.08, 3.0, 1, "cabbage"),
         blob(0.1, (-0.03, 0.0, 0.24), mat("b5e07a", 0.5), (1, 1, 0.8), 0.06, 4.0, 2, "top")]
    finish("item_veg", p)


@model
def item_meat():
    p = [blob(0.17, (0, 0, 0.07), mat("e5707e", 0.35), (1.15, 0.85, 0.45), 0.05, 2.5, 1, "steak"),
         blob(0.07, (0.07, -0.03, 0.12), mat("ffe4e8", 0.4), (1.2, 1, 0.4), 0.04, 3.0, 2, "fat")]
    finish("item_meat", p)


@model
def item_dough():
    finish("item_dough", [blob(0.16, (0, 0, 0.13), mat("f6ead0", 0.75), (1, 1, 0.85), 0.05, 2.0, 5, "dough")])


@model
def item_veg_chop():
    cols = ["7bc043", "f7a541", "e84f3d", "7bc043", "f7a541", "9fd45c"]
    p = []
    for i in range(6):
        a = i * 1.1
        p.append(box((0.1, 0.1, 0.08), (math.cos(a) * 0.1, math.sin(a) * 0.1, 0.05 + (i % 2) * 0.05), mat(cols[i], 0.5), 0.02, rot=(0, 0, i * 25), name="cube"))
    finish("item_veg_chop", p)


@model
def item_meat_chop():
    p = []
    for i in range(7):
        a = i * 0.95
        p.append(blob(0.06, (math.cos(a) * 0.09, math.sin(a) * 0.09, 0.05 + (i % 3) * 0.035), mat("e5707e", 0.4), (1, 1, 0.9), 0.1, 3.0, i, "mince", 2))
    finish("item_meat_chop", p)


def bowl(hex_out, hex_liquid, r=0.2):
    p = [sphere(r, (0, 0, r + 0.02), mat(hex_out, 0.3, 0.2), (1, 1, 0.8), 40, "bowl", hemi=False)]
    return p


@model
def item_veg_cook():
    p = [sphere(0.2, (0, 0, 0.2), mat("c9cfde", 0.3, 0.6), (1, 1, 1), 40, "bowl", hemi=True)]
    p[0].rotation_euler = (math.pi, 0, 0)
    p[0].location = (0, 0, 0.2)
    p.append(cyl(0.19, 0.19, 0.02, (0, 0, 0.17), mat("d98a2f", 0.25), 32, name="stew"))
    for i in range(4):
        p.append(blob(0.05, (math.cos(i * 1.6) * 0.08, math.sin(i * 1.6) * 0.08, 0.2), mat("7bc043", 0.4), (1, 1, 0.8), 0.1, 3.0, i, "veg", 2))
    finish("item_veg_cook", p)


@model
def item_meat_cooked():
    p = [blob(0.17, (0, 0, 0.07), mat("8a5a2b", 0.55), (1.15, 0.85, 0.45), 0.05, 2.5, 1, "steak")]
    for i in range(3):
        p.append(box((0.012, 0.22, 0.012), (-0.08 + i * 0.08, 0, 0.145), mat("3a1f0e", 0.6), 0.004, rot=(0, 0, 25), name="mark"))
    finish("item_meat_cooked", p)


@model
def item_patty():
    p = [cyl(0.15, 0.15, 0.05, (0, 0, 0.04), mat("6f4518", 0.7), 36, 0.015, name="patty"),
         torus(0.12, 0.02, (0, 0, 0.065), mat("5a3318", 0.7), name="edge")]
    finish("item_patty", p)


@model
def item_bun():
    p = [sphere(0.17, (0, 0, 0.03), mat("e0983a", 0.45), (1, 1, 0.85), 40, "bun", hemi=True)]
    for i in range(6):
        a = i * 1.05
        p.append(sphere(0.016, (math.cos(a) * 0.08, math.sin(a) * 0.08, 0.15), mat("fff1c1", 0.4), (1.4, 0.9, 0.7), 10, "seed"))
    finish("item_bun", p)


@model
def item_burnt():
    p = [blob(0.15, (0, 0, 0.1), mat("1a1a1a", 0.9), (1.1, 0.9, 0.7), 0.12, 3.0, 8, "char"),
         blob(0.08, (0.1, 0.05, 0.12), mat("2b2b2b", 0.9), (1, 1, 0.8), 0.1, 3.0, 9, "char2")]
    finish("item_burnt", p)


def plate_parts():
    return [cyl(0.3, 0.26, 0.035, (0, 0, 0.02), mat("f6f8fc", 0.2), 40, 0.006, name="plate"),
            torus(0.28, 0.025, (0, 0, 0.04), mat("e3e7f2", 0.25), name="rim")]


@model
def dish_salad():
    p = plate_parts()
    for i, (x, y, z, c) in enumerate([(-0.1, 0.0, 0.1, "86c04a"), (0.1, 0.05, 0.1, "6aae35"), (0.0, 0.1, 0.14, "86c04a"), (0.0, -0.12, 0.12, "6aae35"), (-0.14, -0.1, 0.09, "9fd45c")]):
        p.append(blob(0.11, (x, y, z), mat(c, 0.5), (1, 1, 0.8), 0.12, 3.0, i + 1, "leaf", 2))
    for x, y, z in [(0.05, 0.0, 0.2), (-0.1, -0.1, 0.17), (0.13, -0.1, 0.15)]:
        p.append(blob(0.05, (x, y, z), mat("e24a3a", 0.3), (1, 1, 0.9), 0.03, 2.0, 3, "tomato", 2))
    finish("dish_salad", p)


@model
def dish_steak():
    p = plate_parts()
    p.append(blob(0.2, (-0.04, 0.0, 0.1), mat("8a5a2b", 0.5), (1.15, 0.9, 0.5), 0.05, 2.5, 4, "steak"))
    for i in range(3):
        p.append(box((0.012, 0.26, 0.012), (-0.14 + i * 0.09, 0, 0.19), mat("3a1f0e", 0.6), 0.004, rot=(0, 0, 25), name="mark"))
    for x, y in [(0.2, 0.12), (0.24, 0.0), (0.18, -0.12)]:
        p.append(blob(0.055, (x, y, 0.08), mat("6aae35", 0.5), (1, 1, 0.9), 0.08, 3.0, 5, "bean", 2))
    finish("dish_steak", p)


def bowl_dish(hex_bowl, hex_liquid):
    p = [sphere(0.28, (0, 0, 0.28), mat(hex_bowl, 0.35), (1, 1, 1), 48, "bowl", hemi=True)]
    p[0].rotation_euler = (math.pi, 0, 0)
    p.append(cyl(0.26, 0.26, 0.02, (0, 0, 0.22), mat(hex_liquid, 0.2), 40, name="liquid"))
    p.append(torus(0.275, 0.02, (0, 0, 0.28), mat(hex_bowl, 0.3), name="rim"))
    return p


@model
def dish_soup():
    p = bowl_dish("ff8a5a", "e08a2f")
    for i in range(4):
        p.append(blob(0.045, (math.cos(i * 1.7) * 0.12, math.sin(i * 1.7) * 0.12, 0.24), mat("7bc043", 0.4), (1, 1, 0.8), 0.1, 3.0, i, "veg", 2))
    finish("dish_soup", p)


@model
def dish_stew():
    p = bowl_dish("6f8fe0", "7a4a26")
    for i, (x, y) in enumerate([(-0.1, -0.05), (0.1, 0.0), (0.0, 0.1)]):
        p.append(box((0.1, 0.1, 0.07), (x, y, 0.26), mat("a86a38", 0.5), 0.025, rot=(0, 0, x * 200), name="meat"))
    p.append(blob(0.04, (0.12, 0.1, 0.25), mat("7bc043", 0.4), (1, 1, 0.8), 0.1, 3.0, 2, "pea", 2))
    finish("dish_stew", p)


@model
def dish_burger():
    p = plate_parts()
    p.append(sphere(0.22, (0, 0, 0.05), mat("e0983a", 0.45), (1, 1, 0.4), 40, "bun_bottom", hemi=True))
    p.append(cyl(0.22, 0.22, 0.1, (0, 0, 0.11), mat("6f4518", 0.7), 36, 0.03, name="patty"))
    p.append(cyl(0.25, 0.25, 0.025, (0, 0, 0.18), mat("7bc043", 0.5), 40, name="lettuce"))
    p.append(box((0.4, 0.4, 0.02), (0, 0, 0.2), mat("ffd23f", 0.4), 0.005, rot=(0, 0, 45), name="cheese"))
    p.append(sphere(0.23, (0, 0, 0.21), mat("e0983a", 0.45), (1, 1, 0.85), 40, "bun_top", hemi=True))
    for i in range(6):
        a = i * 1.05
        p.append(sphere(0.015, (math.cos(a) * 0.11, math.sin(a) * 0.11, 0.38), mat("fff1c1", 0.4), (1.4, 0.9, 0.7), 10, "seed"))
    finish("dish_burger", p)


if __name__ == "__main__":
    want = sys.argv[1:] or list(MODELS)
    for n in want:
        reset()
        MODELS[n]()
