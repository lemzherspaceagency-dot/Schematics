#!/usr/bin/env python3
"""
PHASE 1 congestion analysis. Read-only -- routes nothing.

For every remaining unrouted gap (net + endpoint pair, via the same
real-connectivity MST logic diagnose_unconnected.py uses):
  - endpoint refs, pins, coordinates, accessible layers
  - the physical bounding corridor between the two endpoints (with the
    same span-scaled margin LocalWindow3L itself uses, so "in the
    corridor" matches what the router's own search window would cover)
  - every OTHER net's track/via objects whose geometry falls inside
    that corridor, on any layer

Then aggregates: for each blocking net (and each component reference
that owns pads/tracks inside these corridors), how many DISTINCT
unrouted gaps' corridors it appears in. This is the "which existing
copper is shared infrastructure across the most blocked nets" ranking
Phase 1 asks for -- the basis for picking a single highest-impact
corridor to rip up and jointly reroute, instead of one net at a time.
"""
import sys, math
from collections import defaultdict, Counter

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from design_data import NETS
from board_clusters import get_net_clusters, mm
from route_inner_layer import PCB_PATH, GRID_LAYERS

import pcbnew


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

    tracks_by_net = defaultdict(list)
    all_tracks = []
    for t in board.GetTracks():
        tracks_by_net[t.GetNetname()].append(t)
        all_tracks.append(t)

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

    def mst_gaps(clusters):
        n = len(clusters)
        in_tree = [False] * n
        in_tree[0] = True
        gaps = []
        for _ in range(n - 1):
            best = None
            for i in range(n):
                if not in_tree[i]:
                    continue
                for j in range(n):
                    if in_tree[j]:
                        continue
                    cand = nearest_pair(clusters[i], clusters[j])
                    if best is None or cand[0] < best[0]:
                        best = (cand[0], i, j, cand[1], cand[2], cand[3], cand[4])
            _, i, j, ref_a, pin_a, ref_b, pin_b = best
            in_tree[j] = True
            gaps.append((ref_a, pin_a, ref_b, pin_b))
        return gaps

    gaps = []
    for net_name, conns in NETS.items():
        if net_name == "GND":
            continue
        real_pads = [(ref, pin, find_pad(ref, pin)) for ref, pin in conns if find_pad(ref, pin)]
        if len(real_pads) < 2:
            continue
        clusters = get_net_clusters(board, net_name, real_pads, tracks_by_net)
        if len(clusters) <= 1:
            continue
        for ref_a, pin_a, ref_b, pin_b in mst_gaps(clusters):
            gaps.append((net_name, ref_a, pin_a, ref_b, pin_b))

    print(f"{len(gaps)} remaining gaps to analyze\n")

    blocker_net_count = Counter()
    blocker_net_gaps = defaultdict(set)
    blocker_ref_count = Counter()
    blocker_ref_gaps = defaultdict(set)
    corridor_report = []

    for gi, (net_name, ref_a, pin_a, ref_b, pin_b) in enumerate(gaps):
        pa, pb = find_pad(ref_a, pin_a), find_pad(ref_b, pin_b)
        ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
        bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
        dist = math.hypot(bx - ax, by - ay)
        margin = max(10.0, min(25.0, 0.5 * max(abs(bx - ax), abs(by - ay))))
        x0, y0 = min(ax, bx) - margin, min(ay, by) - margin
        x1, y1 = max(ax, bx) + margin, max(ay, by) + margin

        gap_key = f"{net_name}:{ref_a}.{pin_a}-{ref_b}.{pin_b}"
        blockers_here = set()
        blocker_refs_here = set()
        for t in all_tracks:
            if t.GetNetname() == net_name:
                continue
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                tx0 = ty0 = tx1 = ty1 = None
                px, py = mm(p.x), mm(p.y)
                if not (x0 <= px <= x1 and y0 <= py <= y1):
                    continue
            else:
                s, e = t.GetStart(), t.GetEnd()
                sx, sy, ex, ey = mm(s.x), mm(s.y), mm(e.x), mm(e.y)
                seg_x0, seg_x1 = min(sx, ex), max(sx, ex)
                seg_y0, seg_y1 = min(sy, ey), max(sy, ey)
                if seg_x1 < x0 or seg_x0 > x1 or seg_y1 < y0 or seg_y0 > y1:
                    continue
            blockers_here.add(t.GetNetname())

        # Also count which component references OWN pads inside the
        # corridor (dense packages sitting directly in the path, not
        # just their tracks).
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            if ref in (ref_a, ref_b):
                continue
            for p in fp.Pads():
                pp = p.GetPosition()
                px, py = mm(pp.x), mm(pp.y)
                if x0 <= px <= x1 and y0 <= py <= y1:
                    blocker_refs_here.add(ref)
                    break

        for bn in blockers_here:
            blocker_net_count[bn] += 1
            blocker_net_gaps[bn].add(gap_key)
        for br in blocker_refs_here:
            blocker_ref_count[br] += 1
            blocker_ref_gaps[br].add(gap_key)

        corridor_report.append((gap_key, dist, len(blockers_here), len(blocker_refs_here)))

    print("=== Per-gap corridor summary ===")
    for gap_key, dist, nblockers, nrefs in sorted(corridor_report, key=lambda r: -r[1]):
        print(f"  {gap_key:45s} dist={dist:6.1f}mm  blocking_nets={nblockers:3d}  components_in_corridor={nrefs:3d}")

    print("\n=== Top blocking NETS (existing routed copper occupying the most distinct unrouted-gap corridors) ===")
    for net_name, count in blocker_net_count.most_common(25):
        print(f"  {net_name:25s} blocks {count:2d} distinct gaps")

    print("\n=== Top blocking COMPONENTS (footprints whose pads sit inside the most distinct unrouted-gap corridors) ===")
    for ref, count in blocker_ref_count.most_common(25):
        print(f"  {ref:10s} inside {count:2d} distinct gap corridors")


if __name__ == "__main__":
    main()
