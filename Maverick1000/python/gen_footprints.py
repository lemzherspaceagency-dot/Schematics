#!/usr/bin/env python3
"""
Generate the two custom footprints this design needs that aren't in the
stock KiCad 7 footprint libraries: the Hirose DF40C-100DS-0.4V (CM4 socket)
and the Hirose DF13-22DP-1.25V (Terra payload connector).

Both are documented APPROXIMATIONS built from the connector series' typical
published dimensions (pitch, row count, pad style) -- see
docs/assumptions.md #2. Verify against the manufacturer's mechanical
drawing before ordering boards; this is flagged as the top manufacturing
risk in this project.
"""

OUT_DIR = "/home/user/Schematics/Maverick1000/kicad/libraries/footprints/SKYWARD_Custom.pretty"


def fp_line(x1, y1, x2, y2, layer, width=0.1):
    return f"  (fp_line (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f})\n    (stroke (width {width}) (type solid)) (layer {layer}))\n"


def fp_rect_outline(hw, hh, layer, width=0.1):
    return (fp_line(-hw, -hh, hw, -hh, layer, width) +
            fp_line(hw, -hh, hw, hh, layer, width) +
            fp_line(hw, hh, -hw, hh, layer, width) +
            fp_line(-hw, hh, -hw, -hh, layer, width))


def pad(number, x, y, w, h, shape="rect", ptype="smd", drill=None, layers="F.Cu F.Mask F.Paste"):
    if ptype == "thru_hole":
        return (f"  (pad {number} thru_hole {shape} (at {x:.3f} {y:.3f}) (size {w} {h}) "
                f"(drill {drill}) (layers *.Cu *.Mask))\n")
    return f"  (pad {number} smd {shape} (at {x:.3f} {y:.3f}) (size {w} {h}) (layers {layers}))\n"


def dual_row_connector(name, n_pins, pitch, row_spacing, pad_w, pad_h, descr, tags):
    half = n_pins // 2
    row_len = (half - 1) * pitch
    hw = row_len / 2 + pad_w
    hh = row_spacing / 2 + pad_h
    body = []
    body.append(f"(footprint {name} (version 20221018) (generator SKYWARD_gen_footprints.py)\n")
    body.append("  (layer F.Cu)\n")
    body.append(f'  (descr "{descr}")\n')
    body.append(f'  (tags "{tags}")\n')
    body.append("  (attr smd)\n")
    body.append(f"  (fp_text reference REF** (at 0 {-hh - 1.2:.3f}) (layer F.SilkS)\n"
                 "    (effects (font (size 1 1) (thickness 0.15))))\n")
    body.append(f"  (fp_text value {name} (at 0 {hh + 1.2:.3f}) (layer F.Fab)\n"
                 "    (effects (font (size 1 1) (thickness 0.15))))\n")
    # Fab outline
    body.append(fp_rect_outline(hw, hh, "F.Fab", 0.1))
    # Silkscreen outline, with a corner notch avoided (kept clear of pads)
    body.append(fp_line(-hw - 0.15, -hh - 0.15, hw + 0.15, -hh - 0.15, "F.SilkS", 0.12))
    body.append(fp_line(-hw - 0.15, hh + 0.15, hw + 0.15, hh + 0.15, "F.SilkS", 0.12))
    # Pin-1 marker: small filled triangle at top-left, on silkscreen
    p1x = -row_len / 2
    p1y = -row_spacing / 2
    body.append(
        f"  (fp_poly (pts (xy {p1x - pad_w:.3f} {p1y - pad_h*1.4:.3f}) "
        f"(xy {p1x - pad_w + 0.6:.3f} {p1y - pad_h*1.4:.3f}) "
        f"(xy {p1x - pad_w + 0.3:.3f} {p1y - pad_h*1.4 - 0.6:.3f})) "
        f"(layer F.SilkS) (width 0))\n"
    )
    # Courtyard
    body.append(fp_rect_outline(hw + 0.25, hh + 0.25, "F.CrtYd", 0.05))
    # Pads: row 1 = pins 1..half (top, y = -row_spacing/2), row 2 = half+1..n (bottom)
    for i in range(1, half + 1):
        x = -row_len / 2 + (i - 1) * pitch
        y = -row_spacing / 2
        shape = "roundrect" if i != 1 else "rect"
        body.append(pad(i, x, y, pad_w, pad_h, shape=shape))
    for i in range(half + 1, n_pins + 1):
        x = -row_len / 2 + (i - half - 1) * pitch
        y = row_spacing / 2
        body.append(pad(i, x, y, pad_w, pad_h, shape="roundrect"))
    body.append(")\n")
    return "".join(body)


