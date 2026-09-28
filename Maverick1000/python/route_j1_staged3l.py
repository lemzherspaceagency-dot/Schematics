#!/usr/bin/env python3
"""
Staged J1/J2 escape router, 3-layer remainder (F.Cu/In1.Cu/B.Cu).

Same staging idea as route_j1_staged.py (place the already-proven
straight escape geometry directly, then hand off to a real A* for the
long-distance remainder), but the remainder now runs on
route_inner_layer.py's fixed 3-layer LocalWindow3L instead of the
2-layer MazeRouter. This matters specifically for J1/J2: the earlier
2-layer staged router's remainder search was repeatedly blocked by
corridor-lateral-travel contention (one net's F.Cu/B.Cu path claiming
the whole shared inter-row corridor for a long stretch, per this
session's own diagnosis). A 3-layer remainder can duck onto In1.Cu to
route around that same contention instead of being limited to the two
outer layers everyone else is also fighting over.

Usage: python3 route_j1_staged3l.py [order]
"""
import math
import sys
import time

import pcbnew

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from design_data import NETS
from board_clusters import get_net_clusters, mm
from board_rules import ClearanceModel
from route_inner_layer import LocalWindow3L, GRID, GRID_LAYERS, TRY_WIDTHS, VIA_DIA, VIA_DRILL, simplify

# A real bug this pass found and fixed: a single fixed 1.5mm escape
# depth lands EVERY row-1 pin at the exact same y=12.0 line -- and
# GPIO_GNSS_PPS's own already-routed track (placed earlier this
# session) runs along exactly that line across x=30.8-34.6, so every
# later net whose escape point falls in that span collided with it
# and failed outright (0 free neighbors at the landing cell). Trying
# several depths lets a net step past a specific occupied line instead
# of always aiming at the same one everyone else already used.
ESCAPE_DEPTHS_MM = (1.5, 1.15, 1.85, 0.85, 2.15)
ESCAPE_WIDTH_MM = 0.2
MAX_REMAINDER_MM = 130.0  # tested directly: a 106mm-span 3-layer 0.05mm
# window builds in ~5s and searches in ~10s -- tractable for this
# session's real candidate count (under 20 J1/J2 nets).
ROW1_Y, ROW2_Y = 10.5, 13.5
ROW_TOL = 0.05
PRIORITY_REFS = ("J1", "J2")


def nm(v):
    return int(round(v * 1e6))


def escape_targets(pad_x, pad_y):
    if abs(pad_y - ROW1_Y) < ROW_TOL:
        return [(pad_x, pad_y + d) for d in ESCAPE_DEPTHS_MM]
    if abs(pad_y - ROW2_Y) < ROW_TOL:
        return [(pad_x, pad_y - d) for d in ESCAPE_DEPTHS_MM]
    return []


