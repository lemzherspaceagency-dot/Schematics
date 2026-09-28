#!/usr/bin/env python3
"""
For one unrouted gap, tests each candidate "big" net (an already-
successfully-routed net) by literally excluding its copper from the
obstacle model and re-running the SAME real A* search. If excluding net
X actually lets the gap route, X is a REAL, simulation-verified blocker
-- not a bounding-box-overlap guess. Read-only: never writes the board.

Usage: python3 find_real_blocker.py <net_name> <ref_a.pin_a> <ref_b.pin_b> <candidate1> [<candidate2> ...]
"""
import sys, math

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from route_inner_layer import (
    LocalWindow3L, PCB_PATH, GRID_LAYERS, GRID, TRY_WIDTHS,
    _POWER_NETS, _POWER_MIN_WIDTH, _POWER_NECK_WIDTH,
)
from board_rules import ClearanceModel
import pcbnew


def mm(nm):
    return nm / 1e6


def main():
    net_name = sys.argv[1]
    ref_a, pin_a = sys.argv[2].split(".")
    ref_b, pin_b = sys.argv[3].split(".")
    candidates = sys.argv[4:]

    board = pcbnew.LoadBoard(PCB_PATH)
    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p

    pa, pb = find_pad(ref_a, pin_a), find_pad(ref_b, pin_b)
    ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
    bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
    a_layers = [i for i, kl in enumerate(GRID_LAYERS) if pa.IsOnLayer(kl) or pa.HasHole()]
    b_layers = [i for i, kl in enumerate(GRID_LAYERS) if pb.IsOnLayer(kl) or pb.HasHole()]
    dist = math.hypot(bx - ax, by - ay)
    print(f"{net_name}: {ref_a}.{pin_a}-{ref_b}.{pin_b} dist={dist:.1f}mm")

    clearance_model = ClearanceModel(board)
    widths = TRY_WIDTHS
    if net_name in _POWER_NETS:
        full = tuple(w for w in TRY_WIDTHS if w >= _POWER_MIN_WIDTH) or (_POWER_MIN_WIDTH,)
        neck = tuple(w for w in TRY_WIDTHS if w < _POWER_MIN_WIDTH) + (_POWER_NECK_WIDTH,)
        widths = full + neck

    def try_search(exclude):
        win = LocalWindow3L(board, net_name, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by),
                             clearance_model=clearance_model, exclude_nets=frozenset(exclude))
        for w in widths:
            radius = max(0, math.ceil((w / 2) / GRID))
            path = win.astar((ax, ay), a_layers, (bx, by), b_layers, radius)
            if path is not None:
                return w
        return None

    baseline = try_search(set())
    print(f"baseline (no exclusion): {'FOUND width='+str(baseline) if baseline else 'NO PATH'}")
    if baseline:
        print("Already routable -- nothing to test.")
        return

    for cand in candidates:
        w = try_search({cand})
        status = f"UNLOCKS at width={w}" if w else "still NO PATH"
        print(f"  exclude {cand:20s} -> {status}")

    # Also test excluding ALL candidates together, in case it's a
    # combined effect rather than any single net.
    if len(candidates) > 1:
        w = try_search(set(candidates))
        status = f"UNLOCKS at width={w}" if w else "still NO PATH"
        print(f"  exclude ALL {len(candidates)} together -> {status}")


if __name__ == "__main__":
    main()
