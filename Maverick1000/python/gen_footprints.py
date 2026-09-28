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
        "Hirose_DF40C-100DS-0.4V", 100, pitch=0.4, row_spacing=3.08,
        pad_w=0.2, pad_h=0.7,
        descr=("Hirose DF40C-100DS-0.4V(51), 100-pos 0.4mm pitch SMD receptacle, "
               "CM4 module connector. Odd/even row pad numbering (pin 1,3,5.. one "
               "row, 2,4,6.. the other) -- CONFIRMED correct scheme (not sequential "
               "top-then-bottom), see docs/DF40C_FOOTPRINT_VERIFICATION.md. Pitch, "
               "row spacing (3.08mm), and pad size (0.2x0.7mm) are now CONFIRMED "
               "against two independent real shipped-product KiCad footprints "
               "(NabuCasa/yellow, hatlabs/HALPI2-hardware) that both cite Hirose's "
               "own official 2D-drawing document URL and agree byte-for-byte -- "
               "see docs/DF40C_FOOTPRINT_VERIFICATION.md."),
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

    ec25 = ec25_lcc_footprint()
    with open(f"{OUT_DIR}/LCC-132_EC25_verified.kicad_mod", "w") as f:
        f.write(ec25)
    print(f"Wrote {OUT_DIR}/LCC-132_EC25_verified.kicad_mod (132 real pads, verified against a real OLIMEX EG25-G footprint)")

    sim = sim_holder_footprint()
    with open(f"{OUT_DIR}/SIM_NanoSIM_6Pin_generic.kicad_mod", "w") as f:
        f.write(sim)
    print(f"Wrote {OUT_DIR}/SIM_NanoSIM_6Pin_generic.kicad_mod (6 pads, generic/UNVERIFIED)")


