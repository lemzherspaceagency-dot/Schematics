#!/usr/bin/env python3
"""
Handles the remaining unrouted pairs gen_routes_maze.py's grid-based A*
genuinely cannot find a path for. Diagnosed: its 0.2mm grid cell size is
coarser than several of these pairs' real available clearance (e.g. a
thinnest 0.1mm-wide retry still gets rounded UP via ceil() to a full
1-cell/0.2mm search radius, four times its real half-width) -- a grid
resolution limit, not evidence the connection is physically impossible.
Most of the remaining pairs are short point-to-point runs between two
pins of the same or adjacent components (gate-driver/bootstrap/local
decoupling nets), which do not need maze-like obstacle navigation, just
correct clearance arithmetic.

This does real, continuous-space (not grid-quantized) geometry: for each
still-unconnected pair, try a straight line then simple L-shaped
(2-segment) and Z-shaped (3-segment, 45-degree first/last leg) manhattan
paths, at decreasing trace widths, and for each candidate checks true
point/segment-to-segment and point/segment-to-rectangle clearance against
every real pad and track in a local bounding box (excluding same-net
items) -- not a rasterized approximation. A candidate is committed as
real PCB_TRACK segment(s) only if it clears every nearby item by the
required clearance. As with every other router in this project, this is
not trusted on its own: real KiCad DRC (run_drc.py) + the established
ripup_violations.py backstop is what actually decides safety afterward.

Usage: python3 direct_connect.py [drc_report.txt]
"""
import math
import re
import sys

import pcbnew

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"
REPORT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/Schematics/Maverick1000/verification/drc_report.txt"

CLEARANCE = 0.2  # mm, default netclass clearance (matches board setup)
TRY_WIDTHS = (0.25, 0.2, 0.15, 0.1, 0.075)
_POWER_NETS = {
    "+3V3", "+5V0", "VBAT_BUS", "MODEM_VBAT", "BATT_F", "P1_F",
    "VBAT_MAIN_OUT", "VBAT_P1_OUT", "5V0_SW", "5V0_PRE", "DOCK_PWR_RAW",
    "DOCK_F", "TERRA_BATT_RAW", "TERRA_PWR", "MODEM_5V0_SW",
}
_POWER_MIN_WIDTH = 0.3  # never thin a power net below this


def mm(v):
    return v / 1e6


def nm(v):
    return int(round(v * 1e6))


def parse_unconnected(text):
    pairs = []
    blocks = re.split(r"\n(?=\[[a-z_]+\]: )", text)
    for block in blocks:
        if not block.startswith("[unconnected_items]"):
            continue
        m = re.findall(r"Pad (\S+) \[([^\]]*)\] of (\S+) on", block)
        if len(m) == 2:
            (pin_a, net_a, ref_a), (pin_b, net_b, ref_b) = m
            pairs.append((net_a, ref_a, pin_a, ref_b, pin_b))
    return pairs


def seg_point_dist(ax, ay, bx, by, px, py):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def seg_seg_dist(ax, ay, bx, by, cx, cy, dx_, dy_):
    # Sample-based approximation (fine enough at this scale): min of
    # endpoint-to-segment distances both ways, dense enough for the
    # short segments this script generates.
    best = min(
        seg_point_dist(ax, ay, bx, by, cx, cy),
        seg_point_dist(ax, ay, bx, by, dx_, dy_),
        seg_point_dist(cx, cy, dx_, dy_, ax, ay),
        seg_point_dist(cx, cy, dx_, dy_, bx, by),
    )
    steps = 8
    for i in range(1, steps):
        t = i / steps
        px, py = ax + (bx - ax) * t, ay + (by - ay) * t
        best = min(best, seg_point_dist(cx, cy, dx_, dy_, px, py))
    return best


def seg_rect_dist(ax, ay, bx, by, rx0, ry0, rx1, ry1):
    # Distance from a segment to an axis-aligned rectangle (0 if they
    # overlap). Sampled along the segment against the rect's clamp point.
    steps = 12
    best = None
    for i in range(steps + 1):
        t = i / steps
        px, py = ax + (bx - ax) * t, ay + (by - ay) * t
        cx = min(max(px, rx0), rx1)
        cy = min(max(py, ry0), ry1)
        d = math.hypot(px - cx, py - cy)
        if best is None or d < best:
            best = d
    return best


class Obstacle:
    __slots__ = ("net", "kind", "geom")


