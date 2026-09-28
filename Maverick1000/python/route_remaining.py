#!/usr/bin/env python3
"""
Routes exactly the pad-pairs real DRC currently reports as
[unconnected_items] (parsed straight from a DRC report -- not a recomputed
MST over every net), using the same MazeRouter engine as
gen_routes_maze.py. Re-running gen_routes_maze.py's own main() would
recompute a fresh net-wide MST and re-attempt EVERY edge of every net,
including edges that are already real copper from earlier passes --
wasteful and a real risk of redundant/overlapping copper. This script
instead targets only the specific ref.pin <-> ref.pin pairs DRC says are
still missing a connection, so each run makes forward progress without
re-touching already-good routes.

Usage: python3 route_remaining.py [drc_report.txt]
"""
import re
import sys

import pcbnew

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from gen_routes_maze import MazeRouter, PCB_PATH, width_for, _POWER_WIDTHS

REPORT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/Schematics/Maverick1000/verification/drc_report.txt"


def parse_unconnected(text):
    pairs = []
    blocks = re.split(r"\n(?=\[[a-z_]+\]: )", text)
    for block in blocks:
        if not block.startswith("[unconnected_items]"):
            continue
        m = re.findall(r"Pad (\S+) \[([^\]]*)\] of (\S+) on", block)
        if len(m) == 2:
            (pin_a, net_a, ref_a), (pin_b, net_b, ref_b) = m
            pairs.append((net_a, ref_a, pin_a, ref_b, pin_b))
    return pairs


def main():
    pairs = parse_unconnected(open(REPORT).read())
    print(f"Parsed {len(pairs)} unconnected pad-pairs from {REPORT}")

    board = pcbnew.LoadBoard(PCB_PATH)
    r = MazeRouter(board)

    ok, fail = 0, 0
    for net_name, ref_a, pin_a, ref_b, pin_b in pairs:
        width = width_for(net_name)
        allow_thinning = net_name not in _POWER_WIDTHS
        label = f"{net_name}: {ref_a}.{pin_a}-{ref_b}.{pin_b}"
        try:
            if r.route(ref_a, pin_a, ref_b, pin_b, width, label, allow_thinning=allow_thinning):
                ok += 1
            else:
                fail += 1
        except KeyError as e:
            print(f"  SKIP {label}: {e}")
            fail += 1

    print(f"\nRouted OK: {ok}   Failed: {fail}")
    print("\nFailed edges:")
    for label, status, info in r.results:
        if status == "FAIL":
            print(f"  FAIL: {label} ({info})")

    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    print(f"\nSaved {PCB_PATH}")


if __name__ == "__main__":
    main()
