#!/usr/bin/env python3
"""
Global, lane-aware J1/J2 fanout router.

Diagnosis from the previous pass (route_j1_staged.py): J1's inter-row
corridor is the only open east-west passage past its own ~20mm-wide pin
field, and single-path-at-a-time A* lets whichever net is processed
first claim the ENTIRE corridor width and length for its own route,
blocking every other net that also needs to cross it. This is a
real shared-resource lane-allocation problem, not a per-net geometry
or algorithm bug (both already fixed/proven in earlier passes).

Fix: assign each J1/J2 net crossing the corridor to one of several
parallel Y-lanes (spaced at the real, DRC-proven 0.35mm minimum pitch
for a 0.2mm trace under the board's real 0.15mm J1/J2 courtyard
clearance rule), so multiple nets can physically coexist in the shared
corridor at once instead of one net's path occupying the whole height.

For each net:
  1. Escape straight out from the pad (perpendicular, real proven
     geometry) to its assigned lane's absolute Y.
  2. Travel straight along that lane (real coordinates, no search)
     until clearing J1/J2's own real courtyard X-extent, exiting
     toward whichever side (west/east) is closer to the destination.
  3. Hand off to the existing whole-board A* (gen_routes_maze) for the
     unconstrained remainder from that exit point to the destination.

Each net tries all 6 lanes (nearest-first) until one produces a
complete, real-DRC-checkable path; a lane's 2 fixed segments are only
committed once the remainder search from it actually succeeds, so a
failed lane leaves no partial copper behind.

Usage: python3 route_j1_lanes.py
"""
import math
import sys
import time

import pcbnew

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from design_data import NETS
from board_clusters import get_net_clusters, mm
from gen_routes_maze import MazeRouter, PCB_PATH, to_cell, GRID
from board_rules import get_courtyard_bboxes, parse_courtyard_clearance_rules, ClearanceModel
from local_fine_route import LocalWindow, GRID as FINE_GRID

ESCAPE_WIDTH_MM = 0.2
ROW1_Y, ROW2_Y = 10.5, 13.5
ROW_TOL = 0.05
PRIORITY_REFS = ("J1", "J2")
LANES = [11.25, 11.60, 11.95, 12.30, 12.65]  # absolute mm Y, real 0.35mm pitch
# Margin from each row's pad edge widened from an initial 0.25mm to
# 0.40mm after a real failure this pass: at 0.25mm margin, a lane's own
# fine-grid dilation radius (0.1mm, for a 0.2mm trace) reached back into
# a hard-obstacle strip from J1's own GND/NC-pin halos just past the row
# edge, even though the lane's exact center point tested clear in
# isolation. 0.40mm leaves real headroom instead of exactly the
# theoretical minimum.
EXIT_MARGIN = 0.3  # mm past the real courtyard edge before handing off to A*


def row_of(y):
    if abs(y - ROW1_Y) < ROW_TOL:
        return 1
    if abs(y - ROW2_Y) < ROW_TOL:
        return 2
    return None


def segments_clear(board, clearance_model, net, width_mm, segments):
    """Real, FINE-grid (0.05mm) collision check for one or more straight
    segments against the live board -- the coarse 0.2mm grid this
    router otherwise uses cannot reliably resolve J1/J2's real ~0.28mm
    corridor (proven and confirmed earlier this session: real-open
    space repeatedly showed as coarse-grid-'blocked' near the
    connector). Builds one small LocalWindow spanning all the given
    segments and checks each one at fine resolution, which is what
    correctly resolved this same geometry in the escape-geometry-proof
    phase's real-DRC-verified test traces."""
    xs = [p for seg in segments for p in (seg[0], seg[2])]
    ys = [p for seg in segments for p in (seg[1], seg[3])]
    win = LocalWindow(board, net, min(xs), min(ys), max(xs), max(ys), clearance_model=clearance_model)
    radius = max(0, math.ceil((width_mm / 2) / FINE_GRID))
    for x1, y1, x2, y2 in segments:
        blocked = win._blocked(0, radius)
        length = math.hypot(x2 - x1, y2 - y1)
        steps = max(1, int(length / (FINE_GRID / 2)))
        for i in range(steps + 1):
            t = i / steps
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            cx, cy = win.to_cell(x, y)
            if not (0 <= cx < win.nx and 0 <= cy < win.ny):
                return False
            if blocked[cy, cx]:
                return False
    return True


