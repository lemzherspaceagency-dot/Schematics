#!/usr/bin/env python3
"""
Second-pass silkscreen cleanup, addressing what fix_silkscreen.py's
first pass didn't fully clear (checked against real DRC after that pass
ran):

  1. "CM4" section labels still overlapped the board title text no
     matter where in the narrow J1/J2-top-edge strip they were placed
     (the title spans nearly the whole board width there) -- removed as
     redundant (J1/J2's own reference designators plus the board title
     already identify the connector).
  2. "POWER" label overlapped F1's footprint -- moved further left/up,
     clear of F1's real bounding box (not just its reference text).
  3. U9 and L3 (adjacent, tightly-placed components near y=100mm) still
     had their reference text sitting over copper/near a silkscreen
     line after a small nudge -- moved above/below each component's
     real bounding box instead of just nudging sideways within the same
     cramped strip.

Usage: python3 fix_silkscreen2.py
"""
import pcbnew

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    changed = []

    to_remove = []
    for d in board.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetText() == "CM4":
            to_remove.append(d)
        elif d.GetClass() == "PCB_TEXT" and d.GetText() == "POWER":
            d.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(8.0), pcbnew.FromMM(27.0)))
            changed.append("moved 'POWER' label to (8.0, 27.0)")
    for d in to_remove:
        board.Remove(d)
        changed.append("removed redundant 'CM4' label")

    for fp in board.GetFootprints():
        if fp.GetReference() == "U9":
            txt = fp.Reference()
            txt.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(61.875), pcbnew.FromMM(94.6)))
            changed.append("moved U9 reference text above the component")
        elif fp.GetReference() == "L3":
            txt = fp.Reference()
            txt.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(69.625), pcbnew.FromMM(104.7)))
            changed.append("moved L3 reference text below the component")

    print(f"Applied {len(changed)} fixes:")
    for c in changed:
        print(f"  {c}")
    board.Save(PCB_PATH)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
