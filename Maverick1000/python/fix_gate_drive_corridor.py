#!/usr/bin/env python3
"""
Targeted blocker experiment #2 (per explicit budget): GATE_DRIVE (a
small 3-pad net, ~113 track/via objects) was confirmed via
blocker_impact_scan.py to unlock BOTH SW1 and TS_BIAS when excluded --
a real, simulation-verified 2-net shared blocker, unlike +3V3 (which
would require destroying board-spanning infrastructure the user
explicitly said to preserve). GATE_DRIVE's small pad count makes a full
rip-and-reroute bounded and safe, unlike +3V3.

Removes ALL of GATE_DRIVE's copper, then routes GATE_DRIVE itself, SW1,
and TS_BIAS fresh. Aborts (no save) if GATE_DRIVE itself can't be fully
reconnected afterward -- that would be a real regression.
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

    removed = [t for t in board.GetTracks() if t.GetNetname() == "GATE_DRIVE"]
    print(f"Removing {len(removed)} GATE_DRIVE track/via objects")
    for t in removed:
        board.Remove(t)
    board.BuildConnectivity()

    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
    clearance_model = ClearanceModel(board)
    net_objs = {n.GetNetname(): n for n in board.GetNetInfo().NetsByNetcode().values()}

    # Route GATE_DRIVE's own gaps first (it may need >1 gap now that
    # it's fully split into per-pad clusters).
    gate_drive_ok = True
    for _ in range(3):  # up to 3 gaps for a 3-pad net
        pairs = build_cluster_pairs(board, order="nearest")
        gap = next((p for p in pairs if p[0] == "GATE_DRIVE"), None)
        if gap is None:
            break
        _, ref_a, pin_a, ref_b, pin_b = gap
        ok = route_gap(board, clearance_model, net_objs, fp_by_ref, "GATE_DRIVE", ref_a, pin_a, ref_b, pin_b)
        if not ok:
            gate_drive_ok = False
            break

    if not gate_drive_ok:
        print("GATE_DRIVE could not be fully reconnected -- aborting, board NOT saved")
        sys.exit(1)

    # Confirm GATE_DRIVE is now a single cluster.
    pairs = build_cluster_pairs(board, order="nearest")
    if any(p[0] == "GATE_DRIVE" for p in pairs):
        print("GATE_DRIVE still has a gap after 3 attempts -- aborting, board NOT saved")
        sys.exit(1)
    print("GATE_DRIVE fully reconnected.")

    # Now route the two unlocked targets.
    for net_name, ref_a, pin_a, ref_b, pin_b in [
        ("SW1", "U3", "28", "L2", "1"),
        ("TS_BIAS", "R18", "1", "U3", "16"),
    ]:
        route_gap(board, clearance_model, net_objs, fp_by_ref, net_name, ref_a, pin_a, ref_b, pin_b)

    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
