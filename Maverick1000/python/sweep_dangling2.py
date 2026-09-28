#!/usr/bin/env python3
"""
Robust one-shot dangling-copper sweep, replacing the coordinate-matching
approach (ripup_violations.py's DANGLING_CATEGORIES sweep tries to match
DRC report text coordinates back to exact track endpoints -- but KiCad's
DRC reports a track_dangling/via_dangling marker at the position its own
connectivity algorithm picks, which is not always bit-identical to the
track's own GetStart()/GetEnd() value, so text-coordinate matching
silently failed to converge on the last few stubborn cases).

This instead uses the real topology directly: for every same-net cluster
of touching track/via segments (union-find on shared endpoints, exactly
as sweep_dangling.py did), find every "leaf" point in that cluster -- a
point touched by only ONE track/via endpoint within the cluster (i.e. a
true end of the copper, not a mid-route junction). A cluster is genuinely
complete only if EVERY leaf point lands exactly on a real pad of its own
net. If any leaf floats in free space (touches no pad), the entire
cluster never safely terminates and is removed outright -- this is
exactly what "dangling" means, regardless of which specific point DRC's
report text happened to cite.

CAUTION -- found unsafe for a whole-board run in practice this session:
run across the entire board in one pass, it removed roughly half of all
placed copper (1299 items across 32 of 64 clusters), including many
routes real DRC had never flagged as broken. The exact root cause of
the false positives was not isolated under time pressure. Scoped to a
SINGLE net at a time (with the removal list inspected before commit,
one net's worth of clusters is small enough to sanity-check by eye),
the same leaf-based logic worked correctly and was used successfully
later in the session. Do not re-run this whole-board; if reusing the
technique, loop it net-by-net with manual review, as done ad hoc for
U7_RESET_N.

Usage: python3 sweep_dangling2.py
"""
from collections import defaultdict

import pcbnew

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"
TOL = 1000  # nm, ~0.001mm endpoint-matching tolerance


def pt_key(v):
    return (round(v.x / TOL), round(v.y / TOL))


def main():
    board = pcbnew.LoadBoard(PCB_PATH)

    pad_net_points = {}  # (x,y) -> set of net names touching this exact point
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            k = pt_key(pad.GetPosition())
            pad_net_points.setdefault(k, set()).add(pad.GetNetname())

    items = list(board.GetTracks())

    def item_points(t):
        if t.GetClass() == "PCB_VIA":
            return [pt_key(t.GetPosition())]
        return [pt_key(t.GetStart()), pt_key(t.GetEnd())]

    parent = list(range(len(items)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    by_point_net = defaultdict(list)
    for idx, t in enumerate(items):
        net = t.GetNetname()
        for p in item_points(t):
            by_point_net[(p, net)].append(idx)

    for (p, net), idxs in by_point_net.items():
        for i in range(1, len(idxs)):
            union(idxs[0], idxs[i])

    clusters = defaultdict(list)
    for idx in range(len(items)):
        clusters[find(idx)].append(idx)

    # Point-degree within each cluster: how many track/via endpoints in
    # THIS cluster touch this point (a via counts once at its single
    # point; a track counts once at each of its two ends).
    to_remove = []
    kept_clusters = 0
    for root, idxs in clusters.items():
        net = items[idxs[0]].GetNetname()
        degree = defaultdict(int)
        for idx in idxs:
            for p in item_points(items[idx]):
                degree[p] += 1
        leaves = [p for p, d in degree.items() if d == 1]
        broken = any(net not in pad_net_points.get(p, set()) for p in leaves)
        if broken:
            to_remove.extend(idxs)
        else:
            kept_clusters += 1

    print(f"{len(clusters)} clusters total; {kept_clusters} clean; "
          f"{len(clusters) - kept_clusters} dangling clusters ({len(to_remove)} items) removed.")
    for idx in to_remove:
        board.Remove(items[idx])

    board.Save(PCB_PATH)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
