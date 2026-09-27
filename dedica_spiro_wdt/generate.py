#!/usr/bin/env python3
"""
Spiro51 - planetary "spirograph" WDT tool for 51 mm portafilters
(DeLonghi Dedica EC685 / EC680 / EC695 and other 51 mm DeLonghi baskets).

Low-BOM design: no bearings, no screws, no magnets. The only non-printed
parts are the needles (0.25-0.30 mm acupuncture needles) and a drop of glue.

How it works
------------
  * BASE     - drops into the basket with a short spigot and holds a fixed
               internal ring gear (37 teeth, module 1.5).
  * PLANET   - one big 23-tooth gear that carries the needles. Because it is
               larger than half the ring, its needles sweep every radius from
               the centre of the puck out to ~23 mm.
  * CARRIER  - the lid. Turning it drives the planet around the ring. The
               planet hangs on a printed snap pin, the lid snaps onto the base.
  * KNOB     - free-spinning crank handle that snaps into the lid.
  * STAND    - storage cup that protects the needles.

37 and 23 are coprime, so the pattern only repeats after 23 turns of the lid:
each extra turn lays down new, un-overlapping tracks.

Run:  python3 generate.py            (writes STL + 3MF + preview PNGs to ./out)
Needs: pip install numpy manifold3d trimesh pillow matplotlib
"""
import math
import os
import zipfile

import numpy as np
from manifold3d import CrossSection, Manifold

# --------------------------------------------------------------------------
# Parameters (mm).  Change these if your basket/printer needs it.
# --------------------------------------------------------------------------
SPIGOT_OD = 50.4        # drops into the basket; Dedica basket ID is ~51.0-51.3
SPIGOT_H = 2.5
SPIGOT_WALL = 1.2

MODULE = 1.5
Z_RING = 37
Z_PLANET = 23           # coprime with Z_RING -> 23-turn pattern period
PRESSURE_ANGLE = 20.0
BACKLASH = 0.35         # total, split between the two gears (FDM friendly)

PLANET_Z0 = 5.0         # planet bottom above the basket rim
PLANET_T = 8.0          # planet thickness = needle guide length
TOP_Z = 13.5            # top rim of base (carrier sits here)
LID_T = 4.0
SKIRT_BOTTOM_Z = 9.3
RING_WALL = 2.4         # base wall behind the ring-gear tooth roots
SKIRT_CLEAR = 0.25
SKIRT_WALL = 1.6
SNAP_DEPTH = 0.6        # groove depth in base
SNAP_BEAD = 0.45        # how far the bead reaches into the groove

PIN_D = 6.0
PIN_CLEAR = 0.5         # planet bore = PIN_D + PIN_CLEAR
KNOB_PEG_D = 5.0
KNOB_HOLE_CLEAR = 0.45  # peg spins freely
KNOB_R = 22.5           # knob position on lid

NEEDLE_HOLE = 0.7       # prints ~0.45-0.55 mm; open up with a hot needle
N_NEEDLES = 12
NEEDLE_REACH_MAX = 23.5  # keep tips inside the spigot (r = 24.0) and basket

STAND_DEPTH = 27.0

SEG = 180

TOP_R = MODULE * Z_RING / 2 + 1.25 * MODULE + 0.1 + RING_WALL  # under lid
GRIP_R = TOP_R + 1.0    # outer radius of base grip band


# --------------------------------------------------------------------------
# Gear geometry
# --------------------------------------------------------------------------
def inv(a):
    return math.tan(a) - a


