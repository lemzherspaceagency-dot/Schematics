#!/usr/bin/env python3
"""
Staged J1/J2 escape router: combines the two specialized routers this
project already has, each used for what it's actually good at.

Direct diagnosis (this pass): neither existing router alone can close a
J1 net end-to-end.
  - local_fine_route.py's 0.05mm grid resolves J1's real ~0.28-0.3mm
    escape corridor correctly (proven earlier this session with real,
    DRC-verified test traces), but J1's actual destinations (J5-J9, R6,
    U8, ...) sit 30-70mm away -- far more cells than its A* expansion
    budget can explore at that resolution before giving up.
  - gen_routes_maze.py's 0.2mm grid handles that long distance fine
    (it's this project's proven whole-board router), but 0.2mm cells
    are too coarse to reliably resolve a ~0.28mm-wide corridor even
    with the correct clearance value now wired in.

Fix: use the ALREADY-PROVEN straight escape geometry directly (no
search needed -- it's the same fixed, real-DRC-verified pattern for
every row-1/row-2 J1 pin: 1.5mm straight out on F.Cu, perpendicular to
the row) to get each net the short distance from its pad into the open
inter-row corridor, then hand off to gen_routes_maze.MazeRouter's
existing, working long-distance A* for the rest of the path. Both
halves go through the SAME live obstacle-grid/clearance-model MazeRouter
instance, so the coarse router sees the escape trace as a real obstacle
and the whole thing is still checked by real KiCad DRC afterward, same
as every other router in this project.

Usage: python3 route_j1_staged.py
"""
import sys

import pcbnew

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from design_data import NETS
from board_clusters import get_net_clusters, mm
from gen_routes_maze import MazeRouter, PCB_PATH, to_cell, width_for, GRID

ESCAPE_LEN_MM = 1.5  # matches the real-DRC-verified proof traces
ESCAPE_WIDTH_MM = 0.2
ROW1_Y, ROW2_Y = 10.5, 13.5
ROW_TOL = 0.05
PRIORITY_REFS = ("J1", "J2")


