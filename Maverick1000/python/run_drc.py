#!/usr/bin/env python3
"""
Runs KiCad's real DRC engine (via pcbnew.WriteDRCReport -- this KiCad
7.0.11 build has no `kicad-cli pcb drc` subcommand) against the current
board and writes a full report plus a categorized summary. Kept as a
real, re-runnable script (not a one-off shell command) so results are
reproducible -- see docs/ERC_STATUS.md for why this method is trusted to
be real DRC and not a stub.

Usage: python3 run_drc.py [output_report_path]
"""
import os
import re
import sys

# KiCad's global fp-lib-table / sym-lib-table use ${KICAD7_FOOTPRINT_DIR} /
# ${KICAD7_SYMBOL_DIR} placeholders that a normal desktop KiCad install sets
# automatically. A bare Python script does not get them, which made every
# stock-library footprint report as "not found in library" during DRC --
# 109 false-positive [lib_footprint_issues] warnings, confirmed spurious by
# setting these two variables and re-running (the warning count dropped to
# 0 with an otherwise identical board). Set them here so this script's
# results reflect only real defects.
os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
os.environ.setdefault("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")

import pcbnew

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "/home/user/Schematics/Maverick1000/verification/drc_report.txt"
    board = pcbnew.LoadBoard(PCB_PATH)
    ok = pcbnew.WriteDRCReport(board, out_path, pcbnew.EDA_UNITS_MILLIMETRES, True)
    print(f"WriteDRCReport returned: {ok}")

    text = open(out_path).read()
    for line in re.findall(r"^\*\*.*\*\*$", text, re.M):
        print(line)

    cats = re.findall(r"^\[([a-z_]+)\]: ", text, re.M)
    from collections import Counter

    print("\nCategory breakdown:")
    for cat, count in sorted(Counter(cats).items(), key=lambda kv: -kv[1]):
        print(f"  {count:4d}  {cat}")

    # Independent cross-check: how many [clearance] blocks are track-vs-track
    # (the specific failure mode this project's router had a real bug in,
    # earlier this project) vs pad-vs-pad (a placement issue).
    blocks = re.findall(r"\[clearance\]:.*?\n(?:.*?\n){1,4}?(?=\[|\*\*)", text, re.S)
    kinds = Counter()
    for b in blocks:
        items = tuple(sorted(re.findall(r": (Pad|Track|Zone|Via)\b", b)))
        kinds[items] += 1
    print("\n[clearance] sub-breakdown (item types involved):")
    for k, v in kinds.items():
        print(f"  {v:4d}  {k}")


if __name__ == "__main__":
    main()
