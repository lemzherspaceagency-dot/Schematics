#!/usr/bin/env python3
"""
Phase 3 (fabrication-readiness completion pass) extension to gen_routes.py.

gen_routes.py only ever targeted 59 hand-picked priority-1/2/3 connections
on a single copper layer (F.Cu). This script routes EVERY remaining net in
design_data.NETS (except GND, which the filled zone pours already satisfy
for all but a handful of pads -- see below), using the same never-trust-
your-own-router discipline as gen_routes.py: every candidate path is
checked against every foreign-net pad and every already-placed foreign-net
track/via before being committed, and nothing is committed on a "probably
fine" basis. Real KiCad DRC (python/run_drc.py) is the actual authority on
whether the result is short-free, not this script's own self-check --
exactly the lesson this project already learned once from a real router
bug (see docs/ROUTING_STATUS.md).

New capability vs. gen_routes.py: two-layer routing. All 115 components on
this board are placed on the top side only (F.Cu); B.Cu carries no
footprints, only the GND zone pour and whatever copper this script adds --
so it is comparatively open routing space. For any connection that cannot
be routed as a single F.Cu polyline, this script tries dropping a via near
each end (skipped for through-hole pads, which already have copper on
every layer) and routing the middle span on B.Cu instead.

GND is intentionally excluded from point-to-point routing here: with the
GND zone pours now actually filled (see docs/ERC_STATUS.md), a GND pad
that touches the pour on any layer is already electrically connected with
no explicit track needed -- attempting to also trace 141 GND pin-pairs
point-to-point would be redundant copper, not a real gap. The handful of
GND pads DRC still reports as unconnected after zone fill (isolated
placements the pour doesn't reach) are handled separately, by name, if
fixable without a placement rework.

Usage: python3 gen_routes_full.py
"""
import sys

import pcbnew

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
import gen_routes as gr
from design_data import NETS

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"
mm = gr.mm
MM = gr.MM

VIA_DIA = 0.6
VIA_DRILL = 0.4
VIA_OFFSETS = [
    (0.9, 0), (-0.9, 0), (0, 0.9), (0, -0.9),
    (0.9, 0.9), (-0.9, -0.9), (0.9, -0.9), (-0.9, 0.9),
    (1.4, 0), (-1.4, 0), (0, 1.4), (0, -1.4),
]


