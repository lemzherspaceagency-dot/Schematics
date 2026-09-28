#!/usr/bin/env python3
"""
Real grid-based A* maze router for SKYWARD-COMPUTE-CARRIER's remaining
unrouted connections. The earlier polyline-candidate router
(gen_routes.py / gen_routes_full.py) is a simple heuristic that cannot
navigate genuinely dense, multi-obstacle areas (CM4 connector fanout,
fine-pitch QFN/hub corners) -- it hit a real ceiling there. This script
replaces that approach for the remaining nets with an actual maze router:
a 2-layer (F.Cu + B.Cu, via-transition) grid, occupancy computed from
every real pad and every already-placed track (dilated by the real
clearance the board's own netclass rules require), and A* pathfinding
that can bend around obstacles as many times as needed -- not just the
handful of pre-set L-shapes/jogs the old router tried.

Nothing is committed without the same discipline as every other router
in this project: real KiCad DRC (python/run_drc.py) is what decides
whether the result is actually connected and clearance-safe, not this
script's own pathfinding success.

Usage: python3 gen_routes_maze.py
"""
import heapq
import sys

import numpy as np
import pcbnew
from scipy.ndimage import binary_dilation

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from design_data import NETS
from board_rules import ClearanceModel

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"

GRID = 0.2  # mm per cell
BOARD_W, BOARD_H = 110.0, 125.0
EDGE_MARGIN = 0.6  # keep every cell this far from Edge.Cuts clear
NX = int(BOARD_W / GRID) + 1
NY = int(BOARD_H / GRID) + 1

VIA_DIA = 0.6
VIA_DRILL = 0.4
VIA_COST = 30  # grid steps' worth of extra cost to discourage gratuitous layer hops
HOLE_TO_HOLE = 0.26
import math
# Always round UP (ceil), never to-nearest -- a radius that rounds DOWN
# by even half a cell (0.1mm at this grid resolution) can silently
# under-cover the real required clearance, which is exactly the class of
# bug real DRC caught here as genuine Pad-Via/hole-spacing violations
# (see docs/ROUTING_STATUS.md). +1 extra cell on top of the exact
# geometric requirement is deliberate slack for this grid's 0.2mm
# quantization, not a second guess at the real clearance number.
# The "+1" extra safety cell this originally carried on top of ceil()
# was re-derived this pass: ceil(0.3/0.2)=2 cells=0.4mm already exceeds
# the real 0.3mm via-copper radius requirement by 0.1mm, and
# ceil(0.46/0.2)=3 cells=0.6mm already exceeds the real 0.46mm
# hole-to-hole requirement by 0.14mm -- ceil() alone already covers the
# grid's 0.2mm quantization with margin to spare, so the extra +1 (which
# was doubling that margin to 0.3mm/0.34mm) was blocking legitimate via
# placement in genuinely dense areas without adding real safety. Real
# DRC (run_drc.py) + ripup_violations.py remain the actual authority
# either way, exactly as before.
VIA_COPPER_RADIUS_CELLS = max(1, math.ceil((VIA_DIA / 2) / GRID))
VIA_HOLE_RADIUS_CELLS = max(1, math.ceil((HOLE_TO_HOLE + VIA_DRILL / 2) / GRID))

_POWER_WIDTHS = {
    "+3V3": 0.5, "+5V0": 0.6, "VBAT_BUS": 0.8, "MODEM_VBAT": 0.6,
    "BATT_F": 0.8, "P1_F": 0.6, "VBAT_MAIN_OUT": 0.6, "VBAT_P1_OUT": 0.5,
    "5V0_SW": 0.6, "5V0_PRE": 0.5, "DOCK_PWR_RAW": 0.6, "DOCK_F": 0.6,
    "TERRA_BATT_RAW": 0.5, "TERRA_PWR": 0.5, "MODEM_5V0_SW": 0.6,
}


