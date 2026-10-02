#!/usr/bin/env python3
"""
FLEXI ROCKET - print-in-place articulated rocket (numpy + trimesh + shapely).

* ONE colour / ONE filament (made for milky pink), no AMS, NO extra hardware
* Prints FLAT on the bed, 8 mm thick, every wall vertical -> no supports
* 6 rigid segments joined by 5 print-in-place pin hinges (0.3 mm radial gap,
  0.4 mm = 2 layers vertical gap). Whole model ~170 x 54 x 8 mm.

Hinge (per joint, pivot J):  segment B (nose side) owns two disc plates
(z 0-2.4 and 5.6-8) joined by a pin.  Segment A (tail side) owns a 2.4 mm ear
(z 2.8-5.2) with a hole around the pin, sitting between the plates.
A's end is a circular notch around J, so the joint can turn without collisions.

usage:  python3 flexi_rocket.py [out.stl]
"""
import sys
import numpy as np
import trimesh
from shapely.geometry import Polygon, Point, box
from shapely.ops import unary_union
from shapely import affinity

# ------------------------------------------------------------------ params
GAP    = 0.30          # horizontal clearance (mm)
VG     = 0.40          # vertical clearance (2 layers @ 0.2)
TP     = 2.4           # plate thickness
TE     = 2.4           # ear thickness
H_BODY = 8.5           # strip half-width
RD     = 9.0           # knuckle disc radius
R_EAR  = 4.6
R_PIN  = 2.0
R_HOLE = R_PIN + GAP
R_CAV  = R_EAR + GAP
R_NOTCH = RD + GAP
WRIST  = 4.0
WEDGE  = np.radians(40)   # half angle of the wrist slot in the plate ring
RES    = 48               # circle resolution

# z bands: plate | gap | ear | gap | plate
Z = np.cumsum([0, TP, VG, TE, VG, TP])
B_PL0, B_G1, B_EAR, B_G2, B_PL1 = [(Z[i], Z[i+1]) for i in range(5)]
THICK = Z[-1]

# joint x positions (pivot centres), nose to +X
J = [30.0, 52.0, 82.0, 104.0, 126.0]
NOSE_TIP = J[-1] + 44.0


def circle(cx, r, cy=0.0):
    return Point(cx, cy).buffer(r, RES)


def flame(x_end):
    t = np.linspace(0, 1, 70)
    w = 7.5 * t**0.65 * (0.9 + 0.1*np.cos(5*np.pi*t))
    x = t * x_end
    return Polygon(list(zip(x, w)) + list(zip(x[::-1], -w[::-1])))


def nose(x0):
    """flat strip then tangent ogive to the tip."""
    L = NOSE_TIP - (x0 + 8.0)
    R = H_BODY
    rho = (R*R + L*L) / (2*R)
    s = np.linspace(0, L, 60)                 # x from tip
    y = np.sqrt(np.maximum(rho**2 - (L - s)**2, 0)) + R - rho
    xs = NOSE_TIP - s
    top = list(zip(xs, y))                    # tip -> base
    pts = top + [(x0, R), (x0, -R)] + [(a, -b) for a, b in top[::-1]]
    poly = Polygon(pts)
    return poly.buffer(0)


def fin(x0):
    up = Polygon([(x0+24, H_BODY-0.5), (x0+11, 26), (x0+7, 26), (x0+7, H_BODY-0.5)])
    return unary_union([up, affinity.scale(up, yfact=-1, origin=(0, 0))])


def wedge(jx):
    """slot opening towards -X for the A-segment wrist."""
    a = np.linspace(np.pi - WEDGE, np.pi + WEDGE, 20)
    return Polygon([(jx, 0)] + [(jx + 12*np.cos(t), 12*np.sin(t)) for t in a])


def strip(k):
    if k == 0:
        return flame(J[0])
    if k == 5:
        return nose(J[4])
    if k == 1:
        return box(J[0], -8.0, J[1], 8.0)
    if k == 2:
        return unary_union([box(J[1], -H_BODY, J[2], H_BODY), fin(J[1])])
    return box(J[k-1], -H_BODY, J[k], H_BODY)


def bands(k):
    """list of (z0, z1, polygon) for segment k."""
    base = strip(k)
    has_disc = k > 0
    has_notch = k < 5
    jl = J[k-1] if has_disc else None
    jr = J[k] if has_notch else None

    def cut_notch(p):
        return p.difference(circle(jr, R_NOTCH)) if has_notch else p

    out = []
    # ---- full plates (bottom & top) : body + disc
    plate = unary_union([base, circle(jl, RD)]) if has_disc else base
    plate = cut_notch(plate)
    # ---- gap layers : body without the ear/cavity zone, pin only
    gap = base.difference(circle(jl, R_CAV)) if has_disc else base
    gap = cut_notch(gap)
    # ---- ear layer
    if has_disc:
        ring = unary_union([base, circle(jl, RD)])
        ring = ring.difference(circle(jl, R_CAV)).difference(wedge(jl))
        mid = ring
    else:
        mid = base
    mid = cut_notch(mid)
    if has_notch:   # ear + wrist (this segment's tail-side partner)
        ear = unary_union([circle(jr, R_EAR),
                           box(jr - 12.0, -WRIST/2, jr, WRIST/2)])
        ear = ear.difference(circle(jr, R_HOLE))
        mid = unary_union([mid, ear])
    pin = circle(jl, R_PIN) if has_disc else None

    for (z0, z1), poly in [(B_PL0, plate), (B_G1, gap), (B_EAR, mid),
                           (B_G2, gap), (B_PL1, plate)]:
        p = poly
        if pin is not None:
            p = unary_union([p, pin])
        out.append((z0, z1, p))
    if k == 5:      # porthole through the nose segment
        hole = circle(J[4] + 18.0, 4.0)
        out = [(z0, z1, p.difference(hole)) for z0, z1, p in out]
    return out


def extrude(poly, z0, z1):
    geoms = list(poly.geoms) if hasattr(poly, "geoms") else [poly]
    ms = []
    for g in geoms:
        if g.is_empty or g.area < 1e-6:
            continue
        m = trimesh.creation.extrude_polygon(g, z1 - z0)
        m.apply_translation([0, 0, z0])
        ms.append(m)
    return ms


def build_segment(k):
    parts = []
    for z0, z1, poly in bands(k):
        parts += extrude(poly, z0, z1)
    m = trimesh.boolean.union(parts, engine="manifold")
    m.merge_vertices()
    return m


def main(out="flexi_rocket.stl"):
    segs = [build_segment(k) for k in range(6)]
    scene = trimesh.util.concatenate(segs)
    c = scene.bounds.mean(axis=0)
    shift = np.array([-c[0], -c[1], 0.0])
    for s in segs:
        s.apply_translation(shift)
    scene.apply_translation(shift)
    scene.export(out)
    return segs, scene


if __name__ == "__main__":
    segs, scene = main(sys.argv[1] if len(sys.argv) > 1 else "flexi_rocket.stl")
    print("bounds (mm):", np.round(scene.bounds, 2).tolist())