def dual_row_odd_even_connector(name, n_pins, pitch, row_spacing, pad_w, pad_h, descr, tags):
    """Odd/even numbering: pin 1,3,5...(n-1) down one row, pin 2,4,6...n
    down the other, with pin k and pin k+1 sharing an X position (adjacent
    contacts, opposite rows) -- the scheme the REAL Hirose DF40C-100DS-0.4V
    uses (confirmed via an independent audit that proved it by matching the
    CM4 datasheet's differential-pair assignments; see
    docs/DF40C_FOOTPRINT_VERIFICATION.md). A sequential top-then-bottom
    layout, which this generator used before that finding, is WRONG for
    this specific connector."""
    half = n_pins // 2
    row_len = (half - 1) * pitch
    hw = row_len / 2 + pad_w
    hh = row_spacing / 2 + pad_h
    body = []
    body.append(f"(footprint {name} (version 20221018) (generator SKYWARD_gen_footprints.py)\n")
    body.append("  (layer F.Cu)\n")
    body.append(f'  (descr "{descr}")\n')
    body.append(f'  (tags "{tags}")\n')
    body.append("  (attr smd)\n")
    body.append(f"  (fp_text reference REF** (at 0 {-hh - 1.2:.3f}) (layer F.SilkS)\n"
                 "    (effects (font (size 1 1) (thickness 0.15))))\n")
    body.append(f"  (fp_text value {name} (at 0 {hh + 1.2:.3f}) (layer F.Fab)\n"
                 "    (effects (font (size 1 1) (thickness 0.15))))\n")
    body.append(fp_rect_outline(hw, hh, "F.Fab", 0.1))
    body.append(fp_line(-hw - 0.15, -hh - 0.15, hw + 0.15, -hh - 0.15, "F.SilkS", 0.12))
    body.append(fp_line(-hw - 0.15, hh + 0.15, hw + 0.15, hh + 0.15, "F.SilkS", 0.12))
    p1x = -row_len / 2
    p1y = -row_spacing / 2
    body.append(
        f"  (fp_poly (pts (xy {p1x - pad_w:.3f} {p1y - pad_h*1.4:.3f}) "
        f"(xy {p1x - pad_w + 0.6:.3f} {p1y - pad_h*1.4:.3f}) "
        f"(xy {p1x - pad_w + 0.3:.3f} {p1y - pad_h*1.4 - 0.6:.3f})) "
        f"(layer F.SilkS) (width 0))\n"
    )
    body.append(fp_rect_outline(hw + 0.25, hh + 0.25, "F.CrtYd", 0.05))
    for k in range(half):
        x = -row_len / 2 + k * pitch
        odd_pin = 2 * k + 1
        even_pin = 2 * k + 2
        body.append(pad(odd_pin, x, -row_spacing / 2, pad_w, pad_h,
                         shape="rect" if odd_pin == 1 else "roundrect"))
        body.append(pad(even_pin, x, row_spacing / 2, pad_w, pad_h, shape="roundrect"))
    body.append(")\n")
    return "".join(body)


