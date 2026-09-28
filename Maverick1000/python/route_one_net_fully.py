#!/usr/bin/env python3
"""
Routes ALL remaining gaps for ONE net (loops build_cluster_pairs+astar
until fully connected or a gap fails), in a single LoadBoard/SaveBoard
cycle (Add-only, matches the proven-safe pattern). Exits 1 (no save
change beyond what succeeded) if the net can't be fully reconnected.

Usage: python3 route_one_net_fully.py <net_name>
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


def main():
    net_name = sys.argv[1]
    board = pcbnew.LoadBoard(PCB_PATH)
    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
    clearance_model = ClearanceModel(board)
    net_objs = {n.GetNetname(): n for n in board.GetNetInfo().NetsByNetcode().values()}

    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p

    all_ok = True
    for attempt in range(6):
        pairs = build_cluster_pairs(board, order="nearest")
        gap = next((p for p in pairs if p[0] == net_name), None)
        if gap is None:
            break
        _, ref_a, pin_a, ref_b, pin_b = gap
        pa, pb = find_pad(ref_a, pin_a), find_pad(ref_b, pin_b)
        if pa is None or pb is None:
            all_ok = False
            break
        ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
        bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
        a_layers = [i for i, kl in enumerate(GRID_LAYERS) if pa.IsOnLayer(kl) or pa.HasHole()]
        b_layers = [i for i, kl in enumerate(GRID_LAYERS) if pb.IsOnLayer(kl) or pb.HasHole()]
        if not a_layers or not b_layers:
            all_ok = False
            break
        widths = TRY_WIDTHS
        if net_name in _POWER_NETS:
            full = tuple(w for w in TRY_WIDTHS if w >= _POWER_MIN_WIDTH) or (_POWER_MIN_WIDTH,)
            neck = tuple(w for w in TRY_WIDTHS if w < _POWER_MIN_WIDTH) + (_POWER_NECK_WIDTH,)
            widths = full + neck
        win = LocalWindow3L(board, net_name, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by),
                             clearance_model=clearance_model)
        placed = None
        for w in widths:
            radius = max(0, math.ceil((w / 2) / GRID))
            path = win.astar((ax, ay), a_layers, (bx, by), b_layers, radius)
            if path is not None:
                placed = (simplify(path), w)
                break
        if placed is None:
            print(f"  {net_name}: {ref_a}.{pin_a}-{ref_b}.{pin_b} NO PATH")
            all_ok = False
            break
        path, w = placed
        net_obj = net_objs.get(net_name)
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
        print(f"  {net_name}: {ref_a}.{pin_a}-{ref_b}.{pin_b} OK width={w}")

    pairs = build_cluster_pairs(board, order="nearest")
    still_gap = any(p[0] == net_name for p in pairs)
    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    if still_gap or not all_ok:
        print(f"{net_name}: NOT fully reconnected")
        sys.exit(1)
    print(f"{net_name}: fully reconnected")
    sys.exit(0)


if __name__ == "__main__":
    main()
