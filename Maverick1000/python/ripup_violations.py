#!/usr/bin/env python3
"""
Parses a real DRC report and rips up (deletes) any track or via directly
named in a genuine electrical-safety violation (clearance, hole_clearance,
hole_near_hole, holes_co_located, solder_mask_bridge, items_not_allowed).
Never touches anything for a cosmetic-only category (silk_overlap,
silk_over_copper) -- those are left as-is.

This exists because this project's routers (gen_routes.py,
gen_routes_full.py, gen_routes_maze.py) are three separate pieces of code
with three separate historical bug-fix passes; rather than assume every
one of them is now bug-free for every corner case, this script is the
final, unconditional backstop: real KiCad DRC is the ONLY authority on
whether committed copper is actually safe, and anything it flags as a
real violation gets removed, not argued with or left in place. After
running this, re-fill zones and re-run DRC -- ripped-up nets return to
ratsnest and can be re-attempted by a router (usually at a narrower
width or a different path) or left honestly unrouted.

Usage: python3 ripup_violations.py <drc_report.txt>
"""
import re
import sys

import pcbnew

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"

UNSAFE_CATEGORIES = {
    "clearance", "hole_clearance", "hole_near_hole", "holes_co_located",
    "solder_mask_bridge", "items_not_allowed", "copper_sliver",
}

# Not an electrical-safety category (DRC reports it as a warning, not an
# error) -- but ripping up a violating segment can leave the REST of that
# same multi-segment route as an orphaned, unterminated stub elsewhere.
# Swept in the same pass so no dangling copper is left behind after a
# rip-up, for real fabrication/assembly quality, not because it's unsafe.
DANGLING_CATEGORIES = {"track_dangling", "via_dangling"}


def parse_violations(report_text):
    """Returns a set of (net_name, x_mm, y_mm) identifying each Track/Via
    line mentioned inside an unsafe-category violation block."""
    targets = set()
    blocks = re.split(r"\n(?=\[[a-z_]+\]: )", report_text)
    for block in blocks:
        m = re.match(r"\[([a-z_]+)\]:", block)
        if not m or m.group(1) not in (UNSAFE_CATEGORIES | DANGLING_CATEGORIES):
            continue
        for line in block.splitlines():
            tm = re.search(
                r"@\(([\d.]+) mm, ([\d.]+) mm\): (?:Track|Via) \[([^\]]*)\]",
                line,
            )
            if tm:
                x, y, net = tm.groups()
                targets.add((net, round(float(x), 3), round(float(y), 3)))
    return targets


def main():
    if len(sys.argv) != 2:
        print("usage: ripup_violations.py <drc_report.txt>")
        sys.exit(2)

    targets = parse_violations(open(sys.argv[1]).read())
    print(f"Parsed {len(targets)} distinct (net, position) targets from unsafe-category violations")

    board = pcbnew.LoadBoard(PCB_PATH)
    removed = 0
    for t in list(board.GetTracks()):
        net = t.GetNetname()
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            x, y = round(p.x / 1e6, 3), round(p.y / 1e6, 3)
            if (net, x, y) in targets:
                board.Remove(t)
                removed += 1
                continue
        else:
            s, e = t.GetStart(), t.GetEnd()
            sx, sy = round(s.x / 1e6, 3), round(s.y / 1e6, 3)
            ex, ey = round(e.x / 1e6, 3), round(e.y / 1e6, 3)
            if (net, sx, sy) in targets or (net, ex, ey) in targets:
                board.Remove(t)
                removed += 1

    print(f"Removed {removed} track/via objects.")
    board.Save(PCB_PATH)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