def main():
    import os
    os.makedirs(OUT_DIR, exist_ok=True)

    cm4 = dual_row_odd_even_connector(
        "Hirose_DF40C-100DS-0.4V", 100, pitch=0.4, row_spacing=3.0,
        pad_w=0.25, pad_h=0.9,
        descr=("Hirose DF40C-100DS-0.4V(51), 100-pos 0.4mm pitch SMD receptacle, "
               "CM4 module connector. Odd/even row pad numbering (pin 1,3,5.. one "
               "row, 2,4,6.. the other) -- CONFIRMED correct scheme (not sequential "
               "top-then-bottom), see docs/DF40C_FOOTPRINT_VERIFICATION.md. Pad "
               "size/pitch/row-spacing are still a documented dimensional "
               "APPROXIMATION -- verify against the manufacturer drawing before "
               "fabrication (docs/assumptions.md #2)."),
        tags="hirose df40 cm4 raspberry pi high density 0.4mm odd_even")
    with open(f"{OUT_DIR}/Hirose_DF40C-100DS-0.4V.kicad_mod", "w") as f:
        f.write(cm4)

    terra = dual_row_connector(
        "Hirose_DF13-22DP-1.25V", 22, pitch=1.25, row_spacing=2.0,
        pad_w=0.6, pad_h=1.3,
        descr=("Hirose DF13-22DP-1.25V, 22-pos 1.25mm pitch wire-to-board "
               "connector, Maverick 1000 Terra payload bus. APPROXIMATE "
               "geometry -- verify against manufacturer drawing before "
               "fabrication (docs/assumptions.md #2)."),
        tags="hirose df13 terra payload 1.25mm")
    with open(f"{OUT_DIR}/Hirose_DF13-22DP-1.25V.kicad_mod", "w") as f:
        f.write(terra)

    print(f"Wrote {OUT_DIR}/Hirose_DF40C-100DS-0.4V.kicad_mod (100 pads)")
    print(f"Wrote {OUT_DIR}/Hirose_DF13-22DP-1.25V.kicad_mod (22 pads)")

    bq = bq25792_footprint()
    with open(f"{OUT_DIR}/QFN-29_L4.0-W4.0-P0.40-BQ25792RQMR.kicad_mod", "w") as f:
        f.write(bq)
    print(f"Wrote {OUT_DIR}/QFN-29_L4.0-W4.0-P0.40-BQ25792RQMR.kicad_mod (29 pads + EP)")


# Real perimeter pad coordinates for the BQ25792RQMR WQFN-29 (4x4mm,
# 0.4mm pitch) package, cross-checked against an independent open-source
# KiCad footprint for the same part (see docs/BQ25792_VERIFICATION.md).
# (pin_number, x, y, rot, w, h)
_BQ25792_PADS = [
    (1, -1.35, -1.6, 0, 0.2, 0.7),
    (2, -1.9, -1.2, 0, 0.6, 0.2), (3, -1.9, -0.8, 0, 0.6, 0.2),
    (4, -1.9, -0.4, 0, 0.6, 0.2), (5, -1.9, 0.0, 0, 0.6, 0.2),
    (6, -1.9, 0.4, 0, 0.6, 0.2), (7, -1.9, 0.8, 0, 0.6, 0.2),
    (8, -1.9, 1.2, 0, 0.6, 0.2),
    (9, -1.4, 1.6, 180, 0.2, 0.7),
    (10, -1.0, 1.9, 0, 0.2, 0.6), (11, -0.6, 1.9, 0, 0.2, 0.6),
    (12, -0.2, 1.9, 0, 0.2, 0.6), (13, 0.2, 1.9, 0, 0.2, 0.6),
    (14, 0.6, 1.9, 0, 0.2, 0.6), (15, 1.0, 1.9, 0, 0.2, 0.6),
    (16, 1.4, 1.6, 180, 0.2, 0.7),
    (17, 1.85, 1.2, 0, 0.7, 0.2), (18, 1.875, 0.8, 0, 0.65, 0.2),
    (19, 1.8625, 0.4, 0, 0.68, 0.2), (20, 1.9, 0.0, 0, 0.6, 0.2),
    (21, 1.9, -0.4, 0, 0.6, 0.2), (22, 1.9, -0.8, 0, 0.6, 0.2),
    (23, 1.9, -1.2, 0, 0.6, 0.2),
    (24, 1.35, -1.6, 0, 0.2, 0.7),
    (25, 0.9, -1.7, 0, 0.22, 1.0), (26, 0.45, -1.7, 0, 0.22, 1.0),
    (27, 0.0, -1.7, 0, 0.22, 1.0), (28, -0.45, -1.7, 0, 0.22, 1.0),
    (29, -0.9, -1.725, 0, 0.22, 0.95),
]


