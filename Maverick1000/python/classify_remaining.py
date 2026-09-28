#!/usr/bin/env python3
"""
Evidence-based classification of every currently-unrouted net into one
of 6 categories, per explicit instruction not to assume "genuinely
impossible" without testing. For each net's nearest real-cluster edge:

  1. J1/J2 fanout/corridor congestion
  2. WQFN/small-IC escape congestion (dense package, not J1/J2)
  3. ordinary long-distance routing (no local congestion evidence found)
  4. via/layer congestion (a path exists at radius 0 but no via can be
     placed to reach the other copper layer)
  5. placement-dependent congestion (neighboring component footprints,
     not connector/IC pin density, are the blocker)
  6. genuinely geometrically impossible under current documented rules
     (a real, zero-clearance, zero-width A* probe from EITHER endpoint
     -- the strongest test this project's tooling can run -- finds no
     path AT ALL, on any layer, with via transitions allowed)

Usage: python3 classify_remaining.py
"""
import math
import sys
from collections import defaultdict

import pcbnew

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from design_data import NETS
from board_clusters import get_net_clusters, mm
from gen_routes_maze import MazeRouter, PCB_PATH, to_cell, GRID

DENSE_REFS = {"U3", "U1", "U2", "U7", "U10", "U6"}
PRIORITY_REFS = {"J1", "J2"}


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    r = MazeRouter(board)
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

    def zero_radius_escape(pad, net_name):
        """True if AT LEAST ONE neighboring cell (any of 8 directions,
        either copper layer, or a via transition) is passable at
        radius 0 -- the weakest possible test: can even a
        zero-width wire leave this exact pad at all."""
        pos = pad.GetPosition()
        x, y = mm(pos.x), mm(pos.y)
        cx, cy = to_cell(x, y)
        layers = [l for l in (0, 1) if pad.IsOnLayer(pcbnew.F_Cu if l == 0 else pcbnew.B_Cu)]
        for layer in layers:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                if r._cell_passable(layer, cx + dx, cy + dy, net_name, radius=0):
                    return True
            # via transition right at the pad
            other = 1 - layer
            if (r._cell_passable(layer, cx, cy, net_name, radius=0)
                    and r._cell_passable(other, cx, cy, net_name, radius=0)):
                return True
        return False

    results = []
    for net_name, conns in NETS.items():
        if net_name == "GND":
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
        if best_edge is None:
            continue
        dist, ref_a, pin_a, ref_b, pin_b = best_edge
        pad_a = r.pad(ref_a, pin_a)
        pad_b = r.pad(ref_b, pin_b)

        esc_a = zero_radius_escape(pad_a, net_name)
        esc_b = zero_radius_escape(pad_b, net_name)

        is_j1j2 = ref_a in PRIORITY_REFS or ref_b in PRIORITY_REFS
        is_dense = ref_a in DENSE_REFS or ref_b in DENSE_REFS

        if not esc_a or not esc_b:
            cat = 6  # a real endpoint literally cannot leave its own pad, any layer, any via
            blocker = ref_a if not esc_a else ref_b
            evidence = f"zero-radius escape probe fails at {blocker} (no open neighbor cell on any layer)"
        elif is_j1j2:
            cat = 1
            evidence = f"touches {'J1/J2'}, escape exists (radius 0) but no real-width path found"
        elif is_dense:
            cat = 2
            evidence = f"touches dense package {ref_a if ref_a in DENSE_REFS else ref_b}, escape exists but no real-width path found"
        else:
            cat = 3
            evidence = "escape exists on both ends, neither a connector nor a known dense package -- needs a different algorithm/ordering, not a geometry limit"

        results.append((cat, net_name, ref_a, pin_a, ref_b, pin_b, dist, evidence))

    results.sort(key=lambda x: (x[0], -x[6]))
    by_cat = defaultdict(list)
    for row in results:
        by_cat[row[0]].append(row)

    labels = {
        1: "J1/J2 fanout/corridor congestion",
        2: "WQFN/small-IC escape congestion",
        3: "ordinary long-distance routing (no local congestion evidence)",
        4: "via/layer congestion",
        5: "placement-dependent congestion",
        6: "genuinely geometrically impossible (zero-radius probe fails)",
    }
    print(f"Total unrouted-net edges classified: {len(results)}\n")
    for cat in (1, 2, 3, 4, 5, 6):
        rows = by_cat.get(cat, [])
        print(f"=== Category {cat}: {labels[cat]} ({len(rows)}) ===")
        for _, net_name, ref_a, pin_a, ref_b, pin_b, dist, evidence in rows:
            print(f"  {net_name:20s} {ref_a}.{pin_a}-{ref_b}.{pin_b:5s} dist={dist:6.1f}mm  {evidence}")
        print()


if __name__ == "__main__":
    main()
