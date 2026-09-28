#!/usr/bin/env python3
"""
PHASE-per-new-rules: cheap, bounded blocker-impact scan. For a small set
of candidate blocker nets (start with +3V3, evidence already found),
tests EVERY remaining distributed-congestion gap with that net excluded,
using a SINGLE width (cheap: one window build + one search per gap, not
the full width ladder) to see how many gaps it unlocks. Read-only --
never modifies the board.

Usage: python3 blocker_impact_scan.py <candidate_net> [<candidate_net2> ...]
"""
import sys, math, time
from collections import defaultdict

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from design_data import NETS
from board_clusters import get_net_clusters, mm
from route_inner_layer import LocalWindow3L, PCB_PATH, GRID_LAYERS, GRID
from board_rules import ClearanceModel

import pcbnew


def main():
    candidates = sys.argv[1:]
    board = pcbnew.LoadBoard(PCB_PATH)
    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        if fp is None:
            return None
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p

    tracks_by_net = defaultdict(list)
    for t in board.GetTracks():
        tracks_by_net[t.GetNetname()].append(t)

    def nearest_pair(cluster_a, cluster_b):
        best = None
        for ref_a, pin_a, pa in cluster_a:
            ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
            for ref_b, pin_b, pb in cluster_b:
                bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
                d = math.hypot(bx - ax, by - ay)
                if best is None or d < best[0]:
                    best = (d, ref_a, pin_a, ref_b, pin_b)
        return best

    gaps = []
    for net_name, conns in NETS.items():
        if net_name == "GND" or net_name in candidates:
            continue
        real_pads = [(ref, pin, find_pad(ref, pin)) for ref, pin in conns if find_pad(ref, pin)]
        if len(real_pads) < 2:
            continue
        clusters = get_net_clusters(board, net_name, real_pads, tracks_by_net)
        if len(clusters) <= 1:
            continue
        best_edge = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                cand = nearest_pair(clusters[i], clusters[j])
                if best_edge is None or cand[0] < best_edge[0]:
                    best_edge = cand
        if best_edge:
            d, ref_a, pin_a, ref_b, pin_b = best_edge
            gaps.append((net_name, ref_a, pin_a, ref_b, pin_b, d))

    print(f"{len(gaps)} gaps to test x {len(candidates)} candidate(s)\n")

    clearance_model = ClearanceModel(board)
    unlock_count = defaultdict(int)
    unlock_gaps = defaultdict(list)
    t0 = time.time()

    for gi, (net_name, ref_a, pin_a, ref_b, pin_b, dist) in enumerate(gaps):
        pa, pb = find_pad(ref_a, pin_a), find_pad(ref_b, pin_b)
        ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
        bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
        a_layers = [i for i, kl in enumerate(GRID_LAYERS) if pa.IsOnLayer(kl) or pa.HasHole()]
        b_layers = [i for i, kl in enumerate(GRID_LAYERS) if pb.IsOnLayer(kl) or pb.HasHole()]
        if not a_layers or not b_layers:
            continue

        # cheap baseline check at ONE width (0.2mm, a reasonable common
        # denominator) -- skip nets already routable without any
        # exclusion (not a blocker-impact question).
        win_base = LocalWindow3L(board, net_name, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by),
                                  clearance_model=clearance_model)
        radius = max(0, math.ceil((0.2 / 2) / GRID))
        if win_base.astar((ax, ay), a_layers, (bx, by), b_layers, radius) is not None:
            continue  # already fine, not distributed congestion

        for cand in candidates:
            win = LocalWindow3L(board, net_name, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by),
                                 clearance_model=clearance_model, exclude_nets=frozenset({cand}))
            path = win.astar((ax, ay), a_layers, (bx, by), b_layers, radius)
            if path is not None:
                unlock_count[cand] += 1
                unlock_gaps[cand].append(f"{net_name}:{ref_a}.{pin_a}-{ref_b}.{pin_b}")
        if gi % 5 == 0:
            print(f"  ...{gi}/{len(gaps)} gaps tested, {time.time()-t0:.0f}s elapsed", flush=True)

    print(f"\n=== Blocker impact ranking ({time.time()-t0:.0f}s total) ===")
    for cand in candidates:
        print(f"{cand}: unlocks {unlock_count[cand]} gaps")
        for g in unlock_gaps[cand]:
            print(f"    {g}")


if __name__ == "__main__":
    main()