def involute_gear_polygon(z, m, addendum, dedendum, thin, pa_deg=20.0,
                          flank_pts=14):
    """2D outline of an external involute spur gear.

    `thin` is the tooth-thickness reduction at the pitch circle (mm); a
    negative value makes teeth fatter (used for the ring-gear cavity).
    Tooth 0 is centred on +X.
    """
    pa = math.radians(pa_deg)
    rp = m * z / 2
    rb = rp * math.cos(pa)
    ra = rp + addendum
    rf = rp - dedendum
    half_pitch = (math.pi * m / 2 - thin) / (2 * rp)  # half tooth angle at rp

    def half_angle(r):
        if r <= rb:
            return half_pitch + inv(pa)
        return half_pitch + inv(pa) - inv(math.acos(rb / r))

    radii = np.linspace(max(rf, 0.1), ra, flank_pts)
    # make sure base circle is sampled for a clean radial->involute join
    if rf < rb < ra:
        radii = np.unique(np.concatenate([radii, [rb]]))
    pts = []
    step = 2 * math.pi / z
    for i in range(z):
        c = i * step
        right = [(r, c - half_angle(r)) for r in radii]
        left = [(r, c + half_angle(r)) for r in radii[::-1]]
        tooth = right + left
        pts += tooth
        # root arc to next tooth
        a0 = c + half_angle(radii[0])
        a1 = c + step - half_angle(radii[0])
        if a1 > a0:
            for t in np.linspace(a0, a1, 5)[1:-1]:
                pts.append((rf, t))
    return [(r * math.cos(t), r * math.sin(t)) for r, t in pts]


def ring_pitch_r():
    return MODULE * Z_RING / 2


def planet_pitch_r():
    return MODULE * Z_PLANET / 2


def center_distance():
    return ring_pitch_r() - planet_pitch_r()


def planet_section():
    m = MODULE
    return CrossSection([involute_gear_polygon(
        Z_PLANET, m, addendum=m, dedendum=1.25 * m, thin=BACKLASH / 2,
        pa_deg=PRESSURE_ANGLE)])


def ring_cavity_section():
    # Ring tooth spaces == external tooth shape; addendum/dedendum swapped.
    m = MODULE
    return CrossSection([involute_gear_polygon(
        Z_RING, m, addendum=1.25 * m, dedendum=m, thin=-BACKLASH / 2,
        pa_deg=PRESSURE_ANGLE, flank_pts=16)])


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def revolve_profile(rz):
    """Revolve a closed (r, z) polygon around Z."""
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in
               zip(rz, rz[1:] + rz[:1]))
    if area < 0:
        rz = rz[::-1]
    return Manifold.revolve(CrossSection([rz]), SEG)


def cyl(h, r, r2=None, z0=0.0, seg=SEG):
    c = Manifold.cylinder(h, r, r if r2 is None else r2, seg)
    return c.translate((0, 0, z0))


def box(sx, sy, sz, cx=0, cy=0, z0=0):
    return Manifold.cube((sx, sy, sz), True).translate((cx, cy, z0 + sz / 2))


def radial_ribs(n, r_in, r_out, width, z0, h):
    ribs = []
    for i in range(n):
        rib = box(r_out - r_in, width, h, cx=(r_in + r_out) / 2, z0=z0)
        ribs.append(rib.rotate((0, 0, 360 * i / n)))
    return Manifold.batch_boolean(ribs, _union())


def _union():
    from manifold3d import OpType
    return OpType.Add


def snap_pin(d, length, barb, split_len, slot_w, z0, direction=-1):
    """Split snap pin starting at z0 going in `direction` (+1 up, -1 down)."""
    r = d / 2
    tip_cone = 1.6
    body = cyl(length, r)
    barb_part = cyl(tip_cone, r + barb, r - 0.35, z0=length)   # 45°-ish flare
    pin = body + barb_part
    slot = box(slot_w, d + 2 * barb + 2, split_len + 0.01,
               z0=length + tip_cone - split_len)
    pin = pin - slot
    if direction < 0:
        pin = pin.mirror((0, 0, 1))
    return pin.translate((0, 0, z0))


