"""SCORPION - Bambu A1 mini fight robot with a servo-whipped stinger tail and pincer front.

Run:  python build_scorpion.py   ->  chassis / lid / carapace / claws / tail / wheel .stl
Units mm. X = forward, Y = left, Z = up, ground z = 0.   pip install numpy trimesh manifold3d shapely
"""
import numpy as np, trimesh as tm
from shapely.geometry import Polygon, Point, MultiPoint
from shapely.ops import unary_union
from trimesh.transformations import rotation_matrix as rot

# ---- parameters ----
CH_X0, CH_X1, W = -50, 40, 90
Z0, Z1, WALL = 3, 31, 2.4
WHEEL_D, WHEEL_W = 30, 12
AXLE_X, AXLE_Z = -25, 15
WELL_Y0, WELL_Y1 = 30, 45
WELL_X0, WELL_X1 = AXLE_X - 16, AXLE_X + 16
MOTOR_W, MOTOR_H = 12.2, 10.2                 # N20 gearmotor
LID_T, SHELL_T = 2.4, 2.4
POSTS = [(0, 34), (0, -34), (36, 34), (36, -34)]
# SG90-style 9 g servo, standing upright in the chassis, shaft poking up through the lid
SERVO_X, SERVO_L, SERVO_W, SERVO_H = 0.0, 22.7, 12.2, 22.7
SERVO_TOP = Z1 + LID_T                        # body top flush with lid top
SERVO_BOT = SERVO_TOP - SERVO_H
PIVOT = (SERVO_X - SERVO_L / 2 + 6, 0)        # output shaft ~6 mm from the servo end
TAIL_Z0, TAIL_Z1 = 40.5, 45.5                 # tail arm height (clears the shell ribs)

def box(x0, x1, y0, y1, z0, z1):
    b = tm.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0])
    b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]); return b
def cyl(r, h, c, axis="z", n=48):
    m = tm.creation.cylinder(radius=r, height=h, sections=n)
    if axis == "x": m.apply_transform(rot(np.pi / 2, [0, 1, 0]))
    if axis == "y": m.apply_transform(rot(np.pi / 2, [1, 0, 0]))
    m.apply_translation(c); return m
def cone(r, h, base, axis="z"):
    m = tm.creation.cone(radius=r, height=h, sections=32)
    if axis == "x": m.apply_transform(rot(np.pi / 2, [0, 1, 0]))
    m.apply_translation(base); return m
union = lambda *m: tm.boolean.union(list(m), engine="manifold")
diff = lambda a, *b: tm.boolean.difference([a, *b], engine="manifold")
inter = lambda *m: tm.boolean.intersection(list(m), engine="manifold")
def prism(poly, z0, z1):
    m = tm.creation.extrude_polygon(poly, z1 - z0); m.apply_translation([0, 0, z0]); return m

def outline(z0, z1, g=0.0):
    body = box(CH_X0 + g, CH_X1 - g, -W / 2 + g, W / 2 - g, z0, z1)
    return diff(body, box(WELL_X0 - g, WELL_X1 + g, WELL_Y0 - g, W, z0 - 1, z1 + 1),
                box(WELL_X0 - g, WELL_X1 + g, -W, -WELL_Y0 + g, z0 - 1, z1 + 1))