# Real pad geometry for the Quectel EC25/EG25-family LCC package (144
# castellation positions, 132 physically real -- pins 73-84 are absent on
# the real part, matching this project's independently-sourced EC25
# pinout exactly, see docs/EC25_FOOTPRINT_VERIFICATION.md). Sourced from
# a real, open-hardware KiCad footprint for the pin/footprint-compatible
# Quectel EG25-G sibling module (OLIMEX/KiCAD on GitHub,
# KiCAD_Footprints/OLIMEX_Cases-FP.pretty/Quectel_EG25-G_Module_LGA-144_
# 32.0mmx29.0mmx2.4mm.kicad_mod). Quectel documents EC25/EG25/EC21/EG21
# as a single mechanically/pin-compatible module family in one combined
# Hardware Design guide -- see docs/EC25_FOOTPRINT_VERIFICATION.md for
# the full sourcing writeup and what remains an assumption (this project
# has not independently obtained Quectel's own PDF to confirm the
# compatibility claim beyond the strong internal evidence of the
# matching 132-real-pin/73-84-gap layout).
# (pin_number, x_mm, y_mm, rotation_deg, pad_w_mm, pad_h_mm, is_real_pad)
_EC25_PADS = [
    (1, -12.6, 15.75, 270, 2.5, 0.8, True),
    (2, -11.3, 15.75, 270, 2.5, 0.8, True),
    (3, -10.0, 15.75, 270, 2.5, 0.8, True),
    (4, -8.7, 15.75, 270, 2.5, 0.8, True),
    (5, -7.4, 15.75, 270, 2.5, 0.8, True),
    (6, -6.1, 15.75, 270, 2.5, 0.8, True),
    (7, -4.8, 15.75, 270, 2.5, 0.8, True),
    (8, -0.4, 15.75, 270, 2.5, 0.8, True),
    (9, 0.9, 15.75, 270, 2.5, 0.8, True),
    (10, 2.2, 15.75, 270, 2.5, 0.8, True),
    (11, 3.5, 15.75, 270, 2.5, 0.8, True),
    (12, 4.8, 15.75, 270, 2.5, 0.8, True),
    (13, 6.1, 15.75, 270, 2.5, 0.8, True),
    (14, 7.4, 15.75, 270, 2.5, 0.8, True),
    (15, 8.7, 15.75, 270, 2.5, 0.8, True),
    (16, 10.0, 15.75, 270, 2.5, 0.8, True),
    (17, 11.3, 15.75, 270, 2.5, 0.8, True),
    (18, 12.6, 15.75, 270, 2.5, 0.8, True),
    (19, 14.25, 9.55, 0, 2.5, 0.8, True),
    (20, 14.25, 8.25, 0, 2.5, 0.8, True),
    (21, 14.25, 6.95, 0, 2.5, 0.8, True),
    (22, 14.25, 5.65, 0, 2.5, 0.8, True),
    (23, 14.25, 4.35, 0, 2.5, 0.8, True),
    (24, 14.25, 3.05, 0, 2.5, 0.8, True),
    (25, 14.25, 1.75, 0, 2.5, 0.8, True),
    (26, 14.25, 0.45, 0, 2.5, 0.8, True),
    (27, 14.25, -0.85, 0, 2.5, 0.8, True),
    (28, 14.25, -2.15, 0, 2.5, 0.8, True),
    (29, 14.25, -3.45, 0, 2.5, 0.8, True),
    (30, 14.25, -4.75, 0, 2.5, 0.8, True),
    (31, 14.25, -6.05, 0, 2.5, 0.8, True),
    (32, 14.25, -7.35, 0, 2.5, 0.8, True),
    (33, 14.25, -8.65, 0, 2.5, 0.8, True),
    (34, 14.25, -9.95, 0, 2.5, 0.8, True),
    (35, 14.25, -11.25, 0, 2.5, 0.8, True),
    (36, 14.25, -12.55, 0, 2.5, 0.8, True),
    (37, 12.6, -15.75, 270, 2.5, 0.8, True),
    (38, 11.3, -15.75, 270, 2.5, 0.8, True),
    (39, 10.0, -15.75, 270, 2.5, 0.8, True),
    (40, 8.7, -15.75, 270, 2.5, 0.8, True),
    (41, 7.4, -15.75, 270, 2.5, 0.8, True),
    (42, 6.1, -15.75, 270, 2.5, 0.8, True),
    (43, 4.8, -15.75, 270, 2.5, 0.8, True),
    (44, 3.5, -15.75, 270, 2.5, 0.8, True),
    (45, 2.2, -15.75, 270, 2.5, 0.8, True),
    (46, 0.9, -15.75, 270, 2.5, 0.8, True),
    (47, -0.4, -15.75, 270, 2.5, 0.8, True),
    (48, -4.8, -15.75, 270, 2.5, 0.8, True),
    (49, -6.1, -15.75, 270, 2.5, 0.8, True),
    (50, -7.4, -15.75, 270, 2.5, 0.8, True),
    (51, -8.7, -15.75, 270, 2.5, 0.8, True),
    (52, -10.0, -15.75, 270, 2.5, 0.8, True),
    (53, -11.3, -15.75, 270, 2.5, 0.8, True),
    (54, -12.6, -15.75, 270, 2.5, 0.8, True),
    (55, -14.25, -12.55, 0, 2.5, 0.8, True),
    (56, -14.25, -11.25, 0, 2.5, 0.8, True),
    (57, -14.25, -9.95, 0, 2.5, 0.8, True),
    (58, -14.25, -8.65, 0, 2.5, 0.8, True),
    (59, -14.25, -7.35, 0, 2.5, 0.8, True),
    (60, -14.25, -6.05, 0, 2.5, 0.8, True),
    (61, -14.25, -4.75, 0, 2.5, 0.8, True),
    (62, -14.25, -3.45, 0, 2.5, 0.8, True),
    (63, -14.25, -2.15, 0, 2.5, 0.8, True),
    (64, -14.25, -0.85, 0, 2.5, 0.8, True),
    (65, -14.25, 0.45, 0, 2.5, 0.8, True),
    (66, -14.25, 1.75, 0, 2.5, 0.8, True),
    (67, -14.25, 3.05, 0, 2.5, 0.8, True),
    (68, -14.25, 4.35, 0, 2.5, 0.8, True),
    (69, -14.25, 5.65, 0, 2.5, 0.8, True),
    (70, -14.25, 6.95, 0, 2.5, 0.8, True),
    (71, -14.25, 8.25, 0, 2.5, 0.8, True),
    (72, -14.25, 9.55, 0, 2.5, 0.8, True),
    (73, -1.7, -2.5, 270, 1.1, 1.1, False),
    (74, 0.0, -2.5, 270, 1.1, 1.1, False),
    (75, 1.7, -2.49, 270, 1.1, 1.1, False),
    (76, -1.7, -0.835, 270, 1.1, 1.1, False),
    (77, 0.0, -0.835, 270, 1.1, 1.1, False),
    (78, 1.7, -0.825, 270, 1.1, 1.1, False),
    (79, -1.7, 0.835, 270, 1.1, 1.1, False),
    (80, 0.0, 0.835, 270, 1.1, 1.1, False),
    (81, 1.7, 0.845, 270, 1.1, 1.1, False),
    (82, -1.7, 2.5, 270, 1.1, 1.1, False),
    (83, 0.0, 2.5, 270, 1.1, 1.1, False),
    (84, 1.7, 2.51, 270, 1.1, 1.1, False),
    (85, -9.6, -8.2, 270, 2.0, 3.0, True),
    (86, -4.8, -8.2, 270, 2.0, 3.0, True),
    (87, 0.0, -8.2, 270, 2.0, 3.0, True),
    (88, 4.8, -8.2, 270, 2.0, 3.0, True),
    (89, 9.6, -8.2, 270, 2.0, 3.0, True),
    (90, -9.6, -5.0, 270, 2.0, 3.0, True),
    (91, -4.8, -5.0, 270, 2.0, 3.0, True),
    (92, 0.0, -5.0, 270, 2.0, 3.0, True),
    (93, 4.8, -5.0, 270, 2.0, 3.0, True),
    (94, 9.6, -5.0, 270, 2.0, 3.0, True),
    (95, -9.6, -1.6, 270, 2.0, 3.0, True),
    (96, -4.8, -1.6, 270, 2.0, 3.0, True),
    (97, 4.8, -1.6, 270, 2.0, 3.0, True),
    (98, 9.6, -1.6, 270, 2.0, 3.0, True),
    (99, -9.6, 1.6, 270, 2.0, 3.0, True),
    (100, -4.8, 1.6, 270, 2.0, 3.0, True),
    (101, 4.8, 1.6, 270, 2.0, 3.0, True),
    (102, 9.6, 1.6, 270, 2.0, 3.0, True),
    (103, -9.6, 5.0, 270, 2.0, 3.0, True),
    (104, -4.8, 5.0, 270, 2.0, 3.0, True),
    (105, 0.0, 5.0, 270, 2.0, 3.0, True),
    (106, 4.8, 5.0, 270, 2.0, 3.0, True),
    (107, 9.6, 5.0, 270, 2.0, 3.0, True),
    (108, -9.6, 8.2, 270, 2.0, 3.0, True),
    (109, -4.8, 8.2, 270, 2.0, 3.0, True),
    (110, 0.0, 8.2, 270, 2.0, 3.0, True),
    (111, 4.8, 8.2, 270, 2.0, 3.0, True),
    (112, 9.6, 8.2, 270, 2.0, 3.0, True),
    (113, -14.25, 10.85, 0, 2.5, 0.8, True),
    (114, -14.25, 12.15, 0, 2.5, 0.8, True),
    (115, 14.25, 10.85, 0, 2.5, 0.8, True),
    (116, 14.25, 12.15, 0, 2.5, 0.8, True),
    (117, -11.0, 11.0, 270, 1.1, 1.1, True),
    (118, -9.0, 11.0, 270, 1.1, 1.1, True),
    (119, -7.0, 11.0, 270, 1.1, 1.1, True),
    (120, -5.0, 11.0, 270, 1.1, 1.1, True),
    (121, -3.0, 11.0, 270, 1.1, 1.1, True),
    (122, -1.0, 11.0, 270, 1.1, 1.1, True),
    (123, 1.0, 11.0, 270, 1.1, 1.1, True),
    (124, 3.0, 11.0, 270, 1.1, 1.1, True),
    (125, 5.0, 11.0, 270, 1.1, 1.1, True),
    (126, 7.0, 11.0, 270, 1.1, 1.1, True),
    (127, 9.0, 11.0, 270, 1.1, 1.1, True),
    (128, 11.0, 11.0, 270, 1.1, 1.1, True),
    (129, -11.0, 13.0, 270, 1.1, 1.1, True),
    (130, -9.0, 13.0, 270, 1.1, 1.1, True),
    (131, -7.0, 13.0, 270, 1.1, 1.1, True),
    (132, -5.0, 13.0, 270, 1.1, 1.1, True),
    (133, -3.0, 13.0, 270, 1.1, 1.1, True),
    (134, -1.0, 13.0, 270, 1.1, 1.1, True),
    (135, 1.0, 13.0, 270, 1.1, 1.1, True),
    (136, 3.0, 13.0, 270, 1.1, 1.1, True),
    (137, 5.0, 13.0, 270, 1.1, 1.1, True),
    (138, 7.0, 13.0, 270, 1.1, 1.1, True),
    (139, 9.0, 13.0, 270, 1.1, 1.1, True),
    (140, 11.0, 13.0, 270, 1.1, 1.1, True),
    (141, -3.0, 15.75, 270, 2.5, 0.8, True),
    (142, -1.7, 15.75, 270, 2.5, 0.8, True),
    (143, -1.7, -15.75, 270, 2.5, 0.8, True),
    (144, -3.0, -15.75, 270, 2.5, 0.8, True),
]


