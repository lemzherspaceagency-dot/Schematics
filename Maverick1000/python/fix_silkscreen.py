#!/usr/bin/env python3
"""
Post-hoc silkscreen cleanup on the live board (gen_pcb.py can't be
re-run at this stage without discarding this session's routing, so this
patches the specific items real DRC flags directly, the same pattern as
fix_df40c_dimensions.py).

Fixes, each tied to a specific real [silk_overlap]/[silk_over_copper]
DRC finding:
  1. J1/J2's manually-added "PIN 1" text labels (from gen_pcb.py)
     duplicate the connector footprints' own embedded pin-1 marker
     polygon (a standard part of the DF40C footprint drawing) and
     overlap both it and a nearby silkscreen line -- removed as pure
     redundancy, not a loss of information (the footprint's own pin-1
     triangle marker remains).
  2. "CM4" labels over J1/J2 -- moved up and shrunk slightly so they
     clear the connectors' own reference-designator text.
  3. L3 and U9 reference designators overlapping a nearby silkscreen
     line / sitting over exposed copper -- nudged to a clear position
     near each component.
  4. "GNSS"/"DOCK" section labels clipped by solder mask (sitting over
     copper with no silkscreen-over-copper allowance) -- moved to bare
     substrate.

Usage: python3 fix_silkscreen.py
"""
import pcbnew

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    changed = []

    # 1. Remove the redundant "PIN 1" text markers (PCB_TEXT, not part of
    # any footprint) duplicating J1/J2's own footprint pin-1 polygon.
    to_remove = []
    for d in board.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetText() == "PIN 1":
            to_remove.append(d)
    for d in to_remove:
        board.Remove(d)
        changed.append(f"removed redundant 'PIN 1' text at "
                        f"({d.GetPosition().x/1e6:.2f}, {d.GetPosition().y/1e6:.2f})")

    # 2. Move "CM4" labels clear of J1/J2 reference text.
    for d in board.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetText() == "CM4":
            p = d.GetPosition()
            d.SetPosition(pcbnew.VECTOR2I(p.x, pcbnew.FromMM(5.5)))
            d.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.9), pcbnew.FromMM(0.9)))
            changed.append(f"moved 'CM4' label to y=5.5mm (x={p.x/1e6:.2f})")

    # 3. Move "GNSS"/"DOCK" labels off copper.
    for d in board.GetDrawings():
        if d.GetClass() != "PCB_TEXT":
            continue
        if d.GetText() == "GNSS":
            d.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(95.0), pcbnew.FromMM(24.0)))
            changed.append("moved 'GNSS' label to (95.0, 24.0)")
        elif d.GetText() == "DOCK":
            d.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(13.0), pcbnew.FromMM(60.0)))
            changed.append("moved 'DOCK' label to (13.0, 60.0)")

    # 4. Nudge L3 / U9 reference text off their own nearby silkscreen line.
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref in ("L3", "U9"):
            txt = fp.Reference()
            p = txt.GetPosition()
            txt.SetPosition(pcbnew.VECTOR2I(p.x + pcbnew.FromMM(1.2), p.y))
            changed.append(f"nudged {ref} reference text +1.2mm in X")

    print(f"Applied {len(changed)} silkscreen fixes:")
    for c in changed:
        print(f"  {c}")
    board.Save(PCB_PATH)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
