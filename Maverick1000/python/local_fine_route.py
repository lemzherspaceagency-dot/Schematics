#!/usr/bin/env python3
"""
Local, fine-grid, 2-layer (F.Cu/B.Cu, via-capable) A* router for the
pairs neither gen_routes_maze.py (0.2mm whole-board grid) nor
direct_connect.py's straight/L/Z templates could resolve. Diagnosed
across two prior passes in this session: (1) gen_routes_maze.py's 0.2mm
grid is coarser than several tight destinations' real available
clearance (a thinnest 0.1mm-wide retry still gets rounded UP via ceil()
to a full 1-cell/0.2mm search radius), and (2) a single-layer version of
this fine-grid router (no via support) still failed most of the same
pairs gen_routes_maze.py failed, confirming the real bottleneck for most
of them is needing to ESCAPE a densely packed pin field (e.g. J1's
100-pin 0.4mm-pitch CM4 connector) via a layer change that a same-layer
search cannot express.

This builds a small local 0.05mm-resolution, 2-layer grid covering just
a window around each remaining pair (expanded bounding box, capped in
size) and runs A* with via-layer-transition support, mirroring
gen_routes_maze.py's approach but at 4x finer resolution so it can find
escape paths through gaps narrower than 0.2mm. As with every other
router in this project, this is not trusted on its own: real KiCad DRC
(run_drc.py) + the established ripup_violations.py backstop is what
actually decides safety afterward.

Usage: python3 local_fine_route.py [drc_report.txt]
"""
import heapq
import math
import re
import sys

import numpy as np
import pcbnew
from scipy.ndimage import binary_dilation

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from board_rules import ClearanceModel

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"
REPORT = sys.argv[1] if len(sys.argv) > 1 else "/home/user/Schematics/Maverick1000/verification/drc_report.txt"

GRID = 0.05  # mm
CLEARANCE = 0.2  # this board's Default netclass clearance -- the real
# per-region floor; ClearanceModel narrows this further inside J1/J2/U3's
# real courtyard extent, per the board's own .kicad_dru rules (see
# board_rules.py). Every place below that painted a flat CLEARANCE now
# uses CLEARANCE_MODEL.at_point(x, y) instead.
# Real, pre-existing bug found while verifying this pass's first routes
# against real DRC: to_cell() rounds each painted obstacle boundary to
# the NEAREST grid line, not conservatively outward, which can silently
# erode up to half a grid cell (0.025mm at this 0.05mm grid) of real
# required clearance -- and the A* path's own position is independently
# quantized the same way, so the combined worst case is up to a full
# cell. This was never caught before because no prior run of this
# router had exercised a genuinely marginal default-clearance path;
# this pass's real DRC run did (3 clearance + 2 hole_clearance
# violations at U2/U7/U3, unrelated to the J1/J2 courtyard fix). Fixed
# by adding one full grid cell of buffer to any DEFAULT-region
# clearance (never to a narrowed courtyard rule's own exact value --
# that would shrink the J1 escape corridor this whole fix exists to
# open back below what real DRC has already confirmed fits) and to the
# physical hole-to-hole drill constant, which applies everywhere.
QUANT_MARGIN = GRID
MAX_WINDOW_MM = 130.0
VIA_DIA = 0.6
VIA_DRILL = 0.4
HOLE_TO_HOLE = 0.26 + QUANT_MARGIN
VIA_COPPER_RADIUS_CELLS = max(1, math.ceil((VIA_DIA / 2) / GRID))
VIA_HOLE_RADIUS_CELLS = max(1, math.ceil((HOLE_TO_HOLE + VIA_DRILL / 2) / GRID))
VIA_COST = 30
TRY_WIDTHS = (0.25, 0.2, 0.15, 0.1, 0.075)
_POWER_NETS = {
    "+3V3", "+5V0", "VBAT_BUS", "MODEM_VBAT", "BATT_F", "P1_F",
    "VBAT_MAIN_OUT", "VBAT_P1_OUT", "5V0_SW", "5V0_PRE", "DOCK_PWR_RAW",
    "DOCK_F", "TERRA_BATT_RAW", "TERRA_PWR", "MODEM_5V0_SW",
}
_POWER_MIN_WIDTH = 0.3
LAYER_IDS = (pcbnew.F_Cu, pcbnew.B_Cu)


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