# --------------------------------------------------------------------------
# Parts (all modelled in assembly coordinates; z = 0 is the basket rim)
# --------------------------------------------------------------------------
def make_base():
    rr = ring_pitch_r()
    root_r = rr + 1.25 * MODULE + 0.1
    spigot_ro = SPIGOT_OD / 2
    spigot_ri = spigot_ro - SPIGOT_WALL
    # 45° cone under the ring so the part prints upside down with no support
    cone_top = PLANET_Z0 - 0.6
    cone_bot = cone_top - (root_r - spigot_ri)
    groove_zc = 10.6
    g0, g1 = groove_zc - 0.8, groove_zc + 0.8
    gr = TOP_R - SNAP_DEPTH
    outer = [
        (spigot_ri, -SPIGOT_H),
        (spigot_ro - 0.6, -SPIGOT_H),
        (spigot_ro, -SPIGOT_H + 0.6),
        (spigot_ro, 0.0),
        (GRIP_R - 0.6, 0.0),
        (GRIP_R, 0.6),
        (GRIP_R, SKIRT_BOTTOM_Z - 0.4 - (GRIP_R - TOP_R)),
        (TOP_R, SKIRT_BOTTOM_Z - 0.4),
        (TOP_R, g0 - SNAP_DEPTH),
        (gr, g0),
        (gr, g1),
        (TOP_R, g1 + SNAP_DEPTH),
        (TOP_R, TOP_Z),
        (root_r, TOP_Z),
        (root_r, cone_top),
        (spigot_ri, max(cone_bot, 0.4)),
    ]
    body = revolve_profile(outer)
    # ring gear teeth: body keeps material between tooth spaces
    ring_zone = cyl(TOP_Z - cone_top + 0.01, root_r + 0.2, z0=cone_top - 0.01)
    teeth_solid = ring_zone - ring_cavity_section().extrude(
        TOP_Z - cone_top + 0.4).translate((0, 0, cone_top - 0.2))
    base = body + teeth_solid
    # tooth-tip chamfer at the top so the planet drops in easily
    tip_r = rr - MODULE
    base = base - cyl(0.8, tip_r - 0.01, tip_r + 0.8, z0=TOP_Z - 0.79)
    # grip ribs
    base = base + radial_ribs(48, GRIP_R - 0.2, GRIP_R + 0.7, 1.2, 1.2,
                              SKIRT_BOTTOM_Z - 2.6)
    return base


def needle_positions():
    """(x, y) of needle holes in planet-local coords, plus their offset d."""
    rp = planet_pitch_r()
    a = center_distance()
    d_max = min(rp - 1.25 * MODULE - 1.3, NEEDLE_REACH_MAX - a)
    d_min = PIN_D / 2 + PIN_CLEAR / 2 + 1.9
    # bias spacing outward: the rim of the puck is the biggest area and the
    # most channeling-prone, so more needles sweep there
    ds = d_min + (d_max - d_min) * np.linspace(0, 1, N_NEEDLES) ** 0.6
    golden = math.pi * (3 - math.sqrt(5))
    pts = []
    for i, d in enumerate(ds):
        t = i * golden
        pts.append((d * math.cos(t), d * math.sin(t), d))
    # sanity: holes at least 2 mm apart
    for i in range(len(pts)):
        for j in range(i):
            dd = math.dist(pts[i][:2], pts[j][:2])
            assert dd > 2.0, f"needles {i},{j} too close ({dd:.2f})"
    return pts


def make_planet():
    p = planet_section().extrude(PLANET_T)
    bore_r = (PIN_D + PIN_CLEAR) / 2
    p = p - cyl(PLANET_T + 1, bore_r, z0=-0.5)
    # chamfer on the bottom of the bore: the snap barb seats here
    p = p - cyl(0.7, bore_r + 0.6, bore_r - 0.1, z0=-0.01)
    # top chamfer on the bore for easy insertion
    p = p - cyl(0.6, bore_r - 0.01, bore_r + 0.6, z0=PLANET_T - 0.59)
    for x, y, _ in needle_positions():
        h = cyl(PLANET_T + 1, NEEDLE_HOLE / 2, z0=-0.5, seg=16)
        # countersink on top: guides the needle in and holds a glue drop
        cs = cyl(0.8, NEEDLE_HOLE / 2, NEEDLE_HOLE / 2 + 0.8,
                 z0=PLANET_T - 0.79, seg=24)
        p = p - (h + cs).translate((x, y, 0))
    # small marker dimple so you know which face is up
    p = p - cyl(0.6, 1.0, z0=PLANET_T - 0.59).translate((-(PIN_D / 2 + 2.4), 0, 0))
    return p.translate((0, 0, PLANET_Z0))


