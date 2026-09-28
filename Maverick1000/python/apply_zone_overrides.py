#!/usr/bin/env python3
"""
Applies a real, standard PCB technique: solid (not thermal-relief) zone
connection for every GND-net pad, board-wide.

Real KiCad DRC repeatedly found individual small THT/exposed-pad GND
pins' thermal-relief connection to the GND pour had fewer copper spokes
than the zone's 2-spoke minimum -- the default relief geometry doesn't
fit at this board's pad sizes/pitches. Each routing pass that adds new
copper near a GND pad can change which specific pads trip this (new
tracks eat into the available spoke room), so a hand-maintained
per-pad list needs constant, indefinite updating for no real benefit --
solid GND connection board-wide is a standard, real, fabrication-valid
choice for small/dense boards like this one (the only real tradeoff is
slightly harder hand (not reflow) soldering directly on a GND pad,
which is not a design defect), and it removes this category permanently.
Since gen_pcb.py regenerates a bare board from scratch, this script must
be re-run (and zones re-filled) after every gen_pcb.py run, same as
gen_routes.py / gen_routes_full.py.

Usage: python3 apply_zone_overrides.py
"""
import pcbnew

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    changed = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            if pad.GetNetname() == "GND":
                pad.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
                changed.append((ref, pad.GetPadName()))
    print(f"Set solid zone connection on {len(changed)} GND pads")
    board.Save(PCB_PATH)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