def ec25_lcc_footprint():
    """Quectel EC25/EG25-family LCC module footprint -- real pad geometry.

    Real pad positions, sizes and rotations for all 144 castellation
    positions (132 real copper pads + 12 documentation-only markers for
    the physically-absent 73-84 gap), taken directly from a real,
    open-hardware KiCad footprint for the Quectel EG25-G module -- see
    _EC25_PADS above and docs/EC25_FOOTPRINT_VERIFICATION.md. This
    replaces the earlier proportional-perimeter-distribution
    APPROXIMATION (see git history) that this project previously shipped
    and explicitly flagged as an unresolved fabrication blocker.
    """
    name = "LCC-132_EC25_verified"
    body_w, body_h = 29.0, 32.0  # real F.Fab outline from the source footprint
    hw, hh = body_w / 2, body_h / 2

    body = [f"(footprint {name} (version 20221018) (generator SKYWARD_gen_footprints.py)\n"]
    body.append("  (layer F.Cu)\n")
    body.append(
        '  (descr "Quectel EC25/EG25-family LTE Cat 4 modem, LCC-144-position/'
        '132-real-pin package (29.0 x 32.0mm body). Real pad geometry sourced '
        'from a real, open-hardware KiCad footprint for the pin/footprint-'
        'compatible Quectel EG25-G sibling module (OLIMEX/KiCAD on GitHub). '
        'Quectel documents EC25/EG25/EC21/EG21 as a mechanically/pin-compatible '
        'family in one combined Hardware Design guide. Independently '
        'cross-checked: the 73-84 gap (12 physically-absent positions) matches '
        'this project\'s own EC25VFA-512-STD pinout exactly. See '
        'docs/EC25_FOOTPRINT_VERIFICATION.md for the full sourcing writeup and '
        'residual assumptions.")\n'
    )
    body.append('  (tags "quectel ec25 eg25 lte modem lcc verified")\n')
    body.append("  (attr smd)\n")
    body.append(f"  (fp_text reference REF** (at 0 {-hh-2.0:.3f}) (layer F.SilkS)\n"
                 "    (effects (font (size 1 1) (thickness 0.15))))\n")
    body.append(f"  (fp_text value {name} (at 0 {hh+2.0:.3f}) (layer F.Fab)\n"
                 "    (effects (font (size 1 1) (thickness 0.15))))\n")
    body.append(fp_rect_outline(hw, hh, "F.Fab", 0.1))
    body.append(fp_rect_outline(hw + 1.0, hh + 1.0, "F.CrtYd", 0.05))
    # pin-1 marker (real position: pin 1 is on the top edge, left side)
    body.append(
        f"  (fp_poly (pts (xy {-hw-1.0:.3f} {-hh+0.5:.3f}) (xy {-hw-0.4:.3f} {-hh+0.5:.3f}) "
        f"(xy {-hw-0.7:.3f} {-hh+1.0:.3f})) (layer F.SilkS) (width 0))\n"
    )

    for num, x, y, rot, w, h, is_real in _EC25_PADS:
        if is_real:
            shape = "rect" if num == 1 else "roundrect"
            line = f"  (pad {num} smd {shape} (at {x} {y} {rot:.0f}) (size {w} {h}) (layers F.Cu F.Paste F.Mask)"
            if shape == "roundrect":
                line += " (roundrect_rratio 0.25))\n"
            else:
                line += ")\n"
            body.append(line)
        else:
            # Documentation-only marker for a physically-absent castellation
            # position -- non-conductive layer only, never F.Cu/Paste/Mask,
            # matching the real part's actual gap exactly.
            body.append(f"  (fp_text user \"NC{num}\" (at {x} {y}) (layer Cmts.User)\n"
                         "    (effects (font (size 0.3 0.3) (thickness 0.05))))\n")

    body.append(")\n")
    return "".join(body)