class Router2(gr.Router):
    """Extends gen_routes.Router with layer-aware segments and a B.Cu
    via-drop fallback when a direct F.Cu path can't be found."""

    def __init__(self, board):
        super().__init__(board)
        # placed_segments entries are now (x1,y1,x2,y2,net_name,layer,width_mm)
        self.placed_segments = []
        self.placed_vias = []  # (x, y, net_name, radius_mm)

        # CRITICAL: gen_routes.Router.__init__ starts placed_segments/vias
        # empty, which is only safe when it runs against a bare, just-
        # generated board (as gen_routes.py's own README instructs: "Run
        # gen_pcb.py again ... before every gen_routes.py run"). This
        # script instead runs against the board this project already
        # routed 13+ connections onto -- so it MUST seed its own
        # obstruction lists from whatever copper is already on the board,
        # or every clearance check below is silently blind to it. Missing
        # this the first time this script ran produced real 0.0000mm
        # track-vs-track clearance violations against pre-existing tracks
        # (caught by real DRC, not assumed away -- see docs/ERC_STATUS.md)
        # before this fix.
        for t in board.GetTracks():
            if t.GetClass() == "PCB_TRACK":
                s, e = t.GetStart(), t.GetEnd()
                self.placed_segments.append((
                    mm(s.x), mm(s.y), mm(e.x), mm(e.y),
                    t.GetNetname(), t.GetLayer(), mm(t.GetWidth()),
                ))
            elif t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                self.placed_vias.append((mm(p.x), mm(p.y), t.GetNetname(), mm(t.GetWidth()) / 2))

    # ---- layer-aware clearance checks (mirrors gen_routes.Router but
    # filters foreign tracks by layer; foreign-pad checks stay
    # layer-agnostic/conservative -- this board has no bottom-side
    # components, so the only real B.Cu obstructions are THT pads, which
    # are correctly caught either way since they report on every layer).
    def _seg_clear_of_tracks_layer(self, x1, y1, x2, y2, width_mm, net_name, layer):
        for (a, b, c, d, other_net, other_layer, other_width) in self.placed_segments:
            if other_net == net_name or other_layer != layer:
                continue
            # Pairwise clearance: half of THIS segment's width plus half of
            # the OTHER (already-placed) segment's width, not double the
            # current segment's width -- using only one side's width
            # silently under-checks whenever the two nets have different
            # trace widths (a real bug this script had on its first run;
            # see the __init__ comment above).
            if gr._seg_seg_dist(x1, y1, x2, y2, a, b, c, d) < (width_mm / 2 + other_width / 2 + 0.2):
                return False
        return True

    def _seg_clear_of_vias(self, x1, y1, x2, y2, width_mm, net_name, extra_vias=()):
        # A via's copper (and hole) exists on every layer between the pair
        # it connects (F.Cu-B.Cu here), so it is an obstruction for a
        # track candidate regardless of which of those layers the
        # candidate is on -- unlike tracks/pads, this check is not
        # layer-filtered. Missing this check entirely (the first version
        # of this script) let a real track get placed only 0.175mm from a
        # foreign-net via (0.2mm required) -- caught by real DRC, not
        # assumed away; see docs/ERC_STATUS.md.
        for (vx, vy, other_net, other_r) in list(self.placed_vias) + list(extra_vias):
            if other_net == net_name:
                continue
            if gr._dist_point_seg(vx, vy, x1, y1, x2, y2) < (width_mm / 2 + other_r + 0.2):
                return False
        return True

    # Board outline + required copper-to-edge clearance (matches this
    # board's real DRC-enforced "board setup constraints edge" rule,
    # 0.5mm -- see gen_pcb.py's BOARD_W/BOARD_H). The first version of
    # this script never checked candidate paths against the board edge at
    # all, which let 3 real B.Cu segments land only 0.45mm from Edge.Cuts
    # near the board's right side; caught by real DRC, not assumed away.
    BOARD_W = 110.0
    BOARD_H = 125.0
    EDGE_CLEARANCE = 0.5

    def _in_board(self, x, y, width_mm):
        m = width_mm / 2 + self.EDGE_CLEARANCE
        return m <= x <= (self.BOARD_W - m) and m <= y <= (self.BOARD_H - m)

    def _try_path_layer(self, pts, width_mm, net_name, layer, extra_vias=()):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if (x1, y1) == (x2, y2):
                continue
            if not (self._in_board(x1, y1, width_mm) and self._in_board(x2, y2, width_mm)):
                return False
            if not self._seg_clear_of_pads(x1, y1, x2, y2, width_mm, net_name):
                return False
            if not self._seg_clear_of_tracks_layer(x1, y1, x2, y2, width_mm, net_name, layer):
                return False
            if not self._seg_clear_of_vias(x1, y1, x2, y2, width_mm, net_name, extra_vias):
                return False
        return True

    def _commit_path_layer(self, pts, width_mm, net_name, layer):
        net = self.net_objs[net_name]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if (x1, y1) == (x2, y2):
                continue
            track = pcbnew.PCB_TRACK(self.board)
            track.SetStart(pcbnew.VECTOR2I(MM(x1), MM(y1)))
            track.SetEnd(pcbnew.VECTOR2I(MM(x2), MM(y2)))
            track.SetWidth(MM(width_mm))
            track.SetLayer(layer)
            track.SetNet(net)
            self.board.Add(track)
            self.placed_segments.append((x1, y1, x2, y2, net_name, layer, width_mm))

    # Physical hole-to-hole spacing (drill-to-drill, a manufacturing
    # constraint independent of net -- two same-net via holes drilled too
    # close together are just as unmanufacturable as two different-net
    # ones). Matches this board's real DRC-reported "board setup
    # constraints" minimum (0.2495mm edge-to-edge -- see docs/ERC_STATUS.md);
    # 0.26mm used here for a small additional margin.
    HOLE_TO_HOLE = 0.26

    def _point_clear(self, x, y, radius_mm, net_name, extra_vias=()):
        if not self._in_board(x, y, radius_mm * 2):
            return False
        for ref, p in self.all_pads:
            if p.GetNetname() == net_name:
                continue
            px, py = mm(p.GetPosition().x), mm(p.GetPosition().y)
            sz = p.GetSize()
            pad_r = max(mm(sz.x), mm(sz.y)) / 2
            if ((px - x) ** 2 + (py - y) ** 2) ** 0.5 < (pad_r + radius_mm + 0.2):
                return False
        for (a, b, c, d, other_net, _layer, other_width) in self.placed_segments:
            if other_net == net_name:
                continue
            if gr._dist_point_seg(x, y, a, b, c, d) < (radius_mm + other_width / 2 + 0.2):
                return False
        # Hole-to-hole spacing applies to EVERY via regardless of net (a
        # drilling constraint, not a copper-clearance one) -- checked
        # unconditionally, not skipped for same-net vias as the first,
        # buggy version of this function did (real DRC caught 4
        # [hole_near_hole] violations from that, including same-net
        # MODEM_VBAT vias 0.10mm apart; see docs/ERC_STATUS.md).
        for (vx, vy, other_net, other_r) in list(self.placed_vias) + list(extra_vias):
            same_net = other_net == net_name
            min_center_dist = radius_mm + other_r + self.HOLE_TO_HOLE
            if not same_net:
                min_center_dist = max(min_center_dist, radius_mm + other_r + 0.2)
            if ((vx - x) ** 2 + (vy - y) ** 2) ** 0.5 < min_center_dist:
                return False
        # Also keep new via holes away from existing THT pad holes (same
        # drilling-constraint reasoning) -- approximate a THT pad's hole
        # radius conservatively from its copper pad size.
        for ref, p in self.all_pads:
            if not p.HasHole():
                continue
            px, py = mm(p.GetPosition().x), mm(p.GetPosition().y)
            drill = p.GetDrillSize()
            hole_r = max(mm(drill.x), mm(drill.y)) / 2
            if ((px - x) ** 2 + (py - y) ** 2) ** 0.5 < (radius_mm + hole_r + self.HOLE_TO_HOLE):
                return False
        return True

    def _candidates(self, x1, y1, x2, y2):
        cands = [
            [(x1, y1), (x1, y2), (x2, y2)],
            [(x1, y1), (x2, y1), (x2, y2)],
            [(x1, y1), ((x1 + x2) / 2, y1), ((x1 + x2) / 2, y2), (x2, y2)],
            [(x1, y1), (x1, (y1 + y2) / 2), (x2, (y1 + y2) / 2), (x2, y2)],
        ]
        offs = (2.5, -2.5, 4.0, -4.0, 6.0, -6.0, 8.0, -8.0, 11.0, -11.0, 15.0, -15.0, 20.0, -20.0, 25.0, -25.0)
        for off in offs:
            cands.append([(x1, y1), (x1, y1 + off), (x2, y1 + off), (x2, y2)])
        for off in offs:
            cands.append([(x1, y1), (x1 + off, y1), (x1 + off, y2), (x2, y2)])
        for off in offs:
            cands.append([(x1, y1), (x1, y2 + off), (x2, y2 + off), (x2, y2)])
        for off in offs:
            cands.append([(x1, y1), (x2 + off, y1), (x2 + off, y2), (x2, y2)])
        return cands

    def route_fcu(self, ref_a, pin_a, ref_b, pin_b, width_mm, label=None):
        pa, pb = self.pad(ref_a, pin_a), self.pad(ref_b, pin_b)
        net_a, net_b = pa.GetNetname(), pb.GetNetname()
        if net_a != net_b:
            self.results.append((label, "FAIL", "net mismatch"))
            return False
        net_name = net_a
        x1, y1 = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
        x2, y2 = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
        for cand in self._candidates(x1, y1, x2, y2):
            if self._try_path_layer(cand, width_mm, net_name, pcbnew.F_Cu):
                self._commit_path_layer(cand, width_mm, net_name, pcbnew.F_Cu)
                self.results.append((label, "OK", f"{width_mm}mm F.Cu"))
                return True
        return False

    def _via_drop(self, pad_obj, x, y, net_name, extra_vias=()):
        """Returns (vx, vy, needs_via) or None. THT pads already have
        copper on B.Cu so no via is needed at all. extra_vias lets the
        caller pass along a via already chosen for the OTHER end of the
        same connection in this same call, so the two via-drop searches
        can't independently choose points too close to each other (they
        would otherwise both check only vias already committed from prior
        calls -- missing each other, since neither is committed yet;
        this produced a real same-net hole-to-hole DRC violation the
        first time this script ran without this parameter)."""
        if pad_obj.IsOnLayer(pcbnew.B_Cu):
            return (x, y, False)
        for dx, dy in VIA_OFFSETS:
            vx, vy = x + dx, y + dy
            if not self._point_clear(vx, vy, VIA_DIA / 2, net_name, extra_vias=extra_vias):
                continue
            if self._try_path_layer([(x, y), (vx, vy)], 0.3, net_name, pcbnew.F_Cu, extra_vias=extra_vias):
                return (vx, vy, True)
        return None

    def route_via_bcu(self, ref_a, pin_a, ref_b, pin_b, width_mm, label=None):
        pa, pb = self.pad(ref_a, pin_a), self.pad(ref_b, pin_b)
        net_a, net_b = pa.GetNetname(), pb.GetNetname()
        if net_a != net_b:
            return False
        net_name = net_a
        x1, y1 = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
        x2, y2 = mm(pb.GetPosition().x), mm(pb.GetPosition().y)

        va = self._via_drop(pa, x1, y1, net_name)
        # Pass va's chosen via (if any) as an extra obstruction so vb's
        # search can't land on top of it -- see _via_drop's docstring.
        provisional = [(va[0], va[1], net_name, VIA_DIA / 2)] if va and va[2] else []
        vb = self._via_drop(pb, x2, y2, net_name, extra_vias=provisional)
        if va is None or vb is None:
            self.results.append((label, "FAIL", "no clear via-drop point"))
            return False
        vax, vay, need_via_a = va
        vbx, vby, need_via_b = vb
        both_provisional = []
        if need_via_a:
            both_provisional.append((vax, vay, net_name, VIA_DIA / 2))
        if need_via_b:
            both_provisional.append((vbx, vby, net_name, VIA_DIA / 2))

        for cand in self._candidates(vax, vay, vbx, vby):
            if self._try_path_layer(cand, width_mm, net_name, pcbnew.B_Cu, extra_vias=both_provisional):
                # commit stubs (if any), vias, and the B.Cu span together
                if need_via_a:
                    self._commit_path_layer([(x1, y1), (vax, vay)], 0.3, net_name, pcbnew.F_Cu)
                    self._add_via(vax, vay, net_name)
                if need_via_b:
                    self._commit_path_layer([(x2, y2), (vbx, vby)], 0.3, net_name, pcbnew.F_Cu)
                    self._add_via(vbx, vby, net_name)
                self._commit_path_layer(cand, width_mm, net_name, pcbnew.B_Cu)
                self.results.append((label, "OK", f"{width_mm}mm via B.Cu"))
                return True
        self.results.append((label, "FAIL", "no clear B.Cu path"))
        return False

    def _add_via(self, x, y, net_name):
        via = pcbnew.PCB_VIA(self.board)
        via.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        via.SetWidth(MM(VIA_DIA))
        via.SetDrill(MM(VIA_DRILL))
        via.SetNet(self.net_objs[net_name])
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        self.board.Add(via)
        self.placed_vias.append((x, y, net_name, VIA_DIA / 2))

    def route2(self, ref_a, pin_a, ref_b, pin_b, width_mm, label=None):
        label = label or f"{ref_a}.{pin_a}-{ref_b}.{pin_b}"
        if self.route_fcu(ref_a, pin_a, ref_b, pin_b, width_mm, label):
            return True
        return self.route_via_bcu(ref_a, pin_a, ref_b, pin_b, width_mm, label)