def bq25792_footprint():
    name = "QFN-29_L4.0-W4.0-P0.40-BQ25792RQMR"
    hw, hh = 2.2, 2.2  # courtyard half-size for a 4x4mm body + pad overhang
    body = [f"(footprint {name} (version 20221018) (generator SKYWARD_gen_footprints.py)\n"]
    body.append("  (layer F.Cu)\n")
    body.append(
        '  (descr "TI BQ25792RQMR, WQFN-29 4x4mm 0.4mm pitch. Real perimeter pad '
        'coordinates cross-checked against an independent open-source KiCad '
        'footprint for the same part (see docs/BQ25792_VERIFICATION.md). The '
        'exposed thermal/ground pad (EP) below is a DOCUMENTED ASSUMPTION -- the '
        'reference footprint that supplied the perimeter pad coordinates did not '
        'include one, but WQFN packages in this TI family normally have a large '
        'center EP; a conservative 1.8x1.4mm EP is added here rather than omitted, '
        'since omitting a real EP would be the worse error for a 5A charger IC. '
        'Sized specifically to keep >=0.2mm clearance to every perimeter pad '
        '(a first pass at 2.4x2.4mm was found, by real KiCad DRC, to touch the '
        'bottom-row pads with 0.0mm clearance -- this smaller size is verified '
        'clearance-clean but is almost certainly smaller than the real EP, which '
        'is normally sized to nearly the full pitch envelope between pad rows. '
        'VERIFY EP size against the TI mechanical drawing before fabrication.")\n'
    )
    body.append(f'  (tags "BQ25792RQMR QFN-29 WQFN 0.4mm charger")\n')
    body.append("  (attr smd)\n")
    body.append(f"  (fp_text reference REF** (at 0 {-hh-1.2:.3f}) (layer F.SilkS)\n"
                 "    (effects (font (size 1 1) (thickness 0.15))))\n")
    body.append(f"  (fp_text value {name} (at 0 {hh+1.2:.3f}) (layer F.Fab)\n"
                 "    (effects (font (size 1 1) (thickness 0.15))))\n")
    body.append(fp_rect_outline(2.0, 2.0, "F.Fab", 0.1))
    body.append(fp_rect_outline(hw, hh, "F.CrtYd", 0.05))
    # pin-1 marker
    body.append(
        f"  (fp_poly (pts (xy -2.3 -1.9) (xy -1.7 -1.9) (xy -2.0 -1.4)) "
        f"(layer F.SilkS) (width 0))\n"
    )
    for num, x, y, rot, w, h in _BQ25792_PADS:
        shape = "rect" if num == 1 else "roundrect"
        if rot:
            body.append(
                f"  (pad {num} smd {shape} (at {x:.3f} {y:.3f} {rot}) (size {w} {h}) "
                f"(layers F.Cu F.Mask F.Paste))\n"
            )
        else:
            body.append(pad(num, x, y, w, h, shape=shape))
    # exposed pad / thermal pad, numbered 30, tied to GND/PGND in the netlist
    # -- documented assumption, see descr above. Sized 1.8x1.4mm (not square)
    # specifically to clear the bottom-row pads (25-29), which are closer to
    # center than the side/top rows on this real perimeter pad layout.
    body.append(pad(30, 0, 0, 1.8, 1.4, shape="roundrect"))
    body.append(")\n")
    return "".join(body)


if __name__ == "__main__":
    main()
