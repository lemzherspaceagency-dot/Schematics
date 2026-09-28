#!/usr/bin/env python3
"""
3-layer (F.Cu / In1.Cu / B.Cu) fine-grid router for the pairs that
remain genuinely unroutable with F.Cu+B.Cu alone.

Root-cause finding (this session, diagnostic pass): the ~60 remaining
unrouted pairs are dominated by CM4 J1 GPIO fanout to distant peripheral
connectors (needing to escape J1's dense 100-pin 0.4mm-pitch field),
gate-driver/bootstrap connections with genuinely sub-0.1mm real
clearance next to their own IC's neighboring pins, and USB nets. A
2-layer (F.Cu/B.Cu) router -- even fine-grid, even via-capable, even
with a 130mm search window -- found 0/60 of these routable: real
placement density leaves no F.Cu-or-B.Cu escape corridor for many of
them.

This board's stackup has 4 real copper layers, but this project's
routers so far only ever used 2 (F.Cu/B.Cu) for SIGNAL routing, leaving
In1.Cu and In2.Cu entirely as continuous GND planes. Adding an inner
signal layer for local escape routing near dense connectors is standard
real PCB practice (blind/buried or even a simple through-via breakout),
and does not require any stackup/zone redefinition here: this project's
zone-refill step (refill_zones.py) already automatically carves the GND
pour around whatever new copper exists on a layer at fill time -- the
same mechanism already relied on for F.Cu/B.Cu throughout this session.
This script keeps In2.Cu untouched (one continuous, uninterrupted
reference plane stays adjacent to every signal layer at all times) and
opens In1.Cu as a third routable layer, only for the specific pairs nothing
else could resolve.

A via placed by this script is a normal through-hole via (as used
everywhere else on this board), which mechanically connects all 4
copper layers at that (x,y) regardless of which 2 the router's search
state names -- consistent with the rest of this project's via model.

Usage: python3 route_inner_layer.py [drc_report.txt]
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

GRID = 0.05  # mm -- was 0.1mm; this pass found real cases (VBAT_BUS,
             # U6.14-U6.11: a straight 1.95mm hop with a real ~0.3-0.5mm
             # open pocket around it) where 0.1mm quantization produced
             # a false "no via/path fits" the same way this session
             # already found for the 0.2mm whole-board grid at J1 --
             # matching Phase 11's explicit finest-practical-grid
             # requirement. Window sizing below keeps this tractable for
             # the realistic window sizes this router actually uses.
CLEARANCE = 0.2  # this board's Default netclass clearance -- the real
# per-region floor. Every place below that painted a flat CLEARANCE now
# looks up the real per-point value via ClearanceModel instead (same
# bug this session already found and fixed in gen_routes_maze.py and
# local_fine_route.py: this router never applied the board's own real
# 0.15mm J1/J2 courtyard rule or 0.05mm U3 rule, always using the
# blanket 0.2mm Default value everywhere).
QUANT_MARGIN = GRID
MAX_WINDOW_MM = 115.0  # was 90, then 50, before that 130 at 0.1mm grid; at the
# finer 0.05mm grid a 130mm+margin window is ~30M cells across 3 layers
# -- impractical. But 50mm was quietly SKIPPING every candidate above it
# (main()'s `if span > MAX_WINDOW_MM: fail += 1; continue`) without ever
# attempting a search -- found via direct investigation of I2C0_SCL
# (52.2mm, the single shortest J1-corridor candidate at the time): it
# was never even tried. Directly timed real LocalWindow3L builds+searches
# up to 76.6mm span (UART3_RXD3) -- ~3-5s build, ~10s per width tried,
# ~30-35s total per net. Raised again to 115mm after directly testing
# GPIO_TERRA_A (111.2mm, the longest remaining candidate): build+search
# still ~35s even at a much wider-than-default 40mm margin (well beyond
# the router's own 25mm margin cap), and per-layer flood-fills from the
# J1 side showed 60,000+ open cells on EVERY modeled layer with the goal
# still unreached -- a real, thoroughly-checked "no path in this window"
# result, not a size artifact, consistent with route_j1_staged3l.py's
# earlier finding that the J1-J9 Terra corridor is a genuinely different,
# harder congestion problem. Raising the cap anyway so no candidate is
# ever silently skipped without a real attempt -- the cost is bounded
# (~35s/candidate) and this router's job is to try, not to pre-judge.
VIA_DIA = 0.6
VIA_DRILL = 0.4
HOLE_TO_HOLE = 0.26 + 2 * QUANT_MARGIN  # +1 cell wasn't quite enough --
# repeated real DRC runs kept finding the SAME BATT_F via 0.02-0.05mm
# short near U3's dense WQFN corner; +2 cells forces the search to
# prefer a genuinely safer spot instead of the same marginal one.
VIA_COPPER_RADIUS_CELLS = max(1, math.ceil((VIA_DIA / 2) / GRID))
VIA_HOLE_RADIUS_CELLS = max(1, math.ceil((HOLE_TO_HOLE + VIA_DRILL / 2) / GRID))
VIA_COST = 30
TRY_WIDTHS = (0.25, 0.2, 0.15, 0.1)  # 0.1mm last-resort added: real
# fab-manufacturable (most prototype fabs support 3-4mil/0.075-0.1mm),
# and consistent with the same principle already applied to power nets'
# "necking" fallback -- a thin-but-valid trace beats an unrouted net.
_POWER_NETS = {
    "+3V3", "+5V0", "VBAT_BUS", "MODEM_VBAT", "BATT_F", "P1_F",
    "VBAT_MAIN_OUT", "VBAT_P1_OUT", "5V0_SW", "5V0_PRE", "DOCK_PWR_RAW",
    "DOCK_F", "TERRA_BATT_RAW", "TERRA_PWR", "MODEM_5V0_SW",
}
_POWER_MIN_WIDTH = 0.3
# Last-resort "necking" width for power nets whose full-width path is
# genuinely blocked at a tight pin escape (confirmed via direct pad-
# neighbor probing, e.g. +3V3/U7.15 has 0 free F.Cu cells at radius>=2
# but 5 free cells at radius=1). Still >= common fab min trace width.
_POWER_NECK_WIDTH = 0.1

# Grid layer index -> real KiCad layer. In2.Cu (index 2 in the stackup)
# is deliberately excluded -- kept as one continuous, unbroken GND plane.
GRID_LAYERS = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.B_Cu)


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


class LocalWindow3L:
    def __init__(self, board, net, x0, y0, x1, y1, clearance_model=None, exclude_nets=frozenset()):
        # A real failure this pass found: for two pads that share (or
        # nearly share) an X or Y coordinate, a mere 1mm margin gives
        # the router NO lateral room to detour around an obstacle
        # sitting directly on the straight line between them (found via
        # VBAT_BUS: U6.14-U6.11, a straight vertical 1.95mm hop blocked
        # by a real obstacle at the midpoint on every layer within a
        # ~0.3mm-wide corridor -- a wider window trivially routes around
        # it). A margin proportional to span, with a real floor, gives
        # actual room to detour without blowing up window size for
        # genuinely long routes.
        # Real failure this pass found: VBAT_BUS (U4.7-C3.1, 19.6mm span)
        # had its entire direct corridor -- across all 3 modeled layers,
        # at every X between the two pads -- filled by two wide power
        # nets (5V0_PRE/5V0_SW) for the full height of a 3mm-margin
        # window. A 10mm margin found a real path (531 cells, works down
        # to 0.15mm) on the first try. Raised the floor and the
        # span-scaled term; the 25mm cap keeps very long spans tractable
        # (performance-tested directly: a ~100mm-span window this size
        # still builds/searches in single-digit seconds).
        margin = max(10.0, min(25.0, 0.5 * max(abs(x1 - x0), abs(y1 - y0))))
        self.x0 = x0 - margin
        self.y0 = y0 - margin
        self.x1 = x1 + margin
        self.y1 = y1 + margin
        self.net = net
        self.clearance_model = clearance_model
        self.exclude_nets = exclude_nets
        # Diagnostic-only capability: treats the named net(s)' own copper
        # as if it didn't exist (not painted as an obstacle at all), so a
        # "would net Y route if net X's copper were briefly absent"
        # question can be answered by direct simulation instead of
        # bounding-box-overlap guessing. Empty by default -- zero
        # behavior change for every existing caller. Never used to
        # actually place copper; a real rip-up-and-verify-with-DRC cycle
        # is still required before trusting any such result for real.
        self.nx = int((self.x1 - self.x0) / GRID) + 1
        self.ny = int((self.y1 - self.y0) / GRID) + 1
        self.owner = {i: np.full((self.ny, self.nx), "", dtype=object) for i in range(len(GRID_LAYERS))}
        self.via_owner = np.full((self.ny, self.nx), "", dtype=object)
        self._dilate_cache = {}
        self._build(board)

    def _clearance_at(self, x, y):
        base = CLEARANCE if self.clearance_model is None else self.clearance_model.at_point(x, y)
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
                if pad.GetNetname() in self.exclude_nets:
                    continue
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
                for layer, kicad_layer in enumerate(GRID_LAYERS):
                    if z.GetLayerSet().Contains(kicad_layer):
                        self._paint_rect(layer, cx0, cy0, cx1, cy1, "#")

        # Phase 1: pad clearance halos. Only F.Cu/B.Cu pads exist as SMD;
        # any THT pad (has a hole) blocks all 3 grid layers since a
        # drilled hole physically removes copper/clearance on every
        # layer it passes through.
        for pad in pad_list:
            net = pad.GetNetname()
            p = pad.GetPosition()
            x, y = mm(p.x), mm(p.y)
            sz = pad.GetBoundingBox()
            w, h = mm(sz.GetWidth()), mm(sz.GetHeight())
            clearance = self._clearance_at(x, y)
            hw, hh = w / 2 + clearance, h / 2 + clearance
            cx0, cy0 = self.to_cell(x - hw, y - hh)
            cx1, cy1 = self.to_cell(x + hw, y + hh)
            key = net if net else "#"
            has_hole = pad.HasHole()
            for layer, kicad_layer in enumerate(GRID_LAYERS):
                if has_hole or pad.IsOnLayer(kicad_layer):
                    self._paint_rect(layer, cx0, cy0, cx1, cy1, key)
            if has_hole:
                drill = pad.GetDrillSize()
                hr = max(mm(drill.x), mm(drill.y)) / 2
                vcx0, vcy0 = self.to_cell(x - hr - HOLE_TO_HOLE, y - hr - HOLE_TO_HOLE)
                vcx1, vcy1 = self.to_cell(x + hr + HOLE_TO_HOLE, y + hr + HOLE_TO_HOLE)
                self._paint_via_rect(vcx0, vcy0, vcx1, vcy1, key)
            # NOTE: an earlier version of this pass also painted a
            # via_owner halo for holeless SMD pads (real DRC's board-wide
            # hole clearance applies to any copper a via's hole comes
            # near, not only other holes). Reverted (twice now -- even
            # scoped to just fine-pitch-courtyard pads, e.g. only U3, it
            # still blocked via placement almost everywhere inside a
            # densely populated QFN courtyard, including the specific
            # via BTST1's own route needed -- confirmed directly: BTST1
            # found a path with this scoped halo OFF and NO path with it
            # ON, in an otherwise-identical isolated probe). That narrow
            # case is instead left to real DRC + ripup_violations.py's
            # existing backstop, consistent with this project's
            # established discipline (custom obstacle models are a
            # heuristic; real DRC is the actual authority).

        # Phase 2: pad cores always win.
        for pad in pad_list:
            net = pad.GetNetname()
            if not net:
                continue
            p = pad.GetPosition()
            x, y = mm(p.x), mm(p.y)
            sz = pad.GetBoundingBox()
            w, h = mm(sz.GetWidth()), mm(sz.GetHeight())
            cx0, cy0 = self.to_cell(x - w / 2, y - h / 2)
            cx1, cy1 = self.to_cell(x + w / 2, y + h / 2)
            cx0, cy0 = max(0, cx0), max(0, cy0)
            cx1, cy1 = min(self.nx - 1, cx1), min(self.ny - 1, cy1)
            if cx1 < cx0 or cy1 < cy0:
                continue
            has_hole = pad.HasHole()
            for layer, kicad_layer in enumerate(GRID_LAYERS):
                if has_hole or pad.IsOnLayer(kicad_layer):
                    self.owner[layer][cy0:cy1 + 1, cx0:cx1 + 1] = net

        for t in board.GetTracks():
            net = t.GetNetname()
            if net in self.exclude_nets:
                continue
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
                for layer in range(len(GRID_LAYERS)):
                    self._paint_rect(layer, cx0, cy0, cx1, cy1, key)
                hr = VIA_DRILL / 2
                vcx0, vcy0 = self.to_cell(x - hr - HOLE_TO_HOLE, y - hr - HOLE_TO_HOLE)
                vcx1, vcy1 = self.to_cell(x + hr + HOLE_TO_HOLE, y + hr + HOLE_TO_HOLE)
                self._paint_via_rect(vcx0, vcy0, vcx1, vcy1, key)
                continue
            layer = None
            for i, kl in enumerate(GRID_LAYERS):
                if t.GetLayer() == kl:
                    layer = i
                    break
            if layer is None:
                continue
            s, e = t.GetStart(), t.GetEnd()
            x1, y1, x2, y2 = mm(s.x), mm(s.y), mm(e.x), mm(e.y)
            seg_x0, seg_x1 = min(x1, x2), max(x1, x2)
            seg_y0, seg_y1 = min(y1, y2), max(y1, y2)
            pad3 = 3
            if (seg_x1 < self.x0 - pad3 or seg_x0 > self.x1 + pad3
                    or seg_y1 < self.y0 - pad3 or seg_y0 > self.y1 + pad3):
                continue
            half_width = mm(t.GetWidth()) / 2
            length = math.hypot(x2 - x1, y2 - y1)
            steps = max(1, int(length / (GRID / 2)))
            # Real DRC's courtyard-condition rules (e.g. BQ25792_fine_pitch_
            # clearance) apply to a whole track OBJECT if any part of it
            # touches the courtyard, not point-by-point along its length.
            # Sampling clearance per-point creates a false "clearance
            # cliff" right where a fine-pitch escape trace crosses the
            # courtyard boundary, which incorrectly re-blocks a neighboring
            # pin still inside the courtyard (found via BTST1/U3.4: a
            # VBUS_IN escape trace exiting U3's courtyard reverted to the
            # 0.2mm default clearance for the segment's outer half, and
            # that wider halo reached back in and walled off BTST1's pad,
            # even though BTST1's own copper is squarely inside the same
            # courtyard and would get the relaxed 0.05mm rule against it
            # under real DRC). Use the tightest (smallest) clearance found
            # anywhere along the segment for the whole halo -- consistent
            # with "if any part is inside the courtyard, the relaxed rule
            # can apply", and still just a heuristic double-checked by
            # real DRC afterward.
            seg_clearance = min(
                self._clearance_at(x1 + (x2 - x1) * (i / steps), y1 + (y2 - y1) * (i / steps))
                for i in range(steps + 1)
            )
            for i in range(steps + 1):
                tt = i / steps
                x = x1 + (x2 - x1) * tt
                y = y1 + (y2 - y1) * tt
                half = half_width + seg_clearance
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

    def _via_ok(self, cx, cy, hole_radius=None):
        if cx < 0 or cx >= self.nx or cy < 0 or cy >= self.ny:
            return False
        if hole_radius is None:
            hole_radius = VIA_HOLE_RADIUS_CELLS
        return not self._blocked(0, hole_radius, source="via_hole")[cy, cx]

    def forbid_via_near(self, x_mm, y_mm, radius_mm=0.35):
        """Poisons a real-world point (and a radius around it) so no via
        can be placed there, without touching this net's/other nets'
        track obstacle model at all. For surgically fixing the single
        most common recurring failure this router hits: a via landing
        marginally too close (by 0.02-0.05mm) to a holeless SMD pad's
        real min_hole_clearance requirement -- real DRC catches it,
        ripup_violations.py deletes the via (destroying the whole route,
        not just the marginal bit), and the net goes back to unconnected.
        Blacklisting the exact violating spot and re-searching lets the
        A* pick a genuinely clear via location instead of losing the
        route outright."""
        cx0, cy0 = self.to_cell(x_mm - radius_mm, y_mm - radius_mm)
        cx1, cy1 = self.to_cell(x_mm + radius_mm, y_mm + radius_mm)
        self._paint_via_rect(cx0, cy0, cx1, cy1, "#")
        self._dilate_cache.clear()

    def astar(self, start_xy, start_layers, goal_xy, goal_layers, radius,
              via_copper_radius=None, via_hole_radius=None):
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

        # Real bug found this pass: a flat 600,000-expansion cap silently
        # returned "no path" for nets whose window happens to span nearly
        # the whole board (e.g. J1-to-J9 Terra corridor nets, ~109mm
        # across a 125mm-tall board -> a 1567x3151-cell, 3-layer window,
        # ~14.8M reachable states). Direct proof: GPIO_TERRA_A (J1.27-
        # J9.14), previously classified DISTRIBUTED_CONGESTION by every
        # diagnostic this session, found a real 2305-node path once given
        # room to search -- but only after ~5.8M expansions, ~10x the old
        # cap. A flat larger constant would either waste time on small
        # windows that are genuinely unroutable (rare, since those fail
        # fast well under the old cap) or still be too small for the next
        # unusually large window. Scaling with the window's actual state
        # space count fixes both: small/typical windows keep the old
        # budget (no behavior change, no slowdown), only huge windows get
        # the room they actually need. Capped at 12M (~360s at the
        # measured ~33,000 expansions/sec) so a genuinely-impossible net
        # in a huge window still fails in bounded time rather than
        # searching forever.
        max_expansions = min(12_000_000, max(600_000, self.nx * self.ny * len(GRID_LAYERS)))
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
            # Via transition to ANY other grid layer. A real bug this
            # pass found via actual DRC: a through-hole via physically
            # has copper on EVERY layer it passes through (F.Cu through
            # B.Cu), not just the two named in this state transition --
            # a search going directly from In1.Cu to B.Cu never
            # "visited" F.Cu in its state graph, so the old check here
            # (only the FROM/TO layers) never verified the via's real
            # F.Cu copper against an existing F.Cu track, and real DRC
            # caught a 0.0mm collision. Every via must clear ALL modeled
            # layers, regardless of which two the transition names.
            # via_copper_radius/via_hole_radius let a caller try a
            # smaller-than-standard via (a real "microvia" escape
            # technique) for gaps that can't fit VIA_DIA/VIA_DRILL --
            # defaults preserve the exact prior behavior for every
            # existing caller.
            vcr = VIA_COPPER_RADIUS_CELLS if via_copper_radius is None else via_copper_radius
            all_clear = all(self._passable(l, cx, cy, vcr)
                             for l in range(len(GRID_LAYERS)))
            if all_clear and self._via_ok(cx, cy, hole_radius=via_hole_radius):
                for other in range(len(GRID_LAYERS)):
                    if other == layer:
                        continue
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


def build_cluster_pairs(board, order="nearest"):
    """Real-connectivity-based pair generation (board_clusters.py's
    pad-bounding-box-correct clusters) -- NOT the DRC-report text
    parser, which only sees pad-pair '[unconnected_items]' blocks and
    silently skips any block whose endpoint is a Track/PTH rather than
    a bare pad (a real, previously-found diagnostic gap in this
    project). order picks the candidate ordering strategy (see
    ORDER_STRATEGIES in route_global.py for the full list)."""
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

    rows = []
    for net_name, conns in NETS.items():
        if net_name == "GND":
            continue
        real_pads = [(ref, pin, find_pad(ref, pin)) for ref, pin in conns if find_pad(ref, pin)]
        if len(real_pads) < 2:
            continue
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
        rows.append((d, net_name, ref_a, pin_a, ref_b, pin_b))

    if order == "nearest":
        rows.sort(key=lambda r: r[0])
    elif order == "farthest":
        rows.sort(key=lambda r: -r[0])
    elif order == "connector_first":
        rows.sort(key=lambda r: (0 if r[2] in ("J1", "J2") or r[4] in ("J1", "J2") else 1, r[0]))
    elif order == "dense_ic_first":
        dense = {"U3", "U1", "U2", "U6", "U7", "U10"}
        rows.sort(key=lambda r: (0 if r[2] in dense or r[4] in dense else 1, r[0]))
    elif order == "shuffle":
        import random
        random.Random(42).shuffle(rows)
    elif order.startswith("priority:"):
        # A small fixed net-name list goes first (claims shared via/escape
        # slots before other nets sharing the same tight courtyard eat
        # them), nearest-first for the rest. Needed for BTST1: it found a
        # real path in isolation but repeatedly lost that exact slot to
        # BATT_F/DOCK_OK, which sort earlier under plain "nearest" (7.3mm/
        # 8.6mm vs BTST1's 12.1mm) despite no dependency between them.
        priority_nets = set(order.split(":", 1)[1].split(","))
        rows.sort(key=lambda r: (0 if r[1] in priority_nets else 1, r[0]))
    return [(net_name, ref_a, pin_a, ref_b, pin_b) for d, net_name, ref_a, pin_a, ref_b, pin_b in rows]


def main(order="nearest", save=True):
    board = pcbnew.LoadBoard(PCB_PATH)
    pairs = build_cluster_pairs(board, order=order)
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
    import time
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
        dist = math.hypot(bx - ax, by - ay)
        span = max(dist, 2.0)
        if span > MAX_WINDOW_MM:
            fail += 1
            continue

        widths = TRY_WIDTHS
        if net_name in _POWER_NETS:
            # Prefer full current-carrying width, but allow a thinner
            # "necked" fallback when the full width genuinely can't fit
            # at a tight pin escape (real PCB practice: neck down for a
            # short stretch rather than leaving the net unrouted).
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
            track.SetLayer(GRID_LAYERS[sl])
            track.SetNet(net_obj)
            board.Add(track)
        ok += 1
        if save and ok % 5 == 0:
            board.BuildConnectivity()
            pcbnew.SaveBoard(PCB_PATH, board)
            print(f"  (checkpoint saved, {ok} routed so far)", flush=True)

    print(f"Inner-layer routed: {ok}   Still failed: {fail}")
    board.BuildConnectivity()
    if save:
        pcbnew.SaveBoard(PCB_PATH, board)
        print(f"Saved {PCB_PATH}")
    return board, ok, fail


if __name__ == "__main__":
    order_arg = sys.argv[1] if len(sys.argv) > 1 else "nearest"
    main(order=order_arg)
