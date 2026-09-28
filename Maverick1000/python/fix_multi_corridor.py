#!/usr/bin/env python3
"""
Generalized version of fix_gate_drive_corridor.py: removes ALL copper
of a small set of candidate blocker nets, reconnects each of them fully
(aborting without saving if any can't be fully reconnected), then routes
a set of target unlocked nets.
"""
import sys, math

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from route_inner_layer import (
    build_cluster_pairs, LocalWindow3L, PCB_PATH, GRID_LAYERS, GRID,
    TRY_WIDTHS, _POWER_NETS, _POWER_MIN_WIDTH, _POWER_NECK_WIDTH, simplify,
)
from board_rules import ClearanceModel
import pcbnew

CANDIDATES = ["GATE_DRIVE", "ACDRV1_GATE"]
TARGETS = [
    ("SW1", "U3", "28", "L2", "1"),
    ("TS_BIAS", "R18", "1", "U3", "16"),
]


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


def route_gap(board, clearance_model, net_objs, fp_by_ref, net_name, ref_a, pin_a, ref_b, pin_b):
    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p

    pa, pb = find_pad(ref_a, pin_a), find_pad(ref_b, pin_b)
    if pa is None or pb is None:
        return False
    ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
    bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
    a_layers = [i for i, kl in enumerate(GRID_LAYERS) if pa.IsOnLayer(kl) or pa.HasHole()]
    b_layers = [i for i, kl in enumerate(GRID_LAYERS) if pb.IsOnLayer(kl) or pb.HasHole()]
    if not a_layers or not b_layers:
        return False

    widths = TRY_WIDTHS
    if net_name in _POWER_NETS:
        full = tuple(w for w in TRY_WIDTHS if w >= _POWER_MIN_WIDTH) or (_POWER_MIN_WIDTH,)
        neck = tuple(w for w in TRY_WIDTHS if w < _POWER_MIN_WIDTH) + (_POWER_NECK_WIDTH,)
        widths = full + neck

    win = LocalWindow3L(board, net_name, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by),
                         clearance_model=clearance_model)
    for w in widths:
        radius = max(0, math.ceil((w / 2) / GRID))
        path = win.astar((ax, ay), a_layers, (bx, by), b_layers, radius)
        if path is not None:
            place_path(board, net_objs.get(net_name), simplify(path), w)
            print(f"  {net_name}: {ref_a}.{pin_a}-{ref_b}.{pin_b} OK width={w}")
            return True
    print(f"  {net_name}: {ref_a}.{pin_a}-{ref_b}.{pin_b} NO PATH")
    return False


def main():
    board = pcbnew.LoadBoard(PCB_PATH)

    for cand in CANDIDATES:
        removed = [t for t in board.GetTracks() if t.GetNetname() == cand]
        print(f"Removing {len(removed)} {cand} track/via objects")
        for t in removed:
            board.Remove(t)
    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    del board
    # Fresh reload: bulk board.Remove() across multiple nets followed by
    # board.GetFootprints() in the SAME process corrupted pcbnew's SWIG
    # bindings here too (same class of fragility already found and
    # fixed in reroute_around_violation.py -- Remove-only then Save,
    # never continue using the same board object for anything else).
    board = pcbnew.LoadBoard(PCB_PATH)

    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
    clearance_model = ClearanceModel(board)
    net_objs = {n.GetNetname(): n for n in board.GetNetInfo().NetsByNetcode().values()}

    for cand in CANDIDATES:
        ok = True
        for _ in range(4):
            pairs = build_cluster_pairs(board, order="nearest")
            gap = next((p for p in pairs if p[0] == cand), None)
            if gap is None:
                break
            _, ref_a, pin_a, ref_b, pin_b = gap
            if not route_gap(board, clearance_model, net_objs, fp_by_ref, cand, ref_a, pin_a, ref_b, pin_b):
                ok = False
                break
        pairs = build_cluster_pairs(board, order="nearest")
        if not ok or any(p[0] == cand for p in pairs):
            print(f"{cand} could not be fully reconnected -- aborting, board NOT saved")
            sys.exit(1)
        print(f"{cand} fully reconnected.")

    for net_name, ref_a, pin_a, ref_b, pin_b in TARGETS:
        route_gap(board, clearance_model, net_objs, fp_by_ref, net_name, ref_a, pin_a, ref_b, pin_b)

    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
