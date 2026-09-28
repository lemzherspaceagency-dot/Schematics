#!/usr/bin/env python3
"""
Corrects J1/J2's (CM4 DF40C-100DS-0.4V(51) connector) pad row-spacing and
pad size on the real board to match the REAL part, now that exact
dimensions have been independently confirmed.

Two unrelated, real, shipped-product KiCad projects -- NabuCasa/yellow
(Home Assistant Yellow) and hatlabs/HALPI2-hardware (a real CM4/CM5
carrier board) -- both ship a from-scratch-authored
Hirose_DF40_DF40C-100DS-0.4V_2x50_P0.40mm footprint whose descr field
cites Hirose's own official 2D-drawing document URL
(https://www.hirose.com/en/product/document?...documentid=0001001229),
and their pad geometry is byte-identical: 0.4mm pitch (already correct
in this project), 3.08mm row-to-row spacing (this project modeled
3.0mm), 0.2mm x 0.7mm pads (this project modeled 0.25mm x 0.9mm,
generously oversized). See docs/DF40C_FOOTPRINT_VERIFICATION.md.

The pitch and pin-numbering scheme (the correctness-critical parts) were
already right. This script fixes the remaining two dimensional
approximations directly on the placed board (rather than requiring a
full gen_pcb.py regeneration, which would discard this session's
routing) -- J1/J2 are both unrotated (0 deg) on this board, so each
pad's new absolute position is simply the footprint's origin +/- the new
row-spacing magnitude, keeping the existing sign convention (which row a
given pin is physically on does not matter electrically -- see
docs/DF40C_FOOTPRINT_VERIFICATION.md; what matters is that it stays
internally consistent, which this preserves).

Usage: python3 fix_df40c_dimensions.py
"""
import pcbnew

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"

NEW_ROW_SPACING_MM = 3.08
NEW_PAD_W_MM = 0.2
NEW_PAD_H_MM = 0.7


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    changed = 0
    for ref in ("J1", "J2"):
        matches = [f for f in board.GetFootprints() if f.GetReference() == ref]
        assert len(matches) == 1, f"expected exactly one {ref}"
        fp = matches[0]
        assert fp.GetOrientationDegrees() == 0.0, f"{ref} is rotated -- this script assumes 0 deg"
        cy = fp.GetPosition().y
        half_row_nm = pcbnew.FromMM(NEW_ROW_SPACING_MM / 2)
        new_w = pcbnew.FromMM(NEW_PAD_W_MM)
        new_h = pcbnew.FromMM(NEW_PAD_H_MM)
        for pad in fp.Pads():
            p = pad.GetPosition()
            sign = -1 if p.y < cy else 1
            new_y = cy + sign * half_row_nm
            pad.SetPosition(pcbnew.VECTOR2I(p.x, new_y))
            pad.SetSize(pcbnew.VECTOR2I(new_w, new_h))
            changed += 1
    print(f"Updated {changed} pads on J1/J2 to real row spacing {NEW_ROW_SPACING_MM}mm, "
          f"pad size {NEW_PAD_W_MM}x{NEW_PAD_H_MM}mm")
    board.Save(PCB_PATH)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
