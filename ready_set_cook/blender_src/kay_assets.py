"""Builds the game's models out of the CC0 KayKit Restaurant Bits + Kenney Food Kit packs.
Run: PACKS=/path/to/unzipped/packs python3 kay_assets.py [name ...]   (1 tile = 1 unit, counter top at TOP)"""
import sys, math
from kay import *

TOP = 0.75         # counter top height (KayKit counters are 1.0 tall at full size, we use half size)
MODELS = {}


def model(fn):
    MODELS[fn.__name__] = fn
    return fn


@model
def counter():
    kay("kitchencounter_straight_A", scale=SZ); save("counter")


@model
def table():
    kay("table_round_A_small", scale=0.55); save("table")


@model
def chair():
    kay("chair_A", scale=0.5); save("chair")


@model
def crate_meat():
    kay("crate_steak", scale=SZ); save("crate_meat")


@model
def crate_veg():
    kay("crate_lettuce", scale=SZ); save("crate_veg")


@model
def crate_dough():
    kay("crate_buns", scale=SZ); save("crate_dough")


@model
def chop_board():
    kay("kitchencounter_straight_B", scale=SZ)
    kay("cuttingboard", loc=(0, 0, TOP), scale=0.5)
    kay("knife", loc=(-0.3, 0.12, TOP), rot_z=70, scale=0.38)
    save("chop_board")


@model
def stove():
    kay("stove_single", loc=(0, 0.1, 0), scale=SZ)
    pot = empty("pot", (0, 0, TOP + 0.02))
    p = kay("pot_A", "pot_model", scale=0.42)
    p.parent = pot
    fl = empty("flames", (0, 0, TOP + 0.02))
    for i in range(8):
        a = i * math.tau / 8
        c = cyl(0.035, 0.0, 0.1, (math.cos(a) * 0.17, math.sin(a) * 0.17, 0.03), mat("ff7a1f", 0.5, 0.0, 2.2), 12, name="flame%d" % i)
        c.parent = fl
    save("stove")


@model
def oven():
    kay("oven", loc=(0, 0.15, 0), scale=(0.5, 0.5, 0.62))
    box((0.5, 0.02, 0.4), (0, -0.5, 0.55), mat("e86a1a", 0.4, 0.0, 1.6), 0.01, name="glow")
    save("oven")


@model
def plate_station():
    kay("kitchencounter_straight_A", scale=SZ)
    for i in range(5):
        kay("plate", "plate%d" % i, loc=(0, 0, TOP + i * 0.035), scale=0.4)
    save("plate_station")


@model
def bin():
    p = [cyl(0.2, 0.25, 0.7, (0, 0, 0.35), mat("7f8aa3", 0.5, 0.3), 40, 0.01, name="body"),
         cyl(0.27, 0.27, 0.07, (0, 0, 0.74), mat("9aa5bf", 0.4, 0.3), 40, 0.02, name="lid"),
         torus(0.07, 0.025, (0, 0, 0.82), mat("5b6580", 0.4, 0.3), name="handle")]
    for i in range(6):
        a = i * math.tau / 6
        p.append(box((0.025, 0.025, 0.5), (math.cos(a) * 0.235, math.sin(a) * 0.235, 0.34), mat("4d566c", 0.5), 0.008, rot=(0, 0, math.degrees(a)), name="rib"))
    save("bin")


for _n, _src, _k, _sz in [
    ("item_veg", "food_ingredient_lettuce", "k", 0.3), ("item_meat", "food_ingredient_steak", "k", 0.3),
    ("item_veg_chop", "food_ingredient_lettuce_chopped", "k", 0.3), ("item_meat_chop", "food_ingredient_burger_uncooked", "k", 0.3),
    ("item_veg_cook", "stew_bowl", "k", 0.3), ("item_meat_cooked", "food_ingredient_ham_cooked", "k", 0.3),
    ("item_patty", "food_ingredient_burger_cooked", "k", 0.3), ("item_bun", "food_ingredient_bun", "k", 0.3),
    ("item_burnt", "food_ingredient_burger_trash", "k", 0.3),
    ("dish_burger", "food_burger", "k", 0.4), ("dish_steak", "food_dinner", "k", 0.4), ("dish_stew", "food_stew", "k", 0.4),
    ("dish_salad", "salad", "n", 0.36), ("dish_soup", "bowl-soup", "n", 0.36)]:
    def _mk(n=_n, s=_src, k=_k, z=_sz):
        def f():
            r = (kay if k == "k" else ken)(s, "r")
            fit(r, z)
            save(n)
        f.__name__ = n
        return f
    MODELS[_n] = _mk()


# environment pieces (used by kitchen_view.gd), full-size origin as in the pack
@model
def env_wall():
    kay("wall"); save("env_wall")


@model
def env_window():
    kay("wall_window_open"); save("env_window")


@model
def env_pillar():
    kay("pillar_A"); save("env_pillar")


@model
def env_floor():
    kay("floor_kitchen_small"); save("env_floor")


if __name__ == "__main__":
    for n in (sys.argv[1:] or list(MODELS)):
        reset()
        MODELS[n]()
