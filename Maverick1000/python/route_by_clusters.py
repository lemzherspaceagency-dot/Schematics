#!/usr/bin/env python3
"""
Correct successor to route_remaining.py: computes REAL per-net
connectivity clusters directly from the live board (board_clusters.py's
pad-bounding-box-containment method, not fragile exact-point matching --
see that module's docstring for the real bug found and fixed there) and,
for every net with more than one disconnected cluster, finds the true
nearest real-pad-to-real-pad edge between each pair of clusters and
routes exactly that -- always a genuine pad-to-pad request the existing
MazeRouter already handles correctly, never a mid-track point.

Usage: python3 route_by_clusters.py
"""
import math
import sys
from collections import defaultdict

import pcbnew

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from design_data import NETS
from board_clusters import get_net_clusters, mm
from gen_routes_maze import MazeRouter, PCB_PATH, width_for, _POWER_WIDTHS


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


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        if fp is None:
            return None
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p
        return None

    r = MazeRouter(board)

    total_ok, total_fail = 0, 0
    for net_name, conns in NETS.items():
        if net_name == "GND":
            continue
        real_pads = []
        for ref, pin in conns:
            p = find_pad(ref, pin)
            if p is not None:
                real_pads.append((ref, pin, p))
        if len(real_pads) < 2:
            continue

        default_width = width_for(net_name)
        allow_thinning = net_name not in _POWER_WIDTHS

        for _ in range(len(real_pads)):
            tracks_by_net = defaultdict(list)
            for t in board.GetTracks():
                tracks_by_net[t.GetNetname()].append(t)
            clusters = get_net_clusters(board, net_name, real_pads, tracks_by_net)
            if len(clusters) <= 1:
                break

            best_edge = None
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    cand = nearest_pair(clusters[i], clusters[j])
                    if best_edge is None or cand[0] < best_edge[0]:
                        best_edge = cand
            if best_edge is None:
                break
            _, ref_a, pin_a, ref_b, pin_b = best_edge
            label = f"{net_name}: {ref_a}.{pin_a}-{ref_b}.{pin_b} (cluster-merge)"
            ok = r.route(ref_a, pin_a, ref_b, pin_b, default_width, label, allow_thinning=allow_thinning)
            if ok:
                total_ok += 1
                print(f"  OK   {label}", flush=True)
            else:
                total_fail += 1
                print(f"  FAIL {label}", flush=True)
                break

    print(f"\nCluster-merge routing: {total_ok} succeeded, {total_fail} failed")
    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