def sim_holder_footprint():
    """Generic 6-contact push-pull nano-SIM holder footprint.

    NOT tied to a specific verified manufacturer part -- nano-SIM holders
    vary in exact footprint between manufacturers even though the SIM
    card contact standard (ISO/IEC 7816) itself is standardized. Pad
    layout here is a simple, generic 1x6 row matching J11's own generic
    Conn_01x06 schematic symbol; verify against a specific chosen
    manufacturer's footprint before fabrication -- see
    docs/COMMS_MODULE_DECISION.md.
    """
    name = "SIM_NanoSIM_6Pin_generic"
    pitch = 2.0
    pad_w, pad_h = 1.2, 1.6
    row_len = pitch * 5
    hw, hh = row_len / 2 + 2.0, 6.0
    body = [f"(footprint {name} (version 20221018) (generator SKYWARD_gen_footprints.py)\n"]
    body.append("  (layer F.Cu)\n")
    body.append(
        '  (descr "Generic 6-contact nano-SIM push-pull holder footprint -- '
        'NOT tied to a specific verified manufacturer part, exact pad '
        'layout varies between real SIM holder products. Verify/replace '
        'before fabrication. See docs/COMMS_MODULE_DECISION.md.")\n'
    )
    body.append('  (tags "sim nano-sim holder generic UNVERIFIED")\n')
    body.append("  (attr smd)\n")
    body.append(f"  (fp_text reference REF** (at 0 {-hh-1.5:.3f}) (layer F.SilkS)\n"
                 "    (effects (font (size 1 1) (thickness 0.15))))\n")
    body.append(f"  (fp_text value {name} (at 0 {hh+1.5:.3f}) (layer F.Fab)\n"
                 "    (effects (font (size 1 1) (thickness 0.15))))\n")
    body.append(fp_rect_outline(hw, hh, "F.Fab", 0.1))
    body.append(fp_rect_outline(hw + 0.5, hh + 0.5, "F.CrtYd", 0.05))
    for k in range(6):
        x = -row_len / 2 + k * pitch
        body.append(pad(k + 1, x, 0, pad_w, pad_h, shape="rect" if k == 0 else "roundrect"))
    body.append(")\n")
    return "".join(body)


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
    (17, 1.9, 1.2, 0, 0.7, 0.2), (18, 1.875, 0.8, 0, 0.65, 0.2),
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
