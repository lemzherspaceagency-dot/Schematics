#!/usr/bin/env python3
"""
Surgical fix for this project's single most common recurring failure:
a router-placed via lands marginally (0.02-0.05mm) too close to a
holeless SMD pad's real min_hole_clearance (0.25mm) requirement. Real
DRC catches it every time; the standing ripup_violations.py backstop
then deletes the WHOLE via (and therefore the whole route, not just the
marginal bit), sending the net back to unconnected -- confirmed via
diagnose_unconnected.py that every hole_clearance/clearance violation
seen this session was exactly this pattern.

Processes ONE net per invocation (own OS process, own fresh pcbnew
state) -- confirmed directly that multiple pcbnew.LoadBoard() calls
within a single Python process corrupt its SWIG bindings (a second
LoadBoard() in-process returned a bare SwigPyObject missing
GetFootprints entirely). Driven in a loop from bash, matching this
project's established safe pattern of one pcbnew operation per `python3`
subprocess invocation throughout the whole session.

Usage:
  python3 reroute_around_violation.py list <drc_report.txt>
    -> prints "NET x0 y0 x1 y1 ..." lines, one per offending net, for a
       shell loop to consume.
  python3 reroute_around_violation.py fix <net_name> <x0> <y0> [<x1> <y1> ...]
    -> removes NET's own copper, re-searches with those via positions
       blacklisted, places the new path if found. Exits 0 on success,
       1 on failure (net just stays unconnected, no worse than before).
"""
import sys, re, math
from collections import defaultdict

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


def parse_bad_vias(report_path):
    text = open(report_path).read()
    blocks = re.split(r"\n(?=\[[a-z_]+\]: )", text)
    bad = defaultdict(list)
    for block in blocks:
        if not (block.startswith("[hole_clearance]") or block.startswith("[clearance]")):
            continue
        for m in re.finditer(r"@\(([\d.]+) mm, ([\d.]+) mm\): Via \[([^\]]+)\]", block):
            x, y, net = float(m.group(1)), float(m.group(2)), m.group(3)
            bad[net].append((x, y))
    return bad


def cmd_list(report_path):
    bad = parse_bad_vias(report_path)
    for net_name, positions in bad.items():
        coords = " ".join(f"{x} {y}" for x, y in positions)
        print(f"{net_name} {coords}")


def connected_component(items, seed_points, tol_mm=0.01):
    """items: track/via objects of ONE net. seed_points: real-world
    (x,y) mm points (e.g. a violating via's position) to start from.
    Returns the subset of items reachable from any seed point via
    shared endpoints -- i.e. just the one physically-connected route
    that via belongs to, not the whole net. A real regression this pass
    found: removing ALL of a net's board-wide copper to fix ONE
    marginal via (rather than just that via's own local route) silently
    destroyed +3V3's ~30-pad, many-cluster existing routing down to a
    single freshly re-placed 2-pad segment -- 7->75 unconnected in one
    step. This function is the fix: isolate precisely the connected
    piece containing the violation, nothing else."""
    def key(pt):
        return (round(pt.x / (tol_mm * 1e6)), round(pt.y / (tol_mm * 1e6)))

    by_point = {}
    for idx, t in enumerate(items):
        pts = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
        for pt in pts:
            by_point.setdefault(key(pt), []).append(idx)

    visited = set()
    frontier = []
    for sx, sy in seed_points:
        k = (round(sx / tol_mm), round(sy / tol_mm))
        frontier.extend(by_point.get(k, []))
    frontier = list(set(frontier))
    while frontier:
        idx = frontier.pop()
        if idx in visited:
            continue
        visited.add(idx)
        t = items[idx]
        pts = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
        for pt in pts:
            for nb in by_point.get(key(pt), []):
                if nb not in visited:
                    frontier.append(nb)
    return [items[i] for i in visited]


def cmd_fix(net_name, positions):
    board = pcbnew.LoadBoard(PCB_PATH)
    # Remove ONLY the connected piece of copper containing the
    # violating via(s) -- NOT the whole net's copper board-wide (see
    # connected_component()'s docstring for the regression this fixes).
    net_items = [t for t in board.GetTracks() if t.GetNetname() == net_name]
    to_remove = connected_component(net_items, positions)
    if not to_remove:
        # Fallback: violating via wasn't found by point-match (shouldn't
        # happen since we parsed it from this net's own DRC violation,
        # but never silently remove everything as a substitute).
        print(f"{net_name}: could not isolate the violating segment -- skipping (net's existing copper left untouched)")
        sys.exit(1)
    for t in to_remove:
        board.Remove(t)

    pairs = build_cluster_pairs(board, order="nearest")
    gap = None
    for n, ref_a, pin_a, ref_b, pin_b in pairs:
        if n == net_name:
            gap = (ref_a, pin_a, ref_b, pin_b)
            break
    if gap is None:
        print(f"{net_name}: no gap found even after removing its own copper -- likely a single-pad-pair net or a real bug")
        board.BuildConnectivity()
        pcbnew.SaveBoard(PCB_PATH, board)
        sys.exit(1)
    ref_a, pin_a, ref_b, pin_b = gap
    print(f"{net_name}: {ref_a}.{pin_a}-{ref_b}.{pin_b}, blacklisting {len(positions)} via position(s)")

    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        if fp is None:
            return None
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p

    pa, pb = find_pad(ref_a, pin_a), find_pad(ref_b, pin_b)
    if pa is None or pb is None:
        print("  pad not found")
        board.BuildConnectivity()
        pcbnew.SaveBoard(PCB_PATH, board)
        sys.exit(1)
    ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
    bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
    a_layers = [i for i, kl in enumerate(GRID_LAYERS) if pa.IsOnLayer(kl) or pa.HasHole()]
    b_layers = [i for i, kl in enumerate(GRID_LAYERS) if pb.IsOnLayer(kl) or pb.HasHole()]
    if not a_layers or not b_layers:
        print("  no accessible layer")
        board.BuildConnectivity()
        pcbnew.SaveBoard(PCB_PATH, board)
        sys.exit(1)

    widths = TRY_WIDTHS
    if net_name in _POWER_NETS:
        full = tuple(w for w in TRY_WIDTHS if w >= _POWER_MIN_WIDTH) or (_POWER_MIN_WIDTH,)
        neck = tuple(w for w in TRY_WIDTHS if w < _POWER_MIN_WIDTH) + (_POWER_NECK_WIDTH,)
        widths = full + neck

    clearance_model = ClearanceModel(board)
    win = LocalWindow3L(board, net_name, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by),
                         clearance_model=clearance_model)
    for fx, fy in positions:
        win.forbid_via_near(fx, fy)

    placed = None
    for w in widths:
        radius = max(0, math.ceil((w / 2) / GRID))
        path = win.astar((ax, ay), a_layers, (bx, by), b_layers, radius)
        if path is not None:
            placed = (simplify(path), w)
            break

    if placed is None:
        print("  NO PATH avoiding the blacklisted position(s) -- net stays unconnected")
        board.BuildConnectivity()
        pcbnew.SaveBoard(PCB_PATH, board)
        sys.exit(1)

    path, w = placed
    net_objs = {n.GetNetname(): n for n in board.GetNetInfo().NetsByNetcode().values()}
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
    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    print(f"  OK width={w}")
    sys.exit(0)


if __name__ == "__main__":
    if sys.argv[1] == "list":
        cmd_list(sys.argv[2])
    elif sys.argv[1] == "fix":
        net_name = sys.argv[2]
        coords = [float(x) for x in sys.argv[3:]]
        positions = list(zip(coords[0::2], coords[1::2]))
        cmd_fix(net_name, positions)