def _mst_edges(points):
    """points: list of (ref, pin, x, y). Returns list of index pairs
    forming a minimum spanning tree (Prim's algorithm) so a multi-pin net
    is covered by the shortest total set of point-to-point hops rather
    than an arbitrary chain."""
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


# Width policy: current-carrying power/converter nets get wider traces;
# everything else (logic/data signals) gets a conservative 0.3mm, matching
# the width class already used for signal-priority routes in gen_routes.py.
_POWER_WIDTHS = {
    "+3V3": 0.5, "+5V0": 0.6, "VBAT_BUS": 0.8, "MODEM_VBAT": 0.6,
    "BATT_F": 0.8, "P1_F": 0.6, "VBAT_MAIN_OUT": 0.6, "VBAT_P1_OUT": 0.5,
    "5V0_SW": 0.6, "5V0_PRE": 0.5, "DOCK_PWR_RAW": 0.6, "DOCK_F": 0.6,
    "TERRA_BATT_RAW": 0.5, "TERRA_PWR": 0.5, "MODEM_5V0_SW": 0.6,
}


def width_for(net_name):
    return _POWER_WIDTHS.get(net_name, 0.3)


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    r = Router2(board)

    already_routed_pairs = set()
    for ref_a, pin_a, ref_b, pin_b, w, label in gr.ROUTES + gr.CM4_POWER_ROUTES:
        already_routed_pairs.add(frozenset({(ref_a, str(pin_a)), (ref_b, str(pin_b))}))

    total_ok, total_fail = 0, 0
    per_net_summary = []

    for net_name, conns in NETS.items():
        if net_name == "GND":
            continue  # satisfied by the filled zone pour; see module docstring
        # Resolve to real board positions; skip pins that don't have a
        # placed pad (shouldn't happen given validate.py, but be defensive).
        pts = []
        for ref, pin in conns:
            try:
                pad = r.pad(ref, pin)
            except KeyError:
                continue
            pts.append((ref, pin, mm(pad.GetPosition().x), mm(pad.GetPosition().y)))
        if len(pts) < 2:
            continue

        width = width_for(net_name)
        ok, fail = 0, 0
        for i, j in _mst_edges(pts):
            ref_a, pin_a, _, _ = pts[i]
            ref_b, pin_b, _, _ = pts[j]
            pair_key = frozenset({(ref_a, pin_a), (ref_b, pin_b)})
            if pair_key in already_routed_pairs:
                continue
            label = f"{net_name}: {ref_a}.{pin_a}-{ref_b}.{pin_b}"
            if r.route2(ref_a, pin_a, ref_b, pin_b, width, label):
                ok += 1
            else:
                fail += 1
        total_ok += ok
        total_fail += fail
        if ok or fail:
            per_net_summary.append((net_name, ok, fail))

    print(f"\nRouted OK: {total_ok}   Failed (left as ratsnest): {total_fail}")
    print("\nPer-net summary (net: routed/attempted):")
    for net_name, ok, fail in sorted(per_net_summary, key=lambda t: -(t[1] + t[2])):
        print(f"  {net_name:20s} {ok}/{ok+fail}")

    print("\nFailed edges:")
    for label, status, info in r.results:
        if status == "FAIL":
            print(f"  FAIL: {label} ({info})")

    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    print(f"\nSaved {PCB_PATH}")
    return r.results


if __name__ == "__main__":
    main()