class LocalWindow:
    """2-layer (0=F.Cu, 1=B.Cu) local obstacle grid + via-capable A*."""

    def __init__(self, board, net, x0, y0, x1, y1, clearance_model=None):
        self.x0 = x0 - 1.0
        self.y0 = y0 - 1.0
        self.x1 = x1 + 1.0
        self.y1 = y1 + 1.0
        self.net = net
        self.clearance_model = clearance_model
        self.nx = int((self.x1 - self.x0) / GRID) + 1
        self.ny = int((self.y1 - self.y0) / GRID) + 1
        self.owner = {0: np.full((self.ny, self.nx), "", dtype=object),
                      1: np.full((self.ny, self.nx), "", dtype=object)}
        self.via_owner = np.full((self.ny, self.nx), "", dtype=object)
        self._dilate_cache = {}
        self._build(board)

    def _clearance_at(self, x, y):
        base = CLEARANCE if self.clearance_model is None else self.clearance_model.at_point(x, y)
        # Only buffer the default-region value against grid-quantization
        # error; a narrowed courtyard rule (J1/J2 0.15mm, U3 0.05mm) is
        # used exactly as real DRC enforces it, unbuffered -- see
        # QUANT_MARGIN's docstring above.
        return base if base < CLEARANCE else base + QUANT_MARGIN

    def to_cell(self, x, y):
        return (int(round((x - self.x0) / GRID)), int(round((y - self.y0) / GRID)))

    def to_mm(self, cx, cy):
        return (self.x0 + cx * GRID, self.y0 + cy * GRID)

    def _paint_rect(self, layer, cx0, cy0, cx1, cy1, net):
        cx0 = max(0, cx0); cy0 = max(0, cy0)
        cx1 = min(self.nx - 1, cx1); cy1 = min(self.ny - 1, cy1)
        if cx1 < cx0 or cy1 < cy0:
            return
        region = self.owner[layer][cy0:cy1 + 1, cx0:cx1 + 1]
        free = region == ""
        same = region == net
        other = ~free & ~same
        region[free] = net
        region[other] = "#"

    def _paint_via_rect(self, cx0, cy0, cx1, cy1, net):
        cx0 = max(0, cx0); cy0 = max(0, cy0)
        cx1 = min(self.nx - 1, cx1); cy1 = min(self.ny - 1, cy1)
        if cx1 < cx0 or cy1 < cy0:
            return
        region = self.via_owner[cy0:cy1 + 1, cx0:cx1 + 1]
        free = region == ""
        same = region == net
        other = ~free & ~same
        region[free] = net
        region[other] = "#"

    def _in_window(self, x, y, pad=3):
        return not (x < self.x0 - pad or x > self.x1 + pad or y < self.y0 - pad or y > self.y1 + pad)

    def _build(self, board):
        pad_list = []
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                p = pad.GetPosition()
                x, y = mm(p.x), mm(p.y)
                if not self._in_window(x, y):
                    continue
                pad_list.append(pad)
            for z in fp.Zones():
                if not z.GetIsRuleArea() or not z.GetDoNotAllowTracks():
                    continue
                bbox = z.GetBoundingBox()
                x0, y0b = mm(bbox.GetLeft()), mm(bbox.GetTop())
                x1, y1b = mm(bbox.GetRight()), mm(bbox.GetBottom())
                cx0, cy0 = self.to_cell(x0, y0b)
                cx1, cy1 = self.to_cell(x1, y1b)
                for layer, kicad_layer in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)):
                    if z.GetLayerSet().Contains(kicad_layer):
                        self._paint_rect(layer, cx0, cy0, cx1, cy1, "#")

        # Phase 1: clearance halos.
        for pad in pad_list:
            net = pad.GetNetname()
            p = pad.GetPosition()
            x, y = mm(p.x), mm(p.y)
            # GetBoundingBox() (not GetSize(), which is pre-rotation local
            # size) gives the real board-space width/height -- a real bug
            # this session found via gen_routes_maze.py: GetSize() alone
            # swaps w/h on any 90/270-degree-rotated pad.
            bbox = pad.GetBoundingBox()
            w, h = mm(bbox.GetWidth()), mm(bbox.GetHeight())
            # Real-rule-aware: inside J1/J2's real courtyard this is
            # 0.15mm (the board's own CM4_connector_fine_pitch_clearance
            # rule), inside U3's 0.05mm, elsewhere the Default netclass's
            # 0.2mm -- not a second hardcoded guess. A prior version of
            # this router gave an empty-net (NC) pad an artificially
            # reduced 0.15mm floor everywhere, assuming real DRC cared
            # less about unconnected copper -- it doesn't: real DRC
            # flagged a genuine [clearance] violation (0.1875mm actual
            # vs the real 0.2mm Default requirement) against an NC pad
            # on U7 outside any special courtyard. NC pads now get
            # exactly the same real-rule clearance as any other pad.
            clearance = self._clearance_at(x, y)
            hw, hh = w / 2 + clearance, h / 2 + clearance
            cx0, cy0 = self.to_cell(x - hw, y - hh)
            cx1, cy1 = self.to_cell(x + hw, y + hh)
            key = net if net else "#"
            for layer, kicad_layer in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)):
                if pad.IsOnLayer(kicad_layer):
                    self._paint_rect(layer, cx0, cy0, cx1, cy1, key)
            if pad.HasHole():
                drill = pad.GetDrillSize()
                hr = max(mm(drill.x), mm(drill.y)) / 2
                vcx0, vcy0 = self.to_cell(x - hr - HOLE_TO_HOLE, y - hr - HOLE_TO_HOLE)
                vcx1, vcy1 = self.to_cell(x + hr + HOLE_TO_HOLE, y + hr + HOLE_TO_HOLE)
                self._paint_via_rect(vcx0, vcy0, vcx1, vcy1, key)
            else:
                # Real DRC's board-wide minimum hole clearance
                # ("board setup constraints hole", 0.25mm) applies to
                # ANY copper an unrelated net's drilled hole comes near
                # -- not only other holes. A holeless SMD pad was never
                # painted into via_owner at all before this fix, so a
                # new via's drill could land closer to it than real DRC
                # allows with zero warning from this router's own model.
                # Found directly: real DRC flagged exactly this (a new
                # via 0.21mm from a WQFN SMD pad's copper, real minimum
                # 0.25mm) on U3 (BQ25792), whose pins are almost all
                # holeless SMD. Using the pad's own copper half-extent
                # (already computed above as hw/hh) instead of a hole
                # radius that doesn't exist.
                vcx0, vcy0 = self.to_cell(x - hw - HOLE_TO_HOLE, y - hh - HOLE_TO_HOLE)
                vcx1, vcy1 = self.to_cell(x + hw + HOLE_TO_HOLE, y + hh + HOLE_TO_HOLE)
                self._paint_via_rect(vcx0, vcy0, vcx1, vcy1, key)

        # Phase 2: pad cores always win.
        for pad in pad_list:
            net = pad.GetNetname()
            if not net:
                continue
            p = pad.GetPosition()
            x, y = mm(p.x), mm(p.y)
            bbox = pad.GetBoundingBox()
            w, h = mm(bbox.GetWidth()), mm(bbox.GetHeight())
            cx0, cy0 = self.to_cell(x - w / 2, y - h / 2)
            cx1, cy1 = self.to_cell(x + w / 2, y + h / 2)
            cx0, cy0 = max(0, cx0), max(0, cy0)
            cx1, cy1 = min(self.nx - 1, cx1), min(self.ny - 1, cy1)
            if cx1 < cx0 or cy1 < cy0:
                continue
            for layer, kicad_layer in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)):
                if pad.IsOnLayer(kicad_layer):
                    self.owner[layer][cy0:cy1 + 1, cx0:cx1 + 1] = net

        for t in board.GetTracks():
            layer = 0 if t.GetLayer() == pcbnew.F_Cu else (1 if t.GetLayer() == pcbnew.B_Cu else None)
            net = t.GetNetname()
            key = net if net else "#"
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                x, y = mm(p.x), mm(p.y)
                if not self._in_window(x, y):
                    continue
                r = mm(t.GetWidth()) / 2
                via_clearance = self._clearance_at(x, y)
                cx0, cy0 = self.to_cell(x - r - via_clearance, y - r - via_clearance)
                cx1, cy1 = self.to_cell(x + r + via_clearance, y + r + via_clearance)
                self._paint_rect(0, cx0, cy0, cx1, cy1, key)
                self._paint_rect(1, cx0, cy0, cx1, cy1, key)
                hr = VIA_DRILL / 2
                vcx0, vcy0 = self.to_cell(x - hr - HOLE_TO_HOLE, y - hr - HOLE_TO_HOLE)
                vcx1, vcy1 = self.to_cell(x + hr + HOLE_TO_HOLE, y + hr + HOLE_TO_HOLE)
                self._paint_via_rect(vcx0, vcy0, vcx1, vcy1, key)
                continue
            s, e = t.GetStart(), t.GetEnd()
            x1, y1, x2, y2 = mm(s.x), mm(s.y), mm(e.x), mm(e.y)
            # A segment's own endpoints can both sit outside the window
            # while its middle still crosses through it -- checking only
            # the endpoints missed exactly this case (a real bug this
            # pass found via actual DRC violations). Use the segment's
            # bounding box against the window instead.
            seg_x0, seg_x1 = min(x1, x2), max(x1, x2)
            seg_y0, seg_y1 = min(y1, y2), max(y1, y2)
            pad = 3
            if (seg_x1 < self.x0 - pad or seg_x0 > self.x1 + pad
                    or seg_y1 < self.y0 - pad or seg_y0 > self.y1 + pad):
                continue
            half_width = mm(t.GetWidth()) / 2
            length = math.hypot(x2 - x1, y2 - y1)
            steps = max(1, int(length / (GRID / 2)))
            # Every track on every layer (including In1.Cu/In2.Cu, which
            # this router never routes on but a new via's drilled barrel
            # still physically passes through) gets painted into
            # via_owner -- a real, structural gap this pass found via
            # actual DRC: a new via landed at 0.0mm clearance from an
            # existing In1.Cu track (BOOT_USB_DM) this router had zero
            # visibility into, and separately at a real
            # [hole_clearance] violation against an F.Cu track whose
            # copper clearance alone (owner[layer], below) wasn't a tight
            # enough proxy for the real, separate 0.25mm hole-to-copper
            # requirement.
            for i in range(steps + 1):
                tt = i / steps
                x = x1 + (x2 - x1) * tt
                y = y1 + (y2 - y1) * tt
                half = half_width + HOLE_TO_HOLE
                vcx0, vcy0 = self.to_cell(x - half, y - half)
                vcx1, vcy1 = self.to_cell(x + half, y + half)
                self._paint_via_rect(vcx0, vcy0, vcx1, vcy1, key)
            if layer is None:
                continue
            for i in range(steps + 1):
                tt = i / steps
                x = x1 + (x2 - x1) * tt
                y = y1 + (y2 - y1) * tt
                half = half_width + self._clearance_at(x, y)
                cx0, cy0 = self.to_cell(x - half, y - half)
                cx1, cy1 = self.to_cell(x + half, y + half)
                self._paint_rect(layer, cx0, cy0, cx1, cy1, key)

    def _blocked(self, layer, radius, source="owner"):
        key = (layer, radius, source)
        cached = self._dilate_cache.get(key)
        if cached is not None:
            return cached
        grid = self.owner[layer] if source == "owner" else self.via_owner
        if source == "via_hole":
            occupied = grid != ""
        else:
            occupied = (grid != "") & (grid != self.net)
        if radius == 0:
            blocked = occupied
        else:
            size = 2 * radius + 1
            blocked = binary_dilation(occupied, structure=np.ones((size, size), dtype=bool))
        self._dilate_cache[key] = blocked
        return blocked

    def _passable(self, layer, cx, cy, radius):
        if cx < 0 or cx >= self.nx or cy < 0 or cy >= self.ny:
            return False
        return not self._blocked(layer, radius)[cy, cx]

    def _via_ok(self, cx, cy):
        if cx < 0 or cx >= self.nx or cy < 0 or cy >= self.ny:
            return False
        return not self._blocked(0, VIA_HOLE_RADIUS_CELLS, source="via_hole")[cy, cx]

    def astar(self, start_xy, start_layers, goal_xy, goal_layers, radius):
        start = self.to_cell(*start_xy)
        goal = self.to_cell(*goal_xy)
        if not (0 <= start[0] < self.nx and 0 <= start[1] < self.ny):
            return None
        if not (0 <= goal[0] < self.nx and 0 <= goal[1] < self.ny):
            return None

        def h(cx, cy):
            return math.hypot(cx - goal[0], cy - goal[1])

        NB = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
              (1, 1, 1.41421), (1, -1, 1.41421), (-1, 1, 1.41421), (-1, -1, 1.41421)]
        openq = []
        best = {}
        for layer in start_layers:
            s = (start[0], start[1], layer)
            best[s] = 0
            heapq.heappush(openq, (h(start[0], start[1]), s, None))
        came_from = {}
        goal_set = {(goal[0], goal[1], layer) for layer in goal_layers}

        max_expansions = 500000
        expansions = 0
        found = None
        while openq and expansions < max_expansions:
            _, cur, parent = heapq.heappop(openq)
            if cur in came_from:
                continue
            came_from[cur] = parent
            if cur in goal_set:
                found = cur
                break
            expansions += 1
            cx, cy, layer = cur
            g = best[cur]
            for dx, dy, cost in NB:
                nx_, ny_ = cx + dx, cy + dy
                ns = (nx_, ny_, layer)
                if not self._passable(layer, nx_, ny_, radius):
                    continue
                ng = g + cost
                if ns not in best or ng < best[ns]:
                    best[ns] = ng
                    heapq.heappush(openq, (ng + h(nx_, ny_), ns, cur))
            other = 1 - layer
            if (self._passable(layer, cx, cy, VIA_COPPER_RADIUS_CELLS)
                    and self._passable(other, cx, cy, VIA_COPPER_RADIUS_CELLS)
                    and self._via_ok(cx, cy)):
                ns = (cx, cy, other)
                ng = g + VIA_COST
                if ns not in best or ng < best[ns]:
                    best[ns] = ng
                    heapq.heappush(openq, (ng + h(cx, cy), ns, cur))

        if found is None:
            return None
        path = []
        node = found
        while node is not None:
            path.append(node)
            node = came_from[node]
        path.reverse()
        return [(self.to_mm(cx, cy)[0], self.to_mm(cx, cy)[1], layer) for cx, cy, layer in path]


