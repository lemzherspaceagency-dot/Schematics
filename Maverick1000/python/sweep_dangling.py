#!/usr/bin/env python3
"""
One-shot sweep for track/via clusters that don't terminate on a real pad
at at least one end and a real pad OR another live cluster at the other --
i.e. genuinely orphaned copper left over after ripup_violations.py removed
a violating segment out of the middle of a longer route. Unlike
ripup_violations.py (which removes exactly what real DRC names, one
generation of "now-exposed" dangling ends per run, requiring many
iterations for a long chain), this does a full connectivity flood-fill
per net in one pass: any track/via segment whose connected group of
touching segments never reaches a real pad on both a start point and an
end point is removed entirely, in a single run.

Usage: python3 sweep_dangling.py
"""
import pcbnew

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"
TOL = 1000  # nm, ~0.001mm endpoint-matching tolerance


def pt_key(v):
    return (round(v.x / TOL), round(v.y / TOL))


def main():
    board = pcbnew.LoadBoard(PCB_PATH)

    pad_points = set()  # (x,y) of every pad, any net
    pad_net_points = {}  # (x,y) -> net name, for pads only
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            k = pt_key(pad.GetPosition())
            pad_points.add(k)
            pad_net_points[k] = pad.GetNetname()

    items = [t for t in board.GetTracks()]
    # Build adjacency: two items are connected if they share an endpoint
    # (same net, same point, within tolerance).
    endpoints = []  # (item_index, point_key, net)
    for idx, t in enumerate(items):
        net = t.GetNetname()
        if t.GetClass() == "PCB_VIA":
            p = pt_key(t.GetPosition())
            endpoints.append((idx, p, net))
        else:
            endpoints.append((idx, pt_key(t.GetStart()), net))
            endpoints.append((idx, pt_key(t.GetEnd()), net))

    from collections import defaultdict
    by_point = defaultdict(list)
    for idx, p, net in endpoints:
        by_point[(p, net)].append(idx)

    # Union-Find over item indices
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

    for (p, net), idxs in by_point.items():
        for i in range(1, len(idxs)):
            union(idxs[0], idxs[i])

    # For each cluster, does it touch a real pad on the SAME net at at
    # least 2 distinct points (both ends anchored), or 1 point AND
    # connect onward to something else real? Simplify: a cluster is kept
    # only if it touches >=2 distinct real-pad points on its own net (a
    # genuine point-to-point or multi-point connection), OR exactly 1
    # pad point but has >1 items (still mid-route, likely fine -- err on
    # the side of NOT removing ambiguous cases, only remove clusters
    # touching ZERO real pads at all, the unambiguous orphan case).
    clusters = defaultdict(list)
    for idx in range(len(items)):
        clusters[find(idx)].append(idx)

    to_remove = []
    for root, idxs in clusters.items():
        net = items[idxs[0]].GetNetname()
        touches_pad = False
        for idx in idxs:
            t = items[idx]
            pts = [pt_key(t.GetPosition())] if t.GetClass() == "PCB_VIA" else [pt_key(t.GetStart()), pt_key(t.GetEnd())]
            for p in pts:
                if p in pad_points and pad_net_points.get(p) == net:
                    touches_pad = True
                    break
            if touches_pad:
                break
        if not touches_pad:
            to_remove.extend(idxs)

    print(f"Found {len(clusters)} track/via clusters; {len(to_remove)} items in clusters touching zero real pads.")
    for idx in to_remove:
        board.Remove(items[idx])

    board.Save(PCB_PATH)
    print(f"Removed {len(to_remove)} orphaned items. Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
