#!/usr/bin/env python3
"""
Real per-net connectivity cluster analysis using the corrected
board_clusters.get_net_clusters() (pad-bounding-box containment, not
fragile exact-point matching -- see board_clusters.py's docstring for
why the original point-exact version drastically over-reported
fragmentation).

Usage: python3 diagnose_clusters.py
"""
import sys
from collections import defaultdict

import pcbnew

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from design_data import NETS
from board_clusters import get_net_clusters

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"


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

    tracks_by_net = defaultdict(list)
    for t in board.GetTracks():
        tracks_by_net[t.GetNetname()].append(t)

    fragmented = []
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

        clusters = get_net_clusters(board, net_name, real_pads, tracks_by_net)
        if len(clusters) > 1:
            fragmented.append((net_name, clusters))

    print(f"Nets with real pad-connectivity fragmentation (>1 disconnected cluster): {len(fragmented)}\n")
    total_extra_edges_needed = 0
    for net_name, clusters in sorted(fragmented, key=lambda x: -len(x[1])):
        n = len(clusters)
        total_extra_edges_needed += n - 1
        print(f"{net_name}: {n} disconnected clusters")
        for cluster in clusters:
            pads = [f"{ref}.{pin}" for ref, pin, _ in cluster]
            print(f"    [{', '.join(pads)}]")
    print(f"\nTotal nets fragmented: {len(fragmented)}")
    print(f"Minimum additional connections needed (clusters-1 per net, summed): {total_extra_edges_needed}")


if __name__ == "__main__":
    main()
