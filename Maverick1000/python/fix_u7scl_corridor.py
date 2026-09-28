#!/usr/bin/env python3
"""
Targeted, evidence-verified fix for U7_SCL (confirmed via leave-one-out
simulation + exact-blocker localization, not a heuristic guess): remove
ONE specific +3V3 track segment (61.865,73.0)-(54.115,73.0) on F.Cu,
0.5mm wide -- the exact object whose real clearance halo blocks 11 of
282 cells on U7_SCL's only viable path -- then reroute U7_SCL, then
check whether +3V3 itself needs re-routing to recover full connectivity
(only if removing this segment actually disconnects some of +3V3's
pads; a 0.5mm power trace like this is often one of several redundant
parallel paths on a well-connected net, verified via real connectivity
after, not assumed).
"""
import sys, math

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from route_inner_layer import (
    build_cluster_pairs, LocalWindow3L, PCB_PATH, GRID_LAYERS, GRID,
    TRY_WIDTHS, _POWER_NETS, _POWER_MIN_WIDTH, _POWER_NECK_WIDTH, simplify,
)
from board_rules import ClearanceModel
import pcbnew


def mm(nm):
    return nm / 1e6


def nm_(v):
    return int(round(v * 1e6))


def place_path(board, net_obj, path, w):
    for i in range(len(path) - 1):
        sx, sy, sl = path[i]
        ex, ey, el = path[i + 1]
        if sl != el:
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pcbnew.VECTOR2I(nm_(sx), nm_(sy)))
            via.SetWidth(nm_(0.6))
            via.SetDrill(nm_(0.4))
            via.SetNet(net_obj)
            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            board.Add(via)
            continue
        if abs(sx - ex) < 1e-6 and abs(sy - ey) < 1e-6:
            continue
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I(nm_(sx), nm_(sy)))
        track.SetEnd(pcbnew.VECTOR2I(nm_(ex), nm_(ey)))
        track.SetWidth(nm_(w))
        track.SetLayer(GRID_LAYERS[sl])
        track.SetNet(net_obj)
        board.Add(track)


def main():
    board = pcbnew.LoadBoard(PCB_PATH)

    # Step 1: remove the one identified +3V3 segment.
    target = None
    for t in board.GetTracks():
        if t.GetNetname() != "+3V3" or t.GetClass() == "PCB_VIA":
            continue
        s, e = t.GetStart(), t.GetEnd()
        sx, sy, ex, ey = mm(s.x), mm(s.y), mm(e.x), mm(e.y)
        if t.GetLayer() == pcbnew.F_Cu and (
            (abs(sx - 61.865) < 0.01 and abs(sy - 73.0) < 0.01 and abs(ex - 54.115) < 0.01 and abs(ey - 73.0) < 0.01)
            or (abs(ex - 61.865) < 0.01 and abs(ey - 73.0) < 0.01 and abs(sx - 54.115) < 0.01 and abs(sy - 73.0) < 0.01)
        ):
            target = t
            break
    if target is None:
        print("Target +3V3 segment not found -- board state changed since diagnosis, aborting")
        sys.exit(1)
    board.Remove(target)
    print("Removed the identified +3V3 segment (61.865,73.0)-(54.115,73.0) F.Cu 0.5mm")

    # Step 2: route U7_SCL now that the path is clear.
    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p

    pa, pb = find_pad("R27", "2"), find_pad("U7", "24")
    ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
    bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
    a_layers = [i for i, kl in enumerate(GRID_LAYERS) if pa.IsOnLayer(kl) or pa.HasHole()]
    b_layers = [i for i, kl in enumerate(GRID_LAYERS) if pb.IsOnLayer(kl) or pb.HasHole()]

    clearance_model = ClearanceModel(board)
    win = LocalWindow3L(board, "U7_SCL", min(ax, bx), min(ay, by), max(ax, bx), max(ay, by),
                         clearance_model=clearance_model)
    placed = None
    for w in TRY_WIDTHS:
        radius = max(0, math.ceil((w / 2) / GRID))
        path = win.astar((ax, ay), a_layers, (bx, by), b_layers, radius)
        if path is not None:
            placed = (simplify(path), w)
            break
    if placed is None:
        print("U7_SCL still NO PATH even after removing the identified segment -- aborting, restoring board unchanged")
        sys.exit(1)
    path, w = placed
    net_objs = {n.GetNetname(): n for n in board.GetNetInfo().NetsByNetcode().values()}
    place_path(board, net_objs.get("U7_SCL"), path, w)
    print(f"U7_SCL routed, width={w}")

    # Step 3: check if +3V3 needs a gap filled (removing the segment may
    # have split it into 2 clusters -- only reroute if it actually did).
    pairs = build_cluster_pairs(board, order="nearest")
    v3_gap = None
    for n, ref_a, pin_a, ref_b, pin_b in pairs:
        if n == "+3V3":
            v3_gap = (ref_a, pin_a, ref_b, pin_b)
            break
    if v3_gap is None:
        print("+3V3 still fully connected without that segment (it was redundant/parallel copper) -- nothing more to do")
    else:
        ref_a, pin_a, ref_b, pin_b = v3_gap
        print(f"+3V3 needs reconnecting: {ref_a}.{pin_a}-{ref_b}.{pin_b}")
        pa2, pb2 = find_pad(ref_a, pin_a), find_pad(ref_b, pin_b)
        ax2, ay2 = mm(pa2.GetPosition().x), mm(pa2.GetPosition().y)
        bx2, by2 = mm(pb2.GetPosition().x), mm(pb2.GetPosition().y)
        a_layers2 = [i for i, kl in enumerate(GRID_LAYERS) if pa2.IsOnLayer(kl) or pa2.HasHole()]
        b_layers2 = [i for i, kl in enumerate(GRID_LAYERS) if pb2.IsOnLayer(kl) or pb2.HasHole()]
        widths2 = tuple(w2 for w2 in TRY_WIDTHS if w2 >= _POWER_MIN_WIDTH) or (_POWER_MIN_WIDTH,)
        widths2 = widths2 + (tuple(w2 for w2 in TRY_WIDTHS if w2 < _POWER_MIN_WIDTH) + (_POWER_NECK_WIDTH,))
        win2 = LocalWindow3L(board, "+3V3", min(ax2, bx2), min(ay2, by2), max(ax2, bx2), max(ay2, by2),
                              clearance_model=clearance_model)
        placed2 = None
        for w2 in widths2:
            radius2 = max(0, math.ceil((w2 / 2) / GRID))
            path2 = win2.astar((ax2, ay2), a_layers2, (bx2, by2), b_layers2, radius2)
            if path2 is not None:
                placed2 = (simplify(path2), w2)
                break
        if placed2 is None:
            print("  COULD NOT reconnect +3V3 -- this would be a regression, aborting without saving")
            sys.exit(1)
        path2, w2 = placed2
        place_path(board, net_objs.get("+3V3"), path2, w2)
        print(f"  +3V3 reconnected, width={w2}")

    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