def simplify(path):
    if len(path) < 3:
        return path
    out = [path[0]]
    for i in range(1, len(path) - 1):
        ax, ay, al = out[-1]
        bx, by, bl = path[i]
        cx, cy, cl = path[i + 1]
        if al != bl or bl != cl:
            out.append(path[i])
            continue
        d1 = (round(bx - ax, 6), round(by - ay, 6))
        d2 = (round(cx - bx, 6), round(cy - by, 6))
        n1 = math.hypot(*d1) or 1
        n2 = math.hypot(*d2) or 1
        u1 = (d1[0] / n1, d1[1] / n1)
        u2 = (d2[0] / n2, d2[1] / n2)
        if abs(u1[0] - u2[0]) > 1e-3 or abs(u1[1] - u2[1]) > 1e-3:
            out.append(path[i])
    out.append(path[-1])
    return out


def build_cluster_pairs(board, priority_refs=("J1", "J2")):
    """Real-connectivity-based pair generation (board_clusters.py's
    pad-bounding-box-correct clusters), NOT the DRC-report text parser --
    that parser only sees pad-pair '[unconnected_items]' blocks, which a
    prior pass found silently skips any unconnected block whose endpoint
    is a Track/PTH rather than a bare pad (61 of 105 missed). This
    mirrors route_by_clusters.py's real per-net nearest-cluster-edge
    approach, and additionally sorts nets so every net touching a
    priority ref (J1/J2, per this run's routing-stage priority) is
    attempted before anything else."""
    sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
    from design_data import NETS
    from board_clusters import get_net_clusters

    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        if fp is None:
            return None
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p
        return None

    tracks_by_net = {}
    for t in board.GetTracks():
        tracks_by_net.setdefault(t.GetNetname(), []).append(t)

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

    priority, rest = [], []
    for net_name, conns in NETS.items():
        if net_name == "GND":
            continue
        real_pads = [(ref, pin, find_pad(ref, pin)) for ref, pin in conns if find_pad(ref, pin)]
        if len(real_pads) < 2:
            continue
        clusters = get_net_clusters(board, net_name, real_pads, tracks_by_net)
        if len(clusters) <= 1:
            continue
        is_priority = any(ref in priority_refs for ref, pin, p in real_pads)
        # One nearest-cluster edge per net per pass -- matches
        # route_by_clusters.py's own iterate-until-merged approach;
        # re-running this script after a save picks up newly-merged
        # clusters and finds the next edge.
        best_edge = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                cand = nearest_pair(clusters[i], clusters[j])
                if best_edge is None or cand[0] < best_edge[0]:
                    best_edge = cand
        if best_edge is None:
            continue
        _, ref_a, pin_a, ref_b, pin_b = best_edge
        (priority if is_priority else rest).append((net_name, ref_a, pin_a, ref_b, pin_b))

    return priority + rest


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    pairs = build_cluster_pairs(board)
    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
    net_objs = {n.GetNetname(): n for n in board.GetNetInfo().NetsByNetcode().values()}
    clearance_model = ClearanceModel(board)

    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        if fp is None:
            return None
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p
        return None

    import time
    t0 = time.time()
    ok, fail = 0, 0
    for idx, (net_name, ref_a, pin_a, ref_b, pin_b) in enumerate(pairs):
        print(f"[{idx+1}/{len(pairs)}] {time.time()-t0:.0f}s {net_name}: {ref_a}.{pin_a}-{ref_b}.{pin_b}", flush=True)
        pa, pb = find_pad(ref_a, pin_a), find_pad(ref_b, pin_b)
        if pa is None or pb is None:
            fail += 1
            continue
        a_layers = [l for l, kl in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)) if pa.IsOnLayer(kl)]
        b_layers = [l for l, kl in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)) if pb.IsOnLayer(kl)]
        if not a_layers or not b_layers:
            fail += 1
            continue
        ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
        bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
        dist = math.hypot(bx - ax, by - ay)
        span = max(dist, 2.0)
        if span > MAX_WINDOW_MM:
            fail += 1
            continue

        widths = TRY_WIDTHS
        if net_name in _POWER_NETS:
            widths = tuple(w for w in TRY_WIDTHS if w >= _POWER_MIN_WIDTH) or (_POWER_MIN_WIDTH,)

        win = LocalWindow(board, net_name, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by),
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
            continue

        path, w = placed
        net_obj = net_objs.get(net_name)
        for i in range(len(path) - 1):
            sx, sy, sl = path[i]
            ex, ey, el = path[i + 1]
            if sl != el:
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(pcbnew.VECTOR2I(nm(sx), nm(sy)))
                via.SetWidth(nm(VIA_DIA))
                via.SetDrill(nm(VIA_DRILL))
                via.SetNet(net_obj)
                via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                board.Add(via)
                continue
            if abs(sx - ex) < 1e-6 and abs(sy - ey) < 1e-6:
                continue
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(nm(sx), nm(sy)))
            track.SetEnd(pcbnew.VECTOR2I(nm(ex), nm(ey)))
            track.SetWidth(nm(w))
            track.SetLayer(pcbnew.F_Cu if sl == 0 else pcbnew.B_Cu)
            track.SetNet(net_obj)
            board.Add(track)
        ok += 1
        if ok % 5 == 0:
            board.BuildConnectivity()
            pcbnew.SaveBoard(PCB_PATH, board)
            print(f"  (checkpoint saved, {ok} routed so far)", flush=True)

    print(f"Local fine-grid (2-layer) routed: {ok}   Still failed: {fail}")
    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