def escape_target(pad_x, pad_y):
    if abs(pad_y - ROW1_Y) < ROW_TOL:
        return pad_x, pad_y + ESCAPE_LEN_MM  # south
    if abs(pad_y - ROW2_Y) < ROW_TOL:
        return pad_x, pad_y - ESCAPE_LEN_MM  # north
    return None


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        if fp is None:
            return None
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p
        return None

    r = MazeRouter(board)

    def nearest_pair(cluster_a, cluster_b):
        best = None
        for ref_a, pin_a, pa in cluster_a:
            ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
            for ref_b, pin_b, pb in cluster_b:
                bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
                d = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
                if best is None or d < best[0]:
                    best = (d, ref_a, pin_a, ref_b, pin_b)
        return best

    ok, fail = 0, 0
    import time
    t0 = time.time()
    net_names = [n for n in NETS if n != "GND"]
    for idx, net_name in enumerate(net_names):
        conns = NETS[net_name]
        real_pads = [(ref, pin, find_pad(ref, pin)) for ref, pin in conns if find_pad(ref, pin)]
        if len(real_pads) < 2:
            continue
        if not any(ref in PRIORITY_REFS for ref, pin, p in real_pads):
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
        _, ref_a, pin_a, ref_b, pin_b = best_edge

        # Which side (if either) is the J1/J2 pin needing the staged
        # escape? If neither side is, this net doesn't need staging --
        # skip it here (route_by_clusters.py already tried it).
        if ref_a in PRIORITY_REFS:
            j1_ref, j1_pin, other_ref, other_pin = ref_a, pin_a, ref_b, pin_b
        elif ref_b in PRIORITY_REFS:
            j1_ref, j1_pin, other_ref, other_pin = ref_b, pin_b, ref_a, pin_a
        else:
            continue

        pad_j1 = r.pad(j1_ref, j1_pin)
        pad_other = r.pad(other_ref, other_pin)
        px, py = mm(pad_j1.GetPosition().x), mm(pad_j1.GetPosition().y)
        target = escape_target(px, py)
        label = f"{net_name}: {j1_ref}.{j1_pin}-{other_ref}.{other_pin} (staged escape)"
        print(f"[{idx+1}/{len(net_names)}] {time.time()-t0:.0f}s {label}", flush=True)

        if target is None:
            # Not a row-1/row-2 GPIO pin (e.g. a power pin near the
            # connector's open end) -- the proven perpendicular escape
            # doesn't apply; fall through to a normal direct route.
            ok_direct = r.route(j1_ref, j1_pin, other_ref, other_pin, width_for(net_name), label)
            if ok_direct:
                ok += 1
                print("  OK (direct, no staging needed)", flush=True)
            else:
                fail += 1
                print("  FAIL (direct)", flush=True)
            continue

        tx, ty = target

        # Escape leg: the proven straight geometry, placed directly at
        # its real (unquantized) mm coordinates -- the coarse 0.2mm grid
        # this router otherwise works in can't reliably resolve the real
        # ~0.28-0.3mm corridor, and even just quantizing this leg's own
        # endpoints to that 0.2mm grid could drift them up to 0.1mm off
        # the exact geometry real DRC already verified clean earlier
        # this session. So this leg bypasses A* and the grid entirely:
        # a real PCB_TRACK at the exact proven coordinates, with the
        # router's obstacle grid updated the same way _commit() would
        # (via _paint_line, which also takes real mm coordinates) so
        # subsequent nets in this run see it as a real obstacle. Real
        # DRC after this run remains the actual authority either way.
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I(int(px * 1e6), int(py * 1e6)))
        track.SetEnd(pcbnew.VECTOR2I(int(tx * 1e6), int(ty * 1e6)))
        track.SetWidth(pcbnew.FromMM(ESCAPE_WIDTH_MM))
        track.SetLayer(pcbnew.F_Cu)
        track.SetNet(r.net_objs[net_name])
        board.Add(track)
        r._paint_line(0, px, py, tx, ty, ESCAPE_WIDTH_MM / 2, net_name)
        r._dilate_cache = {}
        escape_cell = to_cell(tx, ty)

        # Remainder: real long-distance A* from the escape landing point
        # to the actual destination pad, on the router's live obstacle
        # grid (which now includes the escape trace we just committed).
        other_layers = [l for l in (0, 1)
                         if pad_other.IsOnLayer(pcbnew.F_Cu if l == 0 else pcbnew.B_Cu)]
        goal_cell = to_cell(mm(pad_other.GetPosition().x), mm(pad_other.GetPosition().y))
        # Real destinations for J1's remaining nets turned out to be
        # whole-board-spanning (e.g. J6, ~79mm away, not "nearby" as an
        # earlier session's docs assumed) -- the default 0.3mm signal
        # width, committed along a long path through J1's own narrow
        # shared inter-row corridor, was found to consume the ENTIRE
        # corridor width for a single net over a long stretch (one net's
        # path blocked every other J1 net from using any part of the
        # same corridor). Using the proven 0.2mm width here too keeps
        # each net's own footprint through the shared corridor as small
        # as the real geometry allows, leaving more of it free for the
        # nets processed after it in this same run.
        widths_to_try = [ESCAPE_WIDTH_MM] + [w for w in r.THIN_RETRY_WIDTHS if w < ESCAPE_WIDTH_MM]
        remainder_path = None
        used_width = None
        import math as _math
        for w in widths_to_try:
            radius = max(0, _math.ceil((w / 2) / GRID))
            path = r._astar(escape_cell, goal_cell, net_name, [0], other_layers, radius)
            if path is not None:
                remainder_path, used_width = path, w
                break

        if remainder_path is not None:
            r._commit(remainder_path, used_width, net_name)
            r._dilate_cache = {}
            ok += 1
            print(f"  OK (escape 1.5mm + remainder {len(remainder_path)} cells @ {used_width}mm)", flush=True)
        else:
            # Remainder truly failed -- remove the escape stub so we
            # don't leave dangling copper with no destination.
            for t in list(board.GetTracks()):
                if (t.GetClass() == "PCB_TRACK" and t.GetNetname() == net_name
                        and abs(mm(t.GetStart().x) - px) < 1e-3 and abs(mm(t.GetStart().y) - py) < 1e-3
                        and abs(mm(t.GetEnd().x) - tx) < 1e-3 and abs(mm(t.GetEnd().y) - ty) < 1e-3):
                    board.Remove(t)
            r._dilate_cache = {}
            fail += 1
            print("  FAIL (escape landed, but no remainder path found -- escape stub removed)", flush=True)

        if ok and ok % 5 == 0:
            board.BuildConnectivity()
            pcbnew.SaveBoard(PCB_PATH, board)
            print(f"  (checkpoint saved, {ok} routed so far)", flush=True)

    print(f"\nStaged J1/J2 routing: {ok} succeeded, {fail} failed")
    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
