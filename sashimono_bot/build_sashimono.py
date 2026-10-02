"""SASHIMONO - samurai fight robot for a Bambu A1 mini.

Kabuto-helmet front (visor ramp, flared fukigaeshi wings, crescent maedate crest), a servo-swept
katana, and a tall breakaway sashimono banner (mitsudomoe emblem) on the back.
Chassis, lid and wheels are shared with ../scorpion_bot.   python build_sashimono.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scorpion_bot"))
import numpy as np, trimesh as tm
from shapely.geometry import Polygon, Point, LineString, box as sbox
from shapely.ops import unary_union
from shapely import affinity
from build_scorpion import *          # box, cyl, union, diff, inter, prism, hull_chain, outline, constants...
from build_scorpion import chassis, lid, wheel

CYC = lambda dx, dy, dz: np.array([[0, 0, 1, dx], [1, 0, 0, dy], [0, 1, 0, dz], [0, 0, 0, 1]], float)  # (x,y,z)->(z+dx, x+dy, y+dz)
POLE_Y, POLE_X = -22.0, -45.5          # banner pole position (world)
POLE_W, POLE_T, POLE_LEN = 5.0, 3.0, 90.0
SOCK_TOP = SERVO_TOP + SHELL_T + 14    # socket height above shell

# ---- carapace with banner socket (breakaway: pole is a friction fit) ----
def carapace_s():
    plate = outline(SERVO_TOP, SERVO_TOP + SHELL_T)
    z0, z1 = SERVO_TOP + SHELL_T - .1, SERVO_TOP + SHELL_T + 3
    ribs = [box(x - 1.8, x + 1.8, -36, 36, z0, z1) for x in (12, 20, 28, 35.5)]
    sock = box(-50, -41, POLE_Y - 5, POLE_Y + 5, z0, SOCK_TOP)
    m = union(plate, *ribs, sock)
    holes = [cyl(1.3, 12, (*p, SERVO_TOP + 1)) for p in POSTS]
    holes += [cyl(2.4, 1.2, (*p, SERVO_TOP + SHELL_T - .4)) for p in POSTS]
    holes.append(box(SERVO_X - 14, SERVO_X + 14, -9, 9, SERVO_TOP - 1, SERVO_TOP + 6))
    holes.append(box(POLE_X - (POLE_T + .4) / 2, POLE_X + (POLE_T + .4) / 2, POLE_Y - (POLE_W + .4) / 2,
                     POLE_Y + (POLE_W + .4) / 2, SOCK_TOP - 12.5, SOCK_TOP + 1))
    return diff(m, *holes)

# ---- kabuto front ----
def kabuto():
    envelope = Polygon([(40, .4), (95, .4), (95, 3), (40, 28)])
    env = tm.creation.extrude_polygon(envelope, 140); env.apply_transform(tm.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    env.apply_translation([0, 70, 0])
    plan = [Polygon([(40, -45), (46, -45), (46, 45), (40, 45)])]
    for s in (1, -1):                                           # fukigaeshi: flared cheek wings
        plan.append(Polygon([(44, s * 24), (44, s * 46), (62, s * 50), (90, s * 66), (80, s * 50), (66, s * 32)]).convex_hull)
    body = inter(prism(unary_union(plan), .4, 40), env)
    ramp = Polygon([(46, .4), (74, .4), (74, 2), (46, 24)])     # mabisashi visor ramp
    r = tm.creation.extrude_polygon(ramp, 56); r.apply_transform(tm.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    r.apply_translation([0, 28, 0])
    bosses = [box(46, 54, y - 4.5, y + 4.5, .4, 22) for y in (-25, 25)]
    # maedate: crescent crest standing on the visor (YZ profile)
    cres = Point(0, 25).buffer(13, 64).difference(Point(0, 31).buffer(10.8, 64))
    cm = tm.creation.extrude_polygon(cres, 3.2); cm.apply_transform(CYC(52.5, 0, 0))
    m = union(body, inter(r, env), *bosses, cm)
    return diff(m, *[cyl(1.1, 15, (47, y, 17), "x") for y in (-25, 25)])

# ---- katana: servo-swept blade with tsuba, tsuka and kashira ----
def katana():
    Rc = 110; th = np.radians(np.linspace(0, 36, 14))
    c = np.array([(11 + Rc * np.sin(t), Rc * (1 - np.cos(t))) for t in th])
    tg = np.stack([np.cos(th), np.sin(th)], 1); nm = np.stack([-tg[:, 1], tg[:, 0]], 1)
    w = np.linspace(9.0, 6.5, len(th))[:, None]
    left = c + nm * w * .5; right = c - nm * w * .5
    tip = c[-1] + tg[-1] * 3 + nm[-1] * 3.5 + tg[-1] * 9                    # kissaki, angled tip
    blade = Polygon([*map(tuple, right), tuple(tip), *map(tuple, left[::-1])])
    tsuba = Point(5, 0).buffer(11, 48)
    sukashi = [Point(5 + 7.2 * np.cos(a), 7.2 * np.sin(a)).buffer(1.6, 16) for a in np.radians([45, 135, 225, 315])]
    tsuka = LineString([(-24, 0), (6, 0)]).buffer(3.6, cap_style=1)
    kashira = Point(-25, 0).buffer(4.6, 24)
    plan = unary_union([blade, tsuba, tsuka, kashira]).difference(unary_union(sukashi))
    arm = prism(plan, TAIL_Z0, TAIL_Z1)
    riser = box(-11, 14, -5, 5, SERVO_TOP + .2, TAIL_Z0 + .1)
    m = union(arm, riser); zh = SERVO_TOP + .2
    cuts = [cyl(4.4, 4.1, (0, 0, zh + 2)), box(-11.5, 14.5, -2.4, 2.4, zh - .1, zh + 2.2), cyl(1.6, 20, (0, 0, zh + 8))]
    cuts += [cyl(0.8, 12, (x, 0, zh + 6)) for x in (-7, 7)]
    m = diff(m, *cuts); m.apply_translation([PIVOT[0], PIVOT[1], 0]); return m

# ---- sashimono banner (mitsudomoe emblem), assembled pose ----
def tomoe(cx, cy, ang, R=9.5):
    pts = [(cx + R * np.cos(ang - a), cy + R * np.sin(ang - a)) for a in np.radians(np.linspace(0, 68, 14))]
    rad = np.linspace(4.6, .4, len(pts))
    head = Point(pts[0]).buffer(rad[0], 24)
    return unary_union([head, hull_chain(pts, rad)])
def banner(assembled=True):
    fx0, fx1, fy0, fy1 = POLE_W, POLE_W + 40, 24, 88
    pole = sbox(0, 0, POLE_W, POLE_LEN)
    frame = sbox(fx0 - 1, fy0, fx1, fy1).difference(sbox(fx0 + 3, fy0 + 3, fx1 - 3, fy1 - 3))
    field = sbox(fx0, fy0, fx1, fy1)
    cx, cy = (fx0 + fx1) / 2, (fy0 + fy1) / 2
    emblem = unary_union([tomoe(cx, cy, np.radians(a)) for a in (90, 210, 330)]).buffer(.05).buffer(-.05).simplify(.08)
    field = field.difference(emblem)
    thick = unary_union([pole, frame])
    m = union(prism(thick, 0, POLE_T), prism(field, 0, 1.6))
    if assembled:
        m.apply_transform(CYC(POLE_X - POLE_T / 2, POLE_Y - POLE_W / 2, SOCK_TOP - 12))
    return m

PARTS = dict(chassis=chassis, lid=lid, wheel=wheel, carapace=carapace_s, kabuto=kabuto, katana=katana, banner=banner)
if __name__ == "__main__":
    for n, fn in PARTS.items():
        m = fn(); m.export(f"{n}.stl")
        print(f"{n:9s} watertight={m.is_watertight} size={np.round(m.extents,1)} vol={m.volume/1000:.1f} cm3")