def make_carrier():
    a = center_distance()
    skirt_ri = TOP_R + SKIRT_CLEAR
    skirt_ro = skirt_ri + SKIRT_WALL
    disc = cyl(LID_T, skirt_ro, z0=TOP_Z)
    skirt = cyl(TOP_Z - SKIRT_BOTTOM_Z + 0.01, skirt_ro, z0=SKIRT_BOTTOM_Z) - \
        cyl(TOP_Z - SKIRT_BOTTOM_Z + 1, skirt_ri, z0=SKIRT_BOTTOM_Z - 0.5)
    # snap bead (double 45° chamfer, sits in the base groove)
    groove_zc = 10.6
    bead = revolve_profile([
        (skirt_ri - SNAP_BEAD, groove_zc - 0.25),
        (skirt_ri - SNAP_BEAD, groove_zc + 0.25),
        (skirt_ri + 0.05, groove_zc + 0.25 + SNAP_BEAD + 0.05),
        (skirt_ri + 0.05, groove_zc - 0.25 - SNAP_BEAD - 0.05),
    ])
    lid = disc + skirt + bead
    # slots make the skirt springy
    for i in range(8):
        s = box(6.0, 1.2, TOP_Z - SKIRT_BOTTOM_Z + 0.5,
                cx=skirt_ri + 1.0, z0=SKIRT_BOTTOM_Z - 0.3)
        lid = lid - s.rotate((0, 0, 360 * i / 8 + 22.5))
    # finger grip ribs around the lid rim
    lid = lid + radial_ribs(60, skirt_ro - 0.3, skirt_ro + 0.6, 1.0,
                            TOP_Z + 0.6, LID_T - 1.2)
    # planet axle: snap pin hanging down from the lid
    pin_len = TOP_Z - PLANET_Z0 + 0.05
    pin = snap_pin(PIN_D, pin_len, barb=0.45, split_len=6.0, slot_w=1.4,
                   z0=TOP_Z, direction=-1)
    # small fillet where pin meets the lid; doubles as the planet's thrust
    # washer so the planet only rubs here, not on the whole lid
    pin = pin + cyl(0.4, PIN_D / 2 + 1.2, PIN_D / 2 + 0.8, z0=TOP_Z - 0.4)
    lid = lid + pin.translate((a, 0, 0))
    # knob hole with counterbore (barb seats inside the lid thickness)
    kh = cyl(LID_T + 1, (KNOB_PEG_D + KNOB_HOLE_CLEAR) / 2, z0=TOP_Z - 0.5)
    kc = cyl(1.8, KNOB_PEG_D / 2 + 1.3, z0=TOP_Z - 0.01)
    lid = lid - (kh + kc).translate((-KNOB_R, 0, 0))
    return lid


def make_knob():
    # modelled with its seat at z = 0, peg pointing up (print orientation)
    flange = cyl(1.2, 8.0) + cyl(0.8, 8.0, 7.2, z0=1.2)
    body = cyl(20.0, 6.5, z0=0.0) + cyl(1.2, 6.5, 5.9, z0=20.0)
    peg_len = LID_T - 1.8 + 0.25   # through the lid to the counterbore
    peg = snap_pin(KNOB_PEG_D, peg_len, barb=0.45, split_len=4.0, slot_w=1.2,
                   z0=0.0, direction=+1)
    knob = body.mirror((0, 0, 1)) + flange.mirror((0, 0, 1)).translate((0, 0, 0)) \
        + peg
    # knob grip ribs
    for i in range(12):
        g = box(1.2, 1.2, 16, cx=6.5, z0=-18).rotate((0, 0, 30 * i))
        knob = knob + g
    return knob   # z = 0 is the lid top face, body goes -z, peg +z


def make_stand():
    ri = SPIGOT_OD / 2 + 0.5
    ro = GRIP_R + 0.7
    floor = 2.0
    cup = revolve_profile([
        (0, 0), (ro - 0.8, 0), (ro, 0.8), (ro, floor + STAND_DEPTH),
        (ri + 1.0, floor + STAND_DEPTH), (ri, floor + STAND_DEPTH - 1.0),
        (ri, floor), (0, floor),
    ])
    return cup


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------
def check_mesh(steps=720):
    """Rotate carrier through a full planet period and look for overlap."""
    ring = CrossSection.circle(ring_pitch_r() + 5, 256) - ring_cavity_section()
    planet = planet_section()
    a = center_distance()
    worst = 0.0
    for k in range(steps):
        phic = 2 * math.pi * k / steps
        phip = phic * (1 - Z_RING / Z_PLANET)
        p = planet.rotate(math.degrees(phip)).translate(
            (a * math.cos(phic), a * math.sin(phic)))
        worst = max(worst, (p ^ ring).area())
    return worst


