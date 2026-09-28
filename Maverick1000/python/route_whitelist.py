#!/usr/bin/env python3
"""
Routes ONLY a pre-vetted whitelist of net names, skipping every other
candidate build_cluster_pairs() would otherwise also try (and waste
20-30s each searching, even though direct diagnosis already showed they
fail: distributed congestion, not a local geometry problem).

The whitelist comes from diagnose_unconnected.py's PATH_EXISTS_NOW
verdicts: gaps where a real, fresh, isolated LocalWindow3L search
against the CURRENT board found a valid path. Some of those nets don't
get captured by a normal full-board pass because an EARLIER net's
newly-placed copper in the SAME pass blocks them before their turn
comes up -- this script sidesteps that by only ever attempting nets
already individually confirmed synthesizable, and re-verifying (not
reusing a stale path) each time since board state shifts as each one
is placed.
"""
import sys
sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from route_inner_layer import (
    build_cluster_pairs, LocalWindow3L, PCB_PATH, GRID_LAYERS, GRID,
    TRY_WIDTHS, _POWER_NETS, _POWER_MIN_WIDTH, _POWER_NECK_WIDTH, simplify,
)
from board_rules import ClearanceModel
import pcbnew
import math
import time

WHITELIST = {
    "+3V3", "BATT_F", "BTST1", "CM4_USB_DP", "I2C0_SDA", "ILIM_SET",
    "Q1_GATE", "REGN", "SW1", "TS_BIAS", "U7_PLLFILT", "U7_SDA",
    "USB2_0_DP",
}


def mm(nm):
    return nm / 1e6


def nm_(v):
    return int(round(v * 1e6))


STUBBORN_FIRST = ("I2C0_SDA", "REGN", "TS_BIAS", "SW1", "ILIM_SET")
# These 5 repeatedly failed with "NO PATH" specifically because earlier
# nets in the SAME pass (Q1_GATE, BATT_F, +3V3, etc., all physically
# near U1/U3/U7 too) place new copper that blocks them before their
# turn comes up -- confirmed by isolated probes against a FRESH board
# finding a valid path for all 5. Giving them first claim on shared
# space fixes the ordering-caused collision directly.


def main(save=True):
    board = pcbnew.LoadBoard(PCB_PATH)
    pairs = build_cluster_pairs(board, order="nearest")
    pairs = [p for p in pairs if p[0] in WHITELIST]
    pairs.sort(key=lambda p: 0 if p[0] in STUBBORN_FIRST else 1)
    print(f"{len(pairs)} whitelisted candidates this pass")

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
        return None

    ok, fail = 0, 0
    t0 = time.time()
    for idx, (net_name, ref_a, pin_a, ref_b, pin_b) in enumerate(pairs):
        print(f"[{idx+1}/{len(pairs)}] {time.time()-t0:.0f}s {net_name}: {ref_a}.{pin_a}-{ref_b}.{pin_b}", flush=True)
        pa, pb = find_pad(ref_a, pin_a), find_pad(ref_b, pin_b)
        if pa is None or pb is None:
            fail += 1
            continue
        a_layers = [i for i, kl in enumerate(GRID_LAYERS) if pa.IsOnLayer(kl) or pa.HasHole()]
        b_layers = [i for i, kl in enumerate(GRID_LAYERS) if pb.IsOnLayer(kl) or pb.HasHole()]
        if not a_layers or not b_layers:
            fail += 1
            continue
        ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
        bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)

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
            fail += 1
            print("  FAIL (was expected to work in isolation -- collision with an earlier net this pass)")
            continue

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
        ok += 1
        print(f"  OK width={w}")

    print(f"Whitelist routed: {ok}  failed: {fail}")
    board.BuildConnectivity()
    if save:
        pcbnew.SaveBoard(PCB_PATH, board)
        print(f"Saved {PCB_PATH}")
    return ok, fail


if __name__ == "__main__":
    main()