def width_for(net_name):
    return _POWER_WIDTHS.get(net_name, 0.3)



def mm(v):
    return v / 1e6


def to_cell(x, y):
    return (int(round(x / GRID)), int(round(y / GRID)))


def to_mm(cx, cy):
    return (cx * GRID, cy * GRID)


class MazeRouter:
    def __init__(self, board):
        self.board = board
        self.clearance_model = ClearanceModel(board)
        self.fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
        self.net_objs = {n.GetNetname(): n for n in board.GetNetInfo().NetsByNetcode().values()}
        # owner[layer][y][x] = net-id string (or '' for free, '#' for
        # permanent obstacle e.g. board edge margin)
        self.owner = {0: np.full((NY, NX), "", dtype=object), 1: np.full((NY, NX), "", dtype=object)}
        self.via_owner = np.full((NY, NX), "", dtype=object)  # via hole positions, any layer
        self.results = []
        self._dilate_cache = {}
        self._build_edge_obstacles()
        self._build_pad_obstacles()
        self._build_existing_track_obstacles()
        self._build_existing_via_obstacles()
        self._build_keepout_obstacles()

    def _build_keepout_obstacles(self):
        # Footprint-embedded rule-area (keepout) zones -- e.g. J12's
        # antenna-connector no-copper area -- are real DRC-enforced
        # exclusion regions this router previously had zero awareness of,
        # which let a route cut straight through one (real DRC caught it
        # as [items_not_allowed]). Painted here as an unconditional hard
        # obstacle ('#', blocks every net, no same-net exemption) on
        # every layer the keepout covers.
        for fp in self.board.GetFootprints():
            for z in fp.Zones():
                if not z.GetIsRuleArea() or not z.GetDoNotAllowTracks():
                    continue
                bbox = z.GetBoundingBox()
                x0, y0 = mm(bbox.GetLeft()), mm(bbox.GetTop())
                x1, y1 = mm(bbox.GetRight()), mm(bbox.GetBottom())
                cx0, cy0 = to_cell(x0, y0)
                cx1, cy1 = to_cell(x1, y1)
                on_f = z.GetLayerSet().Contains(pcbnew.F_Cu)
                on_b = z.GetLayerSet().Contains(pcbnew.B_Cu)
                if on_f:
                    self._paint_rect(0, cx0, cy0, cx1, cy1, "#")
                if on_b:
                    self._paint_rect(1, cx0, cy0, cx1, cy1, "#")

    def _paint_rect(self, layer, cx0, cy0, cx1, cy1, net):
        cx0 = max(0, cx0)
        cy0 = max(0, cy0)
        cx1 = min(NX - 1, cx1)
        cy1 = min(NY - 1, cy1)
        if cx1 < cx0 or cy1 < cy0:
            return
        grid = self.owner[layer]
        region = grid[cy0:cy1 + 1, cx0:cx1 + 1]
        # Only overwrite free cells or cells already owned by a DIFFERENT
        # net with '#'-style contention -- simplest safe rule: a cell
        # owned by net A and repainted for net B becomes a hard obstacle
        # ('#') unless B == A, so no two different nets' obstacle regions
        # silently overwrite each other's ownership.
        free = region == ""
        same = region == net
        other = ~free & ~same
        region[free] = net
        region[other] = "#"

    def _paint_via_rect(self, cx0, cy0, cx1, cy1, net):
        cx0 = max(0, cx0)
        cy0 = max(0, cy0)
        cx1 = min(NX - 1, cx1)
        cy1 = min(NY - 1, cy1)
        if cx1 < cx0 or cy1 < cy0:
            return
        region = self.via_owner[cy0:cy1 + 1, cx0:cx1 + 1]
        free = region == ""
        same = region == net
        other = ~free & ~same
        region[free] = net
        region[other] = "#"

    def _build_edge_obstacles(self):
        m = int(EDGE_MARGIN / GRID)
        for layer in (0, 1):
            g = self.owner[layer]
            g[:m, :] = "#"
            g[-m:, :] = "#"
            g[:, :m] = "#"
            g[:, -m:] = "#"

    def _build_pad_obstacles(self):
        # Two-phase paint: a pad's own exact copper (the "core", no
        # clearance inflation) must NEVER become unreachable for its own
        # net, even when a neighboring different-net pad's clearance halo
        # overlaps it -- at 0.4-0.5mm pitch (CM4 connector, BQ25792,
        # EC25), inflated halos from adjacent pads routinely overlap the
        # next pad's own core. Painting halos first and cores last (cores
        # always win, unconditionally) fixed a real bug this script's
        # first version had: it could mark a pad's OWN goal cell '#'
        # (permanently blocked) purely from a neighbor's halo overlap,
        # making that pad unroutable to no matter what.
        pad_list = []
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                pad_list.append(pad)

        # Phase 1: clearance halos (conflict-tolerant, as before).
        for pad in pad_list:
            net = pad.GetNetname()
            pos = pad.GetPosition()
            x, y = mm(pos.x), mm(pos.y)
            # pad.GetSize() is in the PAD's own local frame, before its
            # rotation is applied -- for a 90/270-degree-rotated pad
            # (common: many small SOIC/VSSOP/SOT parts on this board are
            # placed sideways), that local (w, h) is actually (h, w) in
            # real board X/Y. Using GetSize() directly here was a real
            # bug: it painted every rotated pad's clearance halo with
            # its width/height swapped, which both under- and
            # over-blocked space around it depending on direction --
            # found by tracing why U1 pin 6/7 (a rotated VSSOP-8) showed
            # up in this obstacle grid as apparently overlapping,
            # despite real DRC never flagging a real short there.
            # GetBoundingBox() already accounts for rotation correctly.
            bbox = pad.GetBoundingBox()
            w, h = mm(bbox.GetWidth()), mm(bbox.GetHeight())
            # 0.3mm (up from the netclass's bare 0.2mm copper clearance)
            # -- real DRC additionally flagged several genuine
            # [solder_mask_bridge] violations (a track passing close
            # enough to a different-net pad for their solder mask
            # apertures to merge) that plain copper-to-copper clearance
            # doesn't account for. Rather than model KiCad's separate
            # solder-mask-web constraint exactly, this router keeps an
            # extra 0.1mm of margin around every pad, which empirically
            # keeps new routes clear of that constraint too.
            # Real-rule-aware (board_rules.ClearanceModel), not a second
            # hardcoded guess: inside J1/J2's real courtyard this is
            # 0.15mm and inside U3's 0.05mm (the board's own .kicad_dru
            # rules), used exactly as-is there since real DRC on actual
            # test traces confirmed zero extra margin is needed. Outside
            # any special courtyard, keep this router's existing 0.1mm
            # solder-mask-bridge margin on top of the 0.2mm Default
            # netclass clearance -- unrelated to J1/J2 and already
            # validated by this project's real DRC history.
            base = self.clearance_model.at_point(x, y)
            if net == "":
                clearance = min(base, 0.15)
            elif base < 0.2:
                clearance = base
            else:
                clearance = base + 0.1
            hw, hh = w / 2 + clearance, h / 2 + clearance
            cx0, cy0 = to_cell(x - hw, y - hh)
            cx1, cy1 = to_cell(x + hw, y + hh)
            layers = []
            if pad.IsOnLayer(pcbnew.F_Cu):
                layers.append(0)
            if pad.IsOnLayer(pcbnew.B_Cu):
                layers.append(1)
            key = net if net else "#"
            for layer in layers:
                self._paint_rect(layer, cx0, cy0, cx1, cy1, key)
            if pad.HasHole():
                drill = pad.GetDrillSize()
                hr = max(mm(drill.x), mm(drill.y)) / 2
                vcx0, vcy0 = to_cell(x - hr - HOLE_TO_HOLE, y - hr - HOLE_TO_HOLE)
                vcx1, vcy1 = to_cell(x + hr + HOLE_TO_HOLE, y + hr + HOLE_TO_HOLE)
                self._paint_via_rect(vcx0, vcy0, vcx1, vcy1, key)

        # Phase 2: exact pad cores, unconditionally owned by their own
        # net -- always applied last, always wins.
        for pad in pad_list:
            net = pad.GetNetname()
            if not net:
                continue  # an unconnected pad has no "own net" to protect
            pos = pad.GetPosition()
            x, y = mm(pos.x), mm(pos.y)
            bbox = pad.GetBoundingBox()  # rotation-correct, see Phase 1's comment
            w, h = mm(bbox.GetWidth()), mm(bbox.GetHeight())
            cx0, cy0 = to_cell(x - w / 2, y - h / 2)
            cx1, cy1 = to_cell(x + w / 2, y + h / 2)
            cx0, cy0 = max(0, cx0), max(0, cy0)
            cx1, cy1 = min(NX - 1, cx1), min(NY - 1, cy1)
            if cx1 < cx0 or cy1 < cy0:
                continue
            for layer in (0, 1):
                if layer == 0 and not pad.IsOnLayer(pcbnew.F_Cu):
                    continue
                if layer == 1 and not pad.IsOnLayer(pcbnew.B_Cu):
                    continue
                self.owner[layer][cy0:cy1 + 1, cx0:cx1 + 1] = net

    def _build_existing_track_obstacles(self):
        for t in self.board.GetTracks():
            if t.GetClass() != "PCB_TRACK":
                continue
            net = t.GetNetname()
            layer = 0 if t.GetLayer() == pcbnew.F_Cu else (1 if t.GetLayer() == pcbnew.B_Cu else None)
            s, e = t.GetStart(), t.GetEnd()
            x1, y1, x2, y2 = mm(s.x), mm(s.y), mm(e.x), mm(e.y)
            width = mm(t.GetWidth())
            key = net if net else "#"
            # A real bug this pass found (and already fixed the same
            # way in local_fine_route.py and route_inner_layer.py): a
            # through-hole via's copper physically touches EVERY layer,
            # including In1.Cu/In2.Cu this router never routes on --
            # real DRC caught a new via colliding with an inner-layer
            # track this router had zero visibility into. Every track,
            # on every layer, is painted into via_owner (hole-clearance
            # grid) so via placement respects it, even though only
            # F.Cu/B.Cu tracks are painted as ROUTING obstacles (below).
            length = math.hypot(x2 - x1, y2 - y1)
            steps = max(1, int(length / (GRID / 2)))
            for i in range(steps + 1):
                tt = i / steps
                x = x1 + (x2 - x1) * tt
                y = y1 + (y2 - y1) * tt
                half = width / 2 + HOLE_TO_HOLE
                vcx0, vcy0 = to_cell(x - half, y - half)
                vcx1, vcy1 = to_cell(x + half, y + half)
                self._paint_via_rect(vcx0, vcy0, vcx1, vcy1, key)
            if layer is None:
                continue
            self._paint_line(layer, x1, y1, x2, y2, width / 2, key)

    def _paint_line(self, layer, x1, y1, x2, y2, half_width, net):
        # Rasterize a thick line by stepping along it in ~half-cell
        # increments and painting a small square at each step -- simple
        # and robust for the traces this project uses (all axis-aligned
        # or 45-degree from the polyline routers). Clearance is looked
        # up per sampled point via ClearanceModel (real .kicad_dru
        # rules), not a flat constant, so a track crossing in/out of
        # J1/J2/U3's real courtyard gets the correct margin along its
        # own length.
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        steps = max(1, int(length / (GRID / 2)))
        for i in range(steps + 1):
            t = i / steps
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            base = self.clearance_model.at_point(x, y)
            clearance = base if base < 0.2 else base + 0.1
            half = half_width + clearance
            cx0, cy0 = to_cell(x - half, y - half)
            cx1, cy1 = to_cell(x + half, y + half)
            self._paint_rect(layer, cx0, cy0, cx1, cy1, net)

    def _build_existing_via_obstacles(self):
        for t in self.board.GetTracks():
            if t.GetClass() != "PCB_VIA":
                continue
            net = t.GetNetname()
            p = t.GetPosition()
            x, y = mm(p.x), mm(p.y)
            r = mm(t.GetWidth()) / 2
            key = net if net else "#"
            base = self.clearance_model.at_point(x, y)
            via_clearance = base if base < 0.2 else base + 0.1
            cx0, cy0 = to_cell(x - r - via_clearance, y - r - via_clearance)
            cx1, cy1 = to_cell(x + r + via_clearance, y + r + via_clearance)
            self._paint_rect(0, cx0, cy0, cx1, cy1, key)
            self._paint_rect(1, cx0, cy0, cx1, cy1, key)
            hr = VIA_DRILL / 2
            vcx0, vcy0 = to_cell(x - hr - HOLE_TO_HOLE, y - hr - HOLE_TO_HOLE)
            vcx1, vcy1 = to_cell(x + hr + HOLE_TO_HOLE, y + hr + HOLE_TO_HOLE)
            self._paint_via_rect(vcx0, vcy0, vcx1, vcy1, key)

    def pad(self, ref, pin):
        fp = self.fp_by_ref[ref]
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p
        raise KeyError(f"{ref}.{pin} not found")

    def _blocked_grid(self, layer, net, radius, source="owner"):
        """Precompute, ONCE per (layer, net, radius) combination rather
        than at every A* step, a boolean grid: True where a track/via of
        this radius centered there would violate clearance against some
        OTHER net's copper. This is the real Minkowski-sum collision
        check for the route's own half-width (half_mine + half_theirs +
        clearance, since the obstacle grid already encodes
        half_theirs + clearance) -- checking a live neighborhood at every
        single A* expansion step (this script's second version) was
        correct but far too slow (a full board maze run did not finish
        in 9+ minutes); precomputing the whole dilated grid once with
        scipy and then doing O(1) lookups during search restored the
        original speed while keeping the real clearance fix."""
        key = (layer, net, radius, source)
        cached = self._dilate_cache.get(key)
        if cached is not None:
            return cached
        grid = self.owner[layer] if source == "owner" else self.via_owner
        if source == "via_hole":
            # Hole-to-hole drill spacing is a physical manufacturing
            # constraint, independent of net -- two SAME-net via holes
            # drilled too close together are exactly as unmanufacturable
            # as two different-net ones. Exempting same-net cells here
            # (as the copper-clearance check correctly does) was a real
            # bug: multiple vias for a wide-fanout net (e.g. +3V3, with
            # ~14 pins and many MST edges each possibly needing their own
            # via) could land right on top of each other. Real DRC caught
            # it as [holes_co_located]/[hole_near_hole] violations.
            occupied = grid != ""
        else:
            occupied = (grid != "") & (grid != net)
        if radius == 0:
            blocked = occupied
        else:
            size = 2 * radius + 1
            blocked = binary_dilation(occupied, structure=np.ones((size, size), dtype=bool))
        self._dilate_cache[key] = blocked
        return blocked

    def _cell_passable(self, layer, cx, cy, net, radius=0):
        if cx < 0 or cx >= NX or cy < 0 or cy >= NY:
            return False
        return not self._blocked_grid(layer, net, radius)[cy, cx]

    def _via_ok(self, cx, cy, net, radius=0):
        if cx < 0 or cx >= NX or cy < 0 or cy >= NY:
            return False
        return not self._blocked_grid(0, net, radius, source="via_hole")[cy, cx]

    NEIGHBORS = [
        (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
        (1, 1, 1.41421), (1, -1, 1.41421), (-1, 1, 1.41421), (-1, -1, 1.41421),
    ]

    # Progressively thinner retry widths, tried in order when the default
    # width can't find any clearance-safe path -- all real, standard,
    # fab-manufacturable trace widths (most fabs support down to
    # ~3-3.5mil / 0.075-0.09mm), never a clearance-rule violation. Only
    # used for signal nets (see main()'s allow_thinning=False for power
    # nets, which must keep their current-carrying width).
    THIN_RETRY_WIDTHS = (0.2, 0.15, 0.1)

    def route(self, ref_a, pin_a, ref_b, pin_b, width_mm, label, allow_thinning=True):
        pa, pb = self.pad(ref_a, pin_a), self.pad(ref_b, pin_b)
        net_a, net_b = pa.GetNetname(), pb.GetNetname()
        if net_a != net_b:
            self.results.append((label, "FAIL", "net mismatch"))
            return False
        net = net_a
        ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
        bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
        a_layers = [l for l in (0, 1) if pa.IsOnLayer(pcbnew.F_Cu if l == 0 else pcbnew.B_Cu)]
        b_layers = [l for l in (0, 1) if pb.IsOnLayer(pcbnew.F_Cu if l == 0 else pcbnew.B_Cu)]
        start = to_cell(ax, ay)
        goal = to_cell(bx, by)

        widths_to_try = [width_mm]
        if allow_thinning:
            widths_to_try += [w for w in self.THIN_RETRY_WIDTHS if w < width_mm]

        for w in widths_to_try:
            # ceil, not round-to-nearest -- see VIA_COPPER_RADIUS_CELLS's
            # comment for why a downward-rounded radius is a real
            # under-coverage bug, not a harmless approximation.
            radius = max(0, math.ceil((w / 2) / GRID))
            path = self._astar(start, goal, net, a_layers, b_layers, radius)
            if path is not None:
                self._commit(path, w, net)
                note = f"{w}mm, {len(path)} cells"
                if w != width_mm:
                    note += f" (thinned from {width_mm}mm)"
                self.results.append((label, "OK", note))
                return True
        self.results.append((label, "FAIL", "no path found at any width"))
        return False

    def _astar(self, start, goal, net, start_layers, goal_layers, radius=0):
        # State: (cx, cy, layer). Start/goal may be reachable on either
        # layer their pad exists on (THT pads: both).
        def h(cx, cy):
            return ((cx - goal[0]) ** 2 + (cy - goal[1]) ** 2) ** 0.5

        openq = []
        best = {}
        for layer in start_layers:
            s = (start[0], start[1], layer)
            best[s] = 0
            heapq.heappush(openq, (h(start[0], start[1]), s, None))
        came_from = {}
        goal_set = {(goal[0], goal[1], layer) for layer in goal_layers}

        expansions = 0
        max_expansions = 350000
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
            for dx, dy, cost in self.NEIGHBORS:
                nx, ny = cx + dx, cy + dy
                ns = (nx, ny, layer)
                # Every cell, including the goal, is checked at the
                # route's real full radius -- an earlier version of this
                # script exempted the exact goal cell to radius 0
                # (reasoning: "a track merging into its own pad doesn't
                # need clearance from itself"), but that exemption also
                # silently waived clearance against OTHER, foreign pads
                # that happen to sit right next to the goal (e.g. a
                # tightly-spaced header) -- real DRC caught it as actual
                # 0.0mm Pad-Track clearance violations at several
                # connector goals. A pad's own core is already
                # unconditionally owned by its net (see
                # _build_pad_obstacles), so same-net "self-clearance" was
                # never the problem this needed to solve; genuinely
                # too-tight destinations are instead handled by retrying
                # the whole route at a thinner width (see route()).
                if not self._cell_passable(layer, nx, ny, net, radius):
                    continue
                ng = g + cost
                if ns not in best or ng < best[ns]:
                    best[ns] = ng
                    heapq.heappush(openq, (ng + h(nx, ny), ns, cur))
            # Via transition: switch layer at the same (cx,cy) if both
            # layers are clear (checked at the VIA's own radius, not the
            # track's -- a via's 0.6mm copper pad is wider than most
            # signal traces) and the hole-to-hole rule is met.
            other = 1 - layer
            if (self._cell_passable(layer, cx, cy, net, VIA_COPPER_RADIUS_CELLS)
                    and self._cell_passable(other, cx, cy, net, VIA_COPPER_RADIUS_CELLS)
                    and self._via_ok(cx, cy, net, VIA_HOLE_RADIUS_CELLS)):
                ns = (cx, cy, other)
                ng = g + VIA_COST
                if ns not in best or ng < best[ns]:
                    best[ns] = ng
                    heapq.heappush(openq, (ng + h(cx, cy), ns, cur))

        if found is None:
            return None
        # Reconstruct path
        path = []
        node = found
        while node is not None:
            path.append(node)
            node = came_from[node]
        path.reverse()
        return path

    def _simplify(self, path):
        """Collapse consecutive same-direction, same-layer steps into a
        single segment; keep a point at every via/direction change."""
        if not path:
            return []
        pts = [path[0]]
        for i in range(1, len(path) - 1):
            px, py, pl = path[i - 1]
            cx, cy, cl = path[i]
            nx_, ny_, nl = path[i + 1]
            if pl != cl:
                pts.append(path[i])
                continue
            if cl != nl:
                pts.append(path[i])
                continue
            d1 = (cx - px, cy - py)
            d2 = (nx_ - cx, ny_ - cy)
            if d1 != d2:
                pts.append(path[i])
        pts.append(path[-1])
        return pts

    def _commit(self, path, width_mm, net):
        pts = self._simplify(path)
        net_obj = self.net_objs[net]
        for i in range(len(pts) - 1):
            (cx1, cy1, l1), (cx2, cy2, l2) = pts[i], pts[i + 1]
            x1, y1 = to_mm(cx1, cy1)
            x2, y2 = to_mm(cx2, cy2)
            if l1 != l2:
                # via at (cx1,cy1)
                via = pcbnew.PCB_VIA(self.board)
                via.SetPosition(pcbnew.VECTOR2I(int(x1 * 1e6), int(y1 * 1e6)))
                via.SetWidth(pcbnew.FromMM(VIA_DIA))
                via.SetDrill(pcbnew.FromMM(VIA_DRILL))
                via.SetNet(net_obj)
                via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                self.board.Add(via)
                # Paint the via's own copper (half + clearance margin) and
                # its hole-to-hole keepout, matching how existing vias
                # were painted -- so a later route sees this via with the
                # same real margin, not an arbitrary fixed radius.
                cu_r = VIA_COPPER_RADIUS_CELLS + 1  # +1 cell (~0.2mm) clearance margin
                self._paint_rect(0, cx1 - cu_r, cy1 - cu_r, cx1 + cu_r, cy1 + cu_r, net)
                self._paint_rect(1, cx1 - cu_r, cy1 - cu_r, cx1 + cu_r, cy1 + cu_r, net)
                self._paint_via_rect(cx1 - VIA_HOLE_RADIUS_CELLS, cy1 - VIA_HOLE_RADIUS_CELLS,
                                      cx1 + VIA_HOLE_RADIUS_CELLS, cy1 + VIA_HOLE_RADIUS_CELLS, net)
                continue
            if (cx1, cy1) == (cx2, cy2):
                continue
            layer = pcbnew.F_Cu if l1 == 0 else pcbnew.B_Cu
            track = pcbnew.PCB_TRACK(self.board)
            track.SetStart(pcbnew.VECTOR2I(int(x1 * 1e6), int(y1 * 1e6)))
            track.SetEnd(pcbnew.VECTOR2I(int(x2 * 1e6), int(y2 * 1e6)))
            track.SetWidth(pcbnew.FromMM(width_mm))
            track.SetLayer(layer)
            track.SetNet(net_obj)
            self.board.Add(track)
            self._paint_line(l1, x1, y1, x2, y2, width_mm / 2, net)

        # The owner/via_owner grids just changed -- every cached dilated
        # "blocked" grid is now potentially stale (a later route could
        # otherwise be routed as if this new copper didn't exist, a real
        # short-circuit risk). Invalidate the whole cache; the next
        # route() call rebuilds only the (layer, net, radius)
        # combinations it actually needs.
        self._dilate_cache = {}


def _mst_edges(points):
    n = len(points)
    if n < 2:
        return []
    in_tree = [False] * n
    in_tree[0] = True
    edges = []
    dist = lambda i, j: ((points[i][2] - points[j][2]) ** 2 + (points[i][3] - points[j][3]) ** 2) ** 0.5
    for _ in range(n - 1):
        best = None
        for i in range(n):
            if not in_tree[i]:
                continue
            for j in range(n):
                if in_tree[j]:
                    continue
                d = dist(i, j)
                if best is None or d < best[0]:
                    best = (d, i, j)
        if best is None:
            break
        _, i, j = best
        in_tree[j] = True
        edges.append((i, j))
    return edges


def main():
    import time
    t0 = time.time()
    board = pcbnew.LoadBoard(PCB_PATH)
    r = MazeRouter(board)
    print(f"Obstacle grid built in {time.time()-t0:.1f}s ({NX}x{NY} cells x2 layers)")

    total_ok, total_fail = 0, 0
    per_net = []
    for net_name, conns in NETS.items():
        if net_name == "GND":
            continue
        pts = []
        for ref, pin in conns:
            try:
                pad = r.pad(ref, pin)
            except KeyError:
                continue
            pts.append((ref, pin, mm(pad.GetPosition().x), mm(pad.GetPosition().y)))
        if len(pts) < 2:
            continue
        default_width = width_for(net_name)
        # Power nets keep their full current-carrying width, always (no
        # thinning -- see route()'s allow_thinning). Signal nets may
        # retry at a thinner, still-real, still-DRC-checked width if the
        # default can't find a clearance-safe path: at J1/J2's real
        # 0.4mm pitch (0.25mm-wide pads -> only 0.15mm gap between
        # adjacent pads) and similar fine-pitch corners, a 0.3mm trace
        # genuinely cannot fit through some approaches at all --
        # confirmed directly by exhausting the search at full width.
        # This lets the router discover which destinations need thinning
        # by trying, rather than relying on a hand-maintained list of
        # "known tight" footprints that would silently miss new ones.
        allow_thinning = net_name not in _POWER_WIDTHS
        ok, fail = 0, 0
        for i, j in _mst_edges(pts):
            ref_a, pin_a, _, _ = pts[i]
            ref_b, pin_b, _, _ = pts[j]
            label = f"{net_name}: {ref_a}.{pin_a}-{ref_b}.{pin_b}"
            if r.route(ref_a, pin_a, ref_b, pin_b, default_width, label, allow_thinning=allow_thinning):
                ok += 1
            else:
                fail += 1
        total_ok += ok
        total_fail += fail
        if ok or fail:
            per_net.append((net_name, ok, fail))

    print(f"\nRouted OK: {total_ok}   Failed: {total_fail}   ({time.time()-t0:.1f}s total)")
    for net_name, ok, fail in sorted(per_net, key=lambda t: -(t[1] + t[2])):
        print(f"  {net_name:20s} {ok}/{ok+fail}")
    print("\nFailed edges:")
    for label, status, info in r.results:
        if status == "FAIL":
            print(f"  FAIL: {label} ({info})")

    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    print(f"\nSaved {PCB_PATH}")


if __name__ == "__main__":
    main()
