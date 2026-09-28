#!/usr/bin/env python3
"""
Shared, correct per-net connectivity-cluster computation.

Earlier version of this logic (in diagnose_clusters.py / route_by_clusters.py)
unioned tracks/vias/pads by EXACT point match (1 micron tolerance) --
too strict: real router-placed track endpoints can land tens of microns
off a pad's exact center (still well within the pad's real copper) due
to ordinary floating-point/grid-snap drift across this project's several
different router scripts, causing massive false "still fragmented"
reports (confirmed directly: TP2.1 showed as an isolated singleton
while a real +5V0 track's endpoint sat only 0.028mm from its center --
well inside the pad, but outside a 1-micron point-exact bucket).

Correct definition of "touching", matching real KiCad connectivity:
a track/via touches a pad if its endpoint falls within the pad's real
(rotation-correct) bounding box, not just near its center point.
Track-to-track / via-to-via / via-to-track unions still use point
matching (these come from continuous router paths and should coincide
much more tightly), but with a slightly relaxed 5-micron tolerance
instead of 1, to absorb ordinary float rounding.
"""
from collections import defaultdict

import pcbnew

TRACK_TOL = 5000  # nm, 5 microns -- track/via-to-track/via endpoint matching


def mm(v):
    return v / 1e6


def pt_key(v, tol=TRACK_TOL):
    return (round(v.x / tol), round(v.y / tol))


def pad_contains(pad, point, margin_nm=1000):
    """True if `point` (a VECTOR2I) falls within `pad`'s real (rotation-
    correct) bounding box, expanded by a small margin for float slop."""
    bbox = pad.GetBoundingBox()
    return (bbox.GetLeft() - margin_nm <= point.x <= bbox.GetRight() + margin_nm
            and bbox.GetTop() - margin_nm <= point.y <= bbox.GetBottom() + margin_nm)


def get_net_clusters(board, net_name, real_pads, tracks_by_net=None):
    """real_pads: list of (ref, pin, pad_obj) -- the net's real component
    pads. Returns list of clusters, each a list of (ref, pin, pad_obj).

    tracks_by_net: optional precomputed {netname: [track,...]} to avoid
    rescanning board.GetTracks() for every net when called in a loop.
    """
    if tracks_by_net is None:
        tracks_by_net = defaultdict(list)
        for t in board.GetTracks():
            tracks_by_net[t.GetNetname()].append(t)
    items = tracks_by_net.get(net_name, [])

    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for ref, pin, p in real_pads:
        find(("pad", ref, pin))

    # Track/via <-> track/via unions: point-exact (within TRACK_TOL).
    by_point = defaultdict(list)
    track_endpoints = {}  # idx -> list of VECTOR2I points
    for idx, t in enumerate(items):
        tid = ("trk", idx)
        find(tid)
        if t.GetClass() == "PCB_VIA":
            pts = [t.GetPosition()]
        else:
            pts = [t.GetStart(), t.GetEnd()]
        track_endpoints[idx] = pts
        for pt in pts:
            by_point[pt_key(pt)].append(tid)
    for pt, ids in by_point.items():
        for i in range(1, len(ids)):
            union(ids[0], ids[i])

    # Pad <-> track/via unions: real bounding-box containment.
    for ref, pin, pad in real_pads:
        pad_id = ("pad", ref, pin)
        for idx, t in enumerate(items):
            for pt in track_endpoints[idx]:
                if pad_contains(pad, pt):
                    union(pad_id, ("trk", idx))
                    break

    clusters = defaultdict(list)
    for ref, pin, p in real_pads:
        clusters[find(("pad", ref, pin))].append((ref, pin, p))
    return list(clusters.values())