# ---- chassis ----
def chassis():
    shell = outline(Z0, Z1)
    cav = diff(box(CH_X0 + WALL, CH_X1 - WALL, -W / 2 + WALL, W / 2 - WALL, Z0 + WALL, Z1 + 1),
               box(WELL_X0 - WALL, WELL_X1 + WALL, WELL_Y0 - WALL, W, Z0, Z1 + 2),
               box(WELL_X0 - WALL, WELL_X1 + WALL, -W, -WELL_Y0 + WALL, Z0, Z1 + 2))
    m = diff(shell, cav); add = []
    for s in (1, -1):                                           # motor cradles
        ys = sorted([s * (WELL_Y0 - WALL), s * 8])
        blk = box(AXLE_X - 8.6, AXLE_X + 8.6, ys[0], ys[1], Z0 + WALL - .1, AXLE_Z + 2)
        add.append(diff(blk, box(AXLE_X - MOTOR_W / 2, AXLE_X + MOTOR_W / 2, ys[0] - 1, ys[1] + 1,
                                 AXLE_Z - MOTOR_H / 2, AXLE_Z + 20)))
    wing_z = SERVO_BOT + 16                                     # servo wing height
    cr = box(SERVO_X - 16.5, SERVO_X + 16.5, -7.5, 7.5, Z0 + WALL - .1, wing_z)
    add.append(diff(cr, box(SERVO_X - SERVO_L / 2 - .3, SERVO_X + SERVO_L / 2 + .3, -SERVO_W / 2 - .3,
                            SERVO_W / 2 + .3, SERVO_BOT, Z1 + 5)))
    for p in POSTS: add.append(cyl(3.5, Z1 - (Z0 + WALL) + .2, (*p, (Z1 + Z0 + WALL) / 2)))
    for y in (-25, 25): add.append(box(CH_X0 + 2, CH_X0 + 8, y - 6, y + 6, 0.6, Z0 + 1))   # rear skids
    m = union(m, *add)
    cuts = [cyl(3.2, WALL * 3, (AXLE_X, s * (WELL_Y0 - WALL / 2), AXLE_Z), "y") for s in (1, -1)]
    cuts += [cyl(0.9, 14, (*p, Z1 - 6)) for p in POSTS]                                    # lid screws
    cuts += [cyl(1.4, WALL * 3, (CH_X1, y, 17), "x") for y in (-25, 25)]                   # claw screws
    cuts += [cyl(0.85, 8, (SERVO_X + s * 14.2, 0, wing_z - 3)) for s in (1, -1)]           # servo screws
    cuts.append(box(CH_X0 - 1, CH_X0 + WALL + 1, -6, 6, Z0 + WALL + 2, Z0 + WALL + 12))    # switch slot
    return diff(m, *cuts)

OPEN_L, OPEN_W = SERVO_L + 1.2, SERVO_W + 1.0

# ---- lid (print upside down) ----
def lid():
    plate = outline(Z1, Z1 + LID_T)
    tabs = [box(AXLE_X - 5, AXLE_X + 5, s * 12 - 5, s * 12 + 5, AXLE_Z + MOTOR_H / 2 + .3, Z1 + .1) for s in (1, -1)]
    lip = diff(box(CH_X0 + WALL + .3, CH_X1 - WALL - .3, -W / 2 + WALL + .3, W / 2 - WALL - .3, Z1 - 3, Z1 + .1),
               box(CH_X0 + WALL + 2.7, CH_X1 - WALL - 2.7, -W / 2 + WALL + 2.7, W / 2 - WALL - 2.7, Z1 - 4, Z1 + 1),
               box(WELL_X0 - WALL - .6, WELL_X1 + WALL + .6, WELL_Y0 - WALL - .6, W, Z1 - 4, Z1 + 1),
               box(WELL_X0 - WALL - .6, WELL_X1 + WALL + .6, -W, -WELL_Y0 + WALL + .6, Z1 - 4, Z1 + 1),
               box(SERVO_X - 20, SERVO_X + 20, -12, 12, Z1 - 4, Z1 + 1))
    m = union(plate, lip, *tabs)
    holes = [cyl(1.3, 12, (*p, Z1 + LID_T / 2)) for p in POSTS]
    holes.append(box(SERVO_X - OPEN_L / 2, SERVO_X + OPEN_L / 2, -OPEN_W / 2, OPEN_W / 2, Z1 - 5, Z1 + 5))
    return diff(m, *holes)

# ---- carapace: segmented armor plate on top of the lid ----
def carapace():
    plate = outline(SERVO_TOP, SERVO_TOP + SHELL_T)
    z0, z1 = SERVO_TOP + SHELL_T - .1, SERVO_TOP + SHELL_T + 3
    ribs = [box(x - 1.8, x + 1.8, -36, 36, z0, z1) for x in (12, 20, 28, 36 - 0.5)]
    ribs += [box(x - 1.8, x + 1.8, -20, 20, z0, z1) for x in (-46, -40)]
    eyes = [cone(3, 5, (38, s * 12, z0)) for s in (1, -1)]
    m = union(plate, *ribs, *eyes)
    holes = [cyl(1.3, 12, (*p, SERVO_TOP + 1)) for p in POSTS]
    holes += [cyl(2.4, 1.2, (*p, SERVO_TOP + SHELL_T - .4)) for p in POSTS]
    holes.append(box(SERVO_X - 14, SERVO_X + 14, -9, 9, SERVO_TOP - 1, SERVO_TOP + 6))
    return diff(m, *holes)

# ---- pincer front (claws + ramp) ----
def hull_chain(pts, radii):
    return unary_union([MultiPoint([*Point(p).buffer(r).exterior.coords,
                                    *Point(q).buffer(s).exterior.coords]).convex_hull
                        for (p, r), (q, s) in zip(zip(pts, radii), zip(pts[1:], radii[1:]))])