def main(order="nearest"):
    board = pcbnew.LoadBoard(
        "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb")
    clearance_model = ClearanceModel(board)
    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
    net_objs = {n.GetNetname(): n for n in board.GetNetInfo().NetsByNetcode().values()}

    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        if fp is None:
            return None
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p

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

    rows = []
    for net_name, conns in NETS.items():
        if net_name == "GND":
            continue
        real_pads = [(ref, pin, find_pad(ref, pin)) for ref, pin in conns if find_pad(ref, pin)]
        if len(real_pads) < 2 or not any(ref in PRIORITY_REFS for ref, pin, p in real_pads):
            continue
        tracks_by_net = {}
        for t in board.GetTracks():
            tracks_by_net.setdefault(t.GetNetname(), []).append(t)
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
        d, ref_a, pin_a, ref_b, pin_b = best_edge
        if ref_a not in PRIORITY_REFS and ref_b not in PRIORITY_REFS:
            continue
        rows.append((d, net_name, ref_a, pin_a, ref_b, pin_b))

    if order == "nearest":
        rows.sort(key=lambda r: r[0])
    elif order == "farthest":
        rows.sort(key=lambda r: -r[0])

    print(f"{len(rows)} J1/J2 candidates, order={order}", flush=True)

    ok, fail = 0, 0
    t0 = time.time()
    for idx, (dist, net_name, ref_a, pin_a, ref_b, pin_b) in enumerate(rows):
        if ref_a in PRIORITY_REFS:
            j1_ref, j1_pin, other_ref, other_pin = ref_a, pin_a, ref_b, pin_b
        else:
            j1_ref, j1_pin, other_ref, other_pin = ref_b, pin_b, ref_a, pin_a

        pad_j1 = find_pad(j1_ref, j1_pin)
        pad_other = find_pad(other_ref, other_pin)
        px, py = mm(pad_j1.GetPosition().x), mm(pad_j1.GetPosition().y)
        ox, oy = mm(pad_other.GetPosition().x), mm(pad_other.GetPosition().y)
        label = f"{net_name}: {j1_ref}.{j1_pin}-{other_ref}.{other_pin} dist={dist:.1f}mm"
        print(f"[{idx+1}/{len(rows)}] {time.time()-t0:.0f}s {label}", flush=True)

        targets = escape_targets(px, py)
        if not targets:
            fail += 1
            print("  SKIP (no row1/row2 escape geometry for this pin)", flush=True)
            continue

        other_layers = [i for i, kl in enumerate(GRID_LAYERS)
                         if pad_other.IsOnLayer(kl) or pad_other.HasHole()]
        if not other_layers:
            fail += 1
            print("  FAIL (destination pad has no modeled-layer copper)", flush=True)
            continue
        if max(abs(targets[0][0] - ox), abs(targets[0][1] - oy)) > MAX_REMAINDER_MM:
            fail += 1
            print(f"  SKIP (remainder span > {MAX_REMAINDER_MM}mm, impractical at this grid)", flush=True)
            continue

        placed = None
        track = None
        for tx, ty in targets:
            # Escape leg: exact proven coordinates, no search (same
            # reasoning as route_j1_staged.py). Each candidate depth is
            # tried in turn -- a real bug this pass found: a single
            # fixed depth landed every row-1 pin on the exact same line
            # an earlier-routed net (GPIO_GNSS_PPS) already occupied.
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(nm(px), nm(py)))
            track.SetEnd(pcbnew.VECTOR2I(nm(tx), nm(ty)))
            track.SetWidth(pcbnew.FromMM(ESCAPE_WIDTH_MM))
            track.SetLayer(pcbnew.F_Cu)
            track.SetNet(net_objs[net_name])
            board.Add(track)

            win = LocalWindow3L(board, net_name, min(tx, ox), min(ty, oy), max(tx, ox), max(ty, oy),
                                 clearance_model=clearance_model)
            for w in TRY_WIDTHS:
                radius = max(0, math.ceil((w / 2) / GRID))
                path = win.astar((tx, ty), [0], (ox, oy), other_layers, radius)
                if path is not None:
                    placed = (simplify(path), w)
                    break
            if placed is not None:
                break
            board.Remove(track)
            track = None

        if placed is None:
            fail += 1
            print(f"  FAIL (tried {len(targets)} escape depths, no 3-layer remainder path found for any)", flush=True)
            continue

        path, w = placed
        net_obj = net_objs[net_name]
        for i in range(len(path) - 1):
            sx, sy, sl = path[i]
            ex, ey, el = path[i + 1]
            if sl != el:
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(pcbnew.VECTOR2I(nm(sx), nm(sy)))
                via.SetWidth(pcbnew.FromMM(VIA_DIA))
                via.SetDrill(pcbnew.FromMM(VIA_DRILL))
                via.SetNet(net_obj)
                via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                board.Add(via)
                continue
            if abs(sx - ex) < 1e-6 and abs(sy - ey) < 1e-6:
                continue
            seg = pcbnew.PCB_TRACK(board)
            seg.SetStart(pcbnew.VECTOR2I(nm(sx), nm(sy)))
            seg.SetEnd(pcbnew.VECTOR2I(nm(ex), nm(ey)))
            seg.SetWidth(pcbnew.FromMM(w))
            seg.SetLayer(GRID_LAYERS[sl])
            seg.SetNet(net_obj)
            board.Add(seg)

        ok += 1
        print(f"  OK (escape + 3-layer remainder, {len(path)} cells @ {w}mm)", flush=True)
        if ok % 1 == 0:  # save every success -- each attempt here can take
            # 30-70s (large 3-layer windows), so a run that gets killed by
            # a wall-clock timeout must not lose already-found routes
            board.BuildConnectivity()
            pcbnew.SaveBoard(
                "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb",
                board)
            print(f"  (checkpoint saved, {ok} routed so far)", flush=True)

    print(f"\nStaged 3-layer J1/J2 routing: {ok} succeeded, {fail} failed", flush=True)
    board.BuildConnectivity()
    pcbnew.SaveBoard(
        "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb", board)
    print("Saved.")


if __name__ == "__main__":
    main(order=sys.argv[1] if len(sys.argv) > 1 else "nearest")