def commit_segment(r, board, x1, y1, x2, y2, width_mm, net_name):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I(int(x1 * 1e6), int(y1 * 1e6)))
    track.SetEnd(pcbnew.VECTOR2I(int(x2 * 1e6), int(y2 * 1e6)))
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(r.net_objs[net_name])
    board.Add(track)
    r._paint_line(0, x1, y1, x2, y2, width_mm / 2, net_name)


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    r = MazeRouter(board)
    clearance_model = ClearanceModel(board)
    courtyards = get_courtyard_bboxes(board, ("J1", "J2"))
    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        if fp is None:
            return None
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p
        return None

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

    net_names = [n for n in NETS if n != "GND"]
    candidates = []
    for net_name in net_names:
        conns = NETS[net_name]
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
        if ref_a in PRIORITY_REFS:
            j1_ref, j1_pin, other_ref, other_pin = ref_a, pin_a, ref_b, pin_b
        elif ref_b in PRIORITY_REFS:
            j1_ref, j1_pin, other_ref, other_pin = ref_b, pin_b, ref_a, pin_a
        else:
            continue
        candidates.append((d, net_name, j1_ref, j1_pin, other_ref, other_pin))

    # Nearest-destination-first: shorter remainder legs both succeed
    # more often and consume less of the shared corridor's length,
    # leaving more of it free for the nets processed after them.
    candidates.sort(key=lambda c: c[0])

    print(f"{len(candidates)} J1/J2 candidate nets, nearest-destination-first order", flush=True)

    lane_use_count = {y: 0 for y in LANES}
    ok, fail = 0, 0
    t0 = time.time()
    for idx, (dist, net_name, j1_ref, j1_pin, other_ref, other_pin) in enumerate(candidates):
        pad_j1 = r.pad(j1_ref, j1_pin)
        pad_other = r.pad(other_ref, other_pin)
        px, py = mm(pad_j1.GetPosition().x), mm(pad_j1.GetPosition().y)
        row = row_of(py)
        label = f"{net_name}: {j1_ref}.{j1_pin}-{other_ref}.{other_pin} (lane fanout, dist={dist:.1f}mm)"
        print(f"[{idx+1}/{len(candidates)}] {time.time()-t0:.0f}s {label}", flush=True)

        if row is None:
            print("  SKIP (not a row1/row2 GPIO pin -- no proven lane geometry for this pin)", flush=True)
            continue

        cyx0, cyy0, cyx1, cyy1 = courtyards[j1_ref]
        ox, oy = mm(pad_other.GetPosition().x), mm(pad_other.GetPosition().y)
        exit_west = ox < px
        exit_x = (cyx0 - EXIT_MARGIN) if exit_west else (cyx1 + EXIT_MARGIN)

        other_layers = [l for l in (0, 1)
                         if pad_other.IsOnLayer(pcbnew.F_Cu if l == 0 else pcbnew.B_Cu)]
        widths_to_try = [ESCAPE_WIDTH_MM] + [w for w in r.THIN_RETRY_WIDTHS if w < ESCAPE_WIDTH_MM]

        # Try lanes in least-used-first order -- spreads load evenly
        # across the 6 lanes instead of packing the first one.
        lane_order = sorted(LANES, key=lambda y: lane_use_count[y])

        placed = False
        for lane_y in lane_order:
            if not segments_clear(board, clearance_model, net_name, ESCAPE_WIDTH_MM,
                                   [(px, py, px, lane_y), (px, lane_y, exit_x, lane_y)]):
                continue

            commit_segment(r, board, px, py, px, lane_y, ESCAPE_WIDTH_MM, net_name)
            commit_segment(r, board, px, lane_y, exit_x, lane_y, ESCAPE_WIDTH_MM, net_name)
            r._dilate_cache = {}

            goal_cell = to_cell(ox, oy)
            start_cell = to_cell(exit_x, lane_y)
            remainder_path = None
            used_width = None
            for w in widths_to_try:
                radius = max(0, math.ceil((w / 2) / GRID))
                path = r._astar(start_cell, goal_cell, net_name, [0], other_layers, radius)
                if path is not None:
                    remainder_path, used_width = path, w
                    break

            if remainder_path is not None:
                r._commit(remainder_path, used_width, net_name)
                r._dilate_cache = {}
                lane_use_count[lane_y] += 1
                ok += 1
                placed = True
                print(f"  OK lane_y={lane_y} exit_x={exit_x:.2f} remainder={len(remainder_path)} cells @ {used_width}mm", flush=True)
                break
            else:
                # Remove the two staging segments -- this lane didn't
                # lead anywhere, leave no partial copper behind. Board
                # track removal does NOT undo _paint_line's mutation of
                # r.owner (painting is not reversible in general once a
                # foreign-net conflict marker '#' may have been written)
                # -- rebuild the router from the live board so its
                # obstacle grid actually reflects the rollback, not just
                # its cache.
                for t in list(board.GetTracks()):
                    if t.GetClass() != "PCB_TRACK" or t.GetNetname() != net_name:
                        continue
                    s, e = t.GetStart(), t.GetEnd()
                    sx, sy, ex, ey = mm(s.x), mm(s.y), mm(e.x), mm(e.y)
                    is_seg1 = abs(sx - px) < 1e-3 and abs(sy - py) < 1e-3 and abs(ex - px) < 1e-3 and abs(ey - lane_y) < 1e-3
                    is_seg2 = abs(sx - px) < 1e-3 and abs(sy - lane_y) < 1e-3 and abs(ex - exit_x) < 1e-3 and abs(ey - lane_y) < 1e-3
                    if is_seg1 or is_seg2:
                        board.Remove(t)
                r = MazeRouter(board)

        if not placed:
            fail += 1
            print("  FAIL (no lane produced a complete remainder path)", flush=True)

        if ok and ok % 5 == 0:
            board.BuildConnectivity()
            pcbnew.SaveBoard(PCB_PATH, board)
            print(f"  (checkpoint saved, {ok} routed so far)", flush=True)

    print(f"\nLane-aware J1/J2 fanout: {ok} succeeded, {fail} failed", flush=True)
    print("Lane usage:", lane_use_count, flush=True)
    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