def claws():
    def bez(P0, P1, P2, n=24):
        t = np.linspace(0, 1, n)[:, None]
        return (1 - t) ** 2 * P0 + 2 * (1 - t) * t * P1 + t ** 2 * P2
    rr = np.linspace(8, 3, 24)
    arms = [hull_chain([tuple(p) for p in bez(np.array([44, s * 38.]), np.array([86, s * 46.]), np.array([92, s * 10.]))], rr)
            for s in (1, -1)]
    plan = unary_union([Polygon([(40, -45), (46, -45), (46, 45), (40, 45)]), *arms])
    envelope = Polygon([(40, .4), (95, .4), (95, 3), (40, 28)])
    env = tm.creation.extrude_polygon(envelope, 140); env.apply_transform(rot(np.pi / 2, [1, 0, 0]))
    env.apply_translation([0, 70, 0])
    body = inter(prism(plan, .4, 40), env)
    ramp = Polygon([(46, .4), (68, .4), (68, 2), (46, 24)])
    r = tm.creation.extrude_polygon(ramp, 44); r.apply_transform(rot(np.pi / 2, [1, 0, 0])); r.apply_translation([0, 22, 0])
    bosses = [box(46, 54, y - 4.5, y + 4.5, .4, 22) for y in (-25, 25)]
    m = union(body, inter(r, env), *bosses)
    return diff(m, *[cyl(1.1, 15, (47, y, 17), "x") for y in (-25, 25)])

# ---- tail: beaded arc that whips side to side above the shell ----
def tail():
    th = np.radians(np.linspace(0, 78, 9)); Rc = 54
    pts = [(Rc * np.sin(t), Rc * (1 - np.cos(t))) for t in th]
    beads = np.linspace(8.5, 4.2, len(pts))
    parts = [Point(p).buffer(r, 24) for p, r in zip(pts, beads)]
    neck = [hull_chain(pts[i:i + 2], [3.2, 3.2]) for i in range(len(pts) - 1)]
    tang = np.array([np.cos(th[-1]), np.sin(th[-1])]); nrm = np.array([-tang[1], tang[0]])
    base = np.array(pts[-1]); hook = tang * 18 + nrm * 9
    sting = Polygon([base + nrm * 4, base - nrm * 3, base + hook]).buffer(.6)
    plan = unary_union([*parts, *neck, sting])
    arm = prism(plan, TAIL_Z0, TAIL_Z1)
    riser = box(-11, 14, -5, 5, SERVO_TOP + .2, TAIL_Z0 + .1)
    m = union(arm, riser)
    zh = SERVO_TOP + .2
    cuts = [cyl(4.4, 4.1, (0, 0, zh + 2)), box(-11.5, 14.5, -2.4, 2.4, zh - .1, zh + 2.2),   # horn pocket + arm slot
            cyl(1.6, 20, (0, 0, zh + 8))]                                                    # centre screw
    cuts += [cyl(0.8, 12, (x, 0, zh + 6)) for x in (-7, 7)]                                  # horn-hole screws
    m = diff(m, *cuts)
    m.apply_translation([PIVOT[0], PIVOT[1], 0]); return m

# ---- wheel (TPU) ----
def wheel():
    w = cyl(WHEEL_D / 2, WHEEL_W, (0, 0, 0), "y", 96)
    cuts = []
    for i in range(24):
        t = box(-1, 1, -WHEEL_W, WHEEL_W, 0, 2.2); t.apply_translation([0, 0, WHEEL_D / 2 - 1.1])
        t.apply_transform(rot(2 * np.pi * i / 24, [0, 1, 0])); cuts.append(t)
    w = diff(w, *cuts)
    bore = diff(cyl(1.6, WHEEL_W + 2, (0, 0, 0), "y", 32), box(-3, 3, -WHEEL_W, WHEEL_W, 1.25, 3))
    return diff(w, bore)

PARTS = dict(chassis=chassis, lid=lid, carapace=carapace, claws=claws, tail=tail, wheel=wheel)
if __name__ == "__main__":
    tot = 0
    for n, fn in PARTS.items():
        m = fn(); m.export(f"{n}.stl")
        q = 2 if n == "wheel" else 1; tot += m.volume / 1000 * q
        print(f"{n:9s} watertight={m.is_watertight} size={np.round(m.extents,1)} vol={m.volume/1000:.1f} cm3")
    print(f"total solid volume ~{tot:.0f} cm3 -> ~{tot*1.24*0.35:.0f} g printed at ~35% effective fill (PLA/PETG)")
