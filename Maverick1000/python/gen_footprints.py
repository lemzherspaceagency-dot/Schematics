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


def main():
    import os
    os.makedirs(OUT_DIR, exist_ok=True)

    cm4 = dual_row_connector(
        "Hirose_DF40C-100DS-0.4V", 100, pitch=0.4, row_spacing=3.0,
        pad_w=0.25, pad_h=0.9,
        descr=("Hirose DF40C-100DS-0.4V(51), 100-pos 0.4mm pitch SMD receptacle, "
               "CM4 module connector. APPROXIMATE geometry from published DF40C "
               "series dimensions -- verify against manufacturer drawing before "
               "fabrication (docs/assumptions.md #2)."),
        tags="hirose df40 cm4 raspberry pi high density 0.4mm")
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


if __name__ == "__main__":
    main()