def check_clearances(base, carrier, planet):
    out = {}
    out["planet∩base"] = (planet ^ base).volume()
    out["planet∩carrier"] = (planet ^ carrier).volume()
    out["carrier∩base"] = (carrier ^ base).volume()
    return out


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
def to_trimesh(m):
    import trimesh
    mesh = m.to_mesh()
    return trimesh.Trimesh(np.array(mesh.vert_properties)[:, :3],
                           np.array(mesh.tri_verts), process=False)


def write_3mf(path, parts):
    """Minimal core-spec 3MF (opens in Bambu Studio / Orca / Prusa)."""
    objs, items = [], []
    for i, (name, tm, (tx, ty)) in enumerate(parts, start=1):
        v = "\n".join(f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>'
                      for x, y, z in tm.vertices)
        t = "\n".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>'
                      for a, b, c in tm.faces)
        objs.append(f'<object id="{i}" name="{name}" type="model"><mesh>'
                    f'<vertices>{v}</vertices><triangles>{t}</triangles>'
                    f'</mesh></object>')
        # slicers put the origin at the plate corner: centre on a 256 mm bed
        items.append(f'<item objectid="{i}" transform="1 0 0 0 1 0 0 0 1 '
                     f'{tx + 128:.3f} {ty + 128:.3f} 0"/>')
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             '<metadata name="Title">Spiro51 WDT for DeLonghi Dedica</metadata>'
             f'<resources>{"".join(objs)}</resources>'
             f'<build>{"".join(items)}</build></model>')
    ctypes = ('<?xml version="1.0" encoding="UTF-8"?>\n'
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
              'content-types"><Default Extension="rels" ContentType="'
              'application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Default Extension="model" ContentType="'
              'application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
            '2006/relationships"><Relationship Target="/3D/3dmodel.model" '
            'Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/'
            '2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ctypes)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)


def print_orientation(name, m):
    """Move each part into its support-free print orientation, on z = 0."""
    if name in ("base", "carrier"):
        m = m.mirror((0, 0, 1))            # print upside down
    lo = m.bounding_box()[2]
    return m.translate((0, 0, -lo))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "out")
    os.makedirs(out, exist_ok=True)

    base = make_base()
    planet = make_planet()
    carrier = make_carrier()
    knob = make_knob()
    stand = make_stand()

    print(f"ring pitch dia {2 * ring_pitch_r():.2f}, planet pitch dia "
          f"{2 * planet_pitch_r():.2f}, centre distance {center_distance():.2f}")
    for x, y, d in needle_positions():
        a = center_distance()
        print(f"  needle d={d:5.2f}  sweeps r {abs(a - d):5.2f} .. {a + d:5.2f}")
    print("gear overlap area over full cycle (mm²):", round(check_mesh(), 4))
    a = center_distance()
    planet_asm = planet.translate((a, 0, 0))
    print("assembly interference volumes (mm³):",
          {k: round(v, 4) for k, v in
           check_clearances(base, carrier, planet_asm).items()})

    parts = {
        "base": base, "planet": planet, "carrier": carrier,
        "knob": knob, "stand": stand,
    }
    layout = {"base": (-40, 40), "carrier": (40, 40), "stand": (-40, -40),
              "planet": (30, -35), "knob": (62, -62)}
    tms = []
    for name, m in parts.items():
        pm = print_orientation(name, m)
        tm = to_trimesh(pm)
        assert tm.is_watertight, name
        tm.export(os.path.join(out, f"spiro51_{name}.stl"))
        tms.append((f"Spiro51 {name}", tm, layout[name]))
        bb = pm.bounding_box()
        print(f"{name:8s} {bb[3] - bb[0]:6.1f} x {bb[4] - bb[1]:6.1f} x "
              f"{bb[5] - bb[2]:5.1f} mm  vol {pm.volume() / 1000:5.1f} cm³")
    write_3mf(os.path.join(out, "spiro51_dedica_wdt.3mf"), tms)

    # assembly for previews
    knob_asm = knob.mirror((0, 0, 1)).translate((-KNOB_R, 0, TOP_Z + LID_T))
    asm = {"base": base, "planet": planet_asm, "carrier": carrier,
           "knob": knob_asm}
    print("carrier∩knob:", round((carrier ^ knob_asm).volume(), 4))
    return asm, parts


if __name__ == "__main__":
    main()