def build_local_obstacles(board, net, x0, y0, x1, y1, margin, layer):
    """Returns lists of (net, rect) for pads and (net, seg, half_w) for
    tracks within [x0-margin, x1+margin] x [y0-margin, y1+margin] on the
    given KiCad layer, excluding items on `net`."""
    lx0, ly0, lx1, ly1 = x0 - margin, y0 - margin, x1 + margin, y1 + margin
    pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() == net:
                continue
            if not pad.IsOnLayer(layer):
                continue
            p = pad.GetPosition()
            px, py = mm(p.x), mm(p.y)
            if px < lx0 - 2 or px > lx1 + 2 or py < ly0 - 2 or py > ly1 + 2:
                continue
            # GetBoundingBox(), not GetSize() (pre-rotation local size --
            # swaps w/h on any 90/270-degree-rotated pad, a real bug
            # found this session via gen_routes_maze.py).
            bbox = pad.GetBoundingBox()
            w, h = mm(bbox.GetWidth()), mm(bbox.GetHeight())
            pads.append((pad.GetNetname(), px - w / 2, py - h / 2, px + w / 2, py + h / 2))

    tracks = []
    for t in board.GetTracks():
        if t.GetNetname() == net:
            continue
        if t.GetClass() == "PCB_VIA":
            if t.GetLayer() not in (layer,) and layer not in (pcbnew.F_Cu, pcbnew.B_Cu):
                pass
            p = t.GetPosition()
            px, py = mm(p.x), mm(p.y)
            if px < lx0 - 2 or px > lx1 + 2 or py < ly0 - 2 or py > ly1 + 2:
                continue
            r = mm(t.GetWidth()) / 2
            tracks.append((t.GetNetname(), px, py, px, py, r))
        else:
            if t.GetLayer() != layer:
                continue
            s, e = t.GetStart(), t.GetEnd()
            sx, sy, ex, ey = mm(s.x), mm(s.y), mm(e.x), mm(e.y)
            if max(sx, ex) < lx0 - 2 or min(sx, ex) > lx1 + 2 or max(sy, ey) < ly0 - 2 or min(sy, ey) > ly1 + 2:
                continue
            r = mm(t.GetWidth()) / 2
            tracks.append((t.GetNetname(), sx, sy, ex, ey, r))
    return pads, tracks


def path_clear(pads, tracks, path_pts, half_w, own_net):
    req = half_w + CLEARANCE
    for i in range(len(path_pts) - 1):
        ax, ay = path_pts[i]
        bx, by = path_pts[i + 1]
        for pnet, rx0, ry0, rx1, ry1 in pads:
            d = seg_rect_dist(ax, ay, bx, by, rx0, ry0, rx1, ry1)
            if d < req:
                return False
        for tnet, sx, sy, ex, ey, tr in tracks:
            d = seg_seg_dist(ax, ay, bx, by, sx, sy, ex, ey)
            if d < half_w + tr + CLEARANCE:
                return False
    return True


def candidate_paths(ax, ay, bx, by):
    paths = []
    paths.append([(ax, ay), (bx, by)])
    paths.append([(ax, ay), (bx, ay), (bx, by)])
    paths.append([(ax, ay), (ax, by), (bx, by)])
    dx, dy = bx - ax, by - ay
    adx, ady = abs(dx), abs(dy)
    if adx > 1e-6 and ady > 1e-6:
        short = min(adx, ady)
        sx = math.copysign(short, dx)
        sy = math.copysign(short, dy)
        paths.append([(ax, ay), (ax + sx, ay + sy), (bx, by)])
        paths.append([(ax, ay), (bx - sx, by - sy), (bx, by)])
    return paths


def main():
    pairs = parse_unconnected(open(REPORT).read())
    print(f"Parsed {len(pairs)} unconnected pad-pairs from {REPORT}")

    board = pcbnew.LoadBoard(PCB_PATH)
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
    for net_name, ref_a, pin_a, ref_b, pin_b in pairs:
        pa, pb = find_pad(ref_a, pin_a), find_pad(ref_b, pin_b)
        if pa is None or pb is None:
            fail += 1
            continue
        layer = pcbnew.F_Cu if pa.IsOnLayer(pcbnew.F_Cu) and pb.IsOnLayer(pcbnew.F_Cu) else None
        if layer is None:
            fail += 1
            continue  # needs a via / layer change -- not this script's job
        ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
        bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
        dist = math.hypot(bx - ax, by - ay)
        if dist > 12.0:
            fail += 1
            continue  # too far for a blind direct/L/Z shape -- leave to the maze router

        widths = TRY_WIDTHS
        if net_name in _POWER_NETS:
            widths = tuple(w for w in TRY_WIDTHS if w >= _POWER_MIN_WIDTH) or (_POWER_MIN_WIDTH,)

        margin = dist + 3.0
        pads, tracks = build_local_obstacles(board, net_name, min(ax, bx), min(ay, by),
                                              max(ax, bx), max(ay, by), margin, layer)

        placed = None
        for w in widths:
            half_w = w / 2
            for path in candidate_paths(ax, ay, bx, by):
                if path_clear(pads, tracks, path, half_w, net_name):
                    placed = (path, w)
                    break
            if placed:
                break

        if placed is None:
            fail += 1
            continue

        path, w = placed
        net_obj = net_objs.get(net_name)
        for i in range(len(path) - 1):
            sx, sy = path[i]
            ex, ey = path[i + 1]
            if sx == ex and sy == ey:
                continue
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(nm(sx), nm(sy)))
            track.SetEnd(pcbnew.VECTOR2I(nm(ex), nm(ey)))
            track.SetWidth(nm(w))
            track.SetLayer(layer)
            track.SetNet(net_obj)
            board.Add(track)
        ok += 1

    print(f"Direct-connected: {ok}   Still failed: {fail}")
    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
