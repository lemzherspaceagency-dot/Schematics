"""Parametric antweight-style wedge fight robot for a Bambu A1 mini (180^3 mm bed).

Run:  python build_robot.py   ->  writes chassis.stl, lid.stl, wedge.stl, wheel.stl
Units: mm.  X = forward, Y = width, Z = up.  Ground is z = 0.
Needs: pip install numpy trimesh manifold3d
"""
import numpy as np
import trimesh as tm
from trimesh.transformations import rotation_matrix as rot

# ---- parameters -----------------------------------------------------------
CH_X0, CH_X1 = -50, 40        # chassis length (rear..front)
W = 90                        # chassis width
Z0, Z1 = 3, 31                # chassis bottom / top (3 mm ground clearance)
WALL = 2.4
WHEEL_D, WHEEL_W = 30, 12
AXLE_X, AXLE_Z = -25, WHEEL_D / 2
WELL_Y0, WELL_Y1 = 30, W / 2          # wheel-well notch (inner wall .. outer edge)
WELL_X0, WELL_X1 = AXLE_X - 16, AXLE_X + 16
MOTOR_W, MOTOR_H = 12.2, 10.2         # N20 gearmotor body (+ clearance)
LID_T = 2.4
POSTS = [(0, 34), (0, -34), (36, 34), (36, -34)]   # lid screw posts (M2)
WEDGE_LEN = 28


def box(x0, x1, y0, y1, z0, z1):
    b = tm.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0])
    b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    return b


def cyl(r, h, center, axis="z", sections=48):
    c = tm.creation.cylinder(radius=r, height=h, sections=sections)
    if axis == "x":
        c.apply_transform(rot(np.pi / 2, [0, 1, 0]))
    elif axis == "y":
        c.apply_transform(rot(np.pi / 2, [1, 0, 0]))
    c.apply_translation(center)
    return c


def union(*m):
    return tm.boolean.union(list(m), engine="manifold")


def diff(a, *bs):
    return tm.boolean.difference([a, *bs], engine="manifold")


def outline(z0, z1, grow=0.0):
    """Chassis footprint (box minus the two wheel wells), optionally inset by -grow."""
    g = grow
    body = box(CH_X0 + g, CH_X1 - g, -W / 2 + g, W / 2 - g, z0, z1)
    wells = [box(WELL_X0 - g, WELL_X1 + g, WELL_Y0 - g, W, z0 - 1, z1 + 1),
             box(WELL_X0 - g, WELL_X1 + g, -W, -WELL_Y0 + g, z0 - 1, z1 + 1)]
    return diff(body, *wells)


# ---- chassis --------------------------------------------------------------
def chassis():
    shell = outline(Z0, Z1)
    # cavity: inset footprint, but keep a wall around the wheel wells
    cav_body = box(CH_X0 + WALL, CH_X1 - WALL, -W / 2 + WALL, W / 2 - WALL, Z0 + WALL, Z1 + 1)
    cav_wells = [box(WELL_X0 - WALL, WELL_X1 + WALL, WELL_Y0 - WALL, W, Z0, Z1 + 2),
                 box(WELL_X0 - WALL, WELL_X1 + WALL, -W, -WELL_Y0 + WALL, Z0, Z1 + 2)]
    cavity = diff(cav_body, *cav_wells)
    m = diff(shell, cavity)

    add = []
    # motor cradles (one per side), motor axis along Y, gearbox face on the inner wall
    for s in (1, -1):
        ys = sorted([s * (WELL_Y0 - WALL), s * 8])
        blk = box(AXLE_X - 8.6, AXLE_X + 8.6, ys[0], ys[1], Z0 + WALL - .1, AXLE_Z + 2)
        slot = box(AXLE_X - MOTOR_W / 2, AXLE_X + MOTOR_W / 2, ys[0] - 1, ys[1] + 1,
                   AXLE_Z - MOTOR_H / 2, AXLE_Z + 20)
        add.append(diff(blk, slot))
    # lid screw posts
    for (px, py) in POSTS:
        add.append(cyl(3.5, Z1 - (Z0 + WALL) + .2, (px, py, (Z1 + Z0 + WALL) / 2)))
    # rear skids
    for y in (-25, 25):
        add.append(box(CH_X0 + 2, CH_X0 + 8, y - 6, y + 6, 0.6, Z0 + 1))
    m = union(m, *add)

    cuts = []
    # shaft holes through the wheel-well inner walls
    for s in (1, -1):
        cuts.append(cyl(3.2, WALL * 3, (AXLE_X, s * (WELL_Y0 - WALL / 2), AXLE_Z), "y"))
    # lid screw pilot holes (M2 self-tapping)
    for (px, py) in POSTS:
        cuts.append(cyl(0.9, 14, (px, py, Z1 - 6)))
    # wedge screw holes through front wall (M2.5)
    for y in (-25, 25):
        cuts.append(cyl(1.4, WALL * 3, (CH_X1, y, 17), "x"))
    # power switch / wire slot in rear wall
    cuts.append(box(CH_X0 - 1, CH_X0 + WALL + 1, -6, 6, Z0 + WALL + 2, Z0 + WALL + 12))
    return diff(m, *cuts)


# ---- lid ------------------------------------------------------------------
def lid():
    plate = outline(Z1, Z1 + LID_T)
    add = []
    # clamp tabs pressing motors down
    for s in (1, -1):
        add.append(box(AXLE_X - 5, AXLE_X + 5, s * 12 - 5, s * 12 + 5, AXLE_Z + MOTOR_H / 2 + .3, Z1 + .1))
    # locating lip
    lip = diff(box(CH_X0 + WALL + .3, CH_X1 - WALL - .3, -W / 2 + WALL + .3, W / 2 - WALL - .3, Z1 - 3, Z1 + .1),
               box(CH_X0 + WALL + 2.7, CH_X1 - WALL - 2.7, -W / 2 + WALL + 2.7, W / 2 - WALL - 2.7, Z1 - 4, Z1 + 1))
    lip = diff(lip, *[box(WELL_X0 - WALL - .6, WELL_X1 + WALL + .6, WELL_Y0 - WALL - .6, W, Z1 - 4, Z1 + 1),
                      box(WELL_X0 - WALL - .6, WELL_X1 + WALL + .6, -W, -WELL_Y0 + WALL + .6, Z1 - 4, Z1 + 1)])
    m = union(plate, lip, *add)
    holes = [cyl(1.3, 10, (px, py, Z1 + LID_T / 2)) for (px, py) in POSTS]
    # countersink-ish
    holes += [cyl(2.4, 1.2, (px, py, Z1 + LID_T - .5)) for (px, py) in POSTS]
    # ventilation / antenna hole
    holes.append(cyl(2, 10, (-44, 0, Z1)))
    return diff(m, *holes)


# ---- wedge ----------------------------------------------------------------
def wedge():
    h = Z1 - 0.4
    prof = np.array([[0, 0.4], [WEDGE_LEN, 0.4 + 1.5], [0, Z1]])  # (x, z) triangle-ish, tip at +x
    # build prism: polygon in XZ extruded along Y
    from shapely.geometry import Polygon
    poly = Polygon([(0, 0.4), (WEDGE_LEN, 0.4), (WEDGE_LEN, 2.0), (0, Z1)])
    m = tm.creation.extrude_polygon(poly, W)           # extrudes along +Z; map Z->Y
    m.apply_transform(rot(np.pi / 2, [1, 0, 0]))        # (x,y,z)->(x,-z,y)  => poly y becomes Z
    m.apply_translation([0, W / 2, 0])
    m.apply_translation([CH_X1, 0, 0])
    # pilot holes for M2.5 screws, from the back (chassis) face
    holes = [cyl(1.1, 14, (CH_X1 + 7, y, 17), "x") for y in (-25, 25)]
    # trim wheel-well-free corners: round the outer sides slightly
    return diff(m, *holes)


# ---- wheel ----------------------------------------------------------------
def wheel():
    w = cyl(WHEEL_D / 2, WHEEL_W, (0, 0, 0), "y", sections=96)
    treads = []
    for i in range(24):
        a = 2 * np.pi * i / 24
        t = box(-1, 1, -WHEEL_W, WHEEL_W, 0, 2.2)
        t.apply_translation([0, 0, WHEEL_D / 2 - 1.1])
        t.apply_transform(rot(a, [0, 1, 0]))
        treads.append(t)
    w = diff(w, *treads)
    # N20 "D" shaft bore: 3.0 mm with 2.5 mm flat (+0.1 clearance)
    bore = cyl(1.6, WHEEL_W + 2, (0, 0, 0), "y", sections=32)
    keep = box(-3, 3, -WHEEL_W, WHEEL_W, -3, 1.25 + 0.0)  # remove nothing above flat
    flat = box(-3, 3, -WHEEL_W, WHEEL_W, 1.25, 3)          # material put back above the flat
    bore = diff(bore, flat)
    return diff(w, bore)


if __name__ == "__main__":
    for name, fn in [("chassis", chassis), ("lid", lid), ("wedge", wedge), ("wheel", wheel)]:
        m = fn()
        m.export(f"{name}.stl")
        print(f"{name:8s} watertight={m.is_watertight} size={np.round(m.extents,1)} vol={m.volume/1000:.1f} cm3")
