#!/usr/bin/env python3
"""
Route the critical, current-carrying nets on SKYWARD-COMPUTE-CARRIER as
real, verified copper: battery paths, power converter loops, the dock
charge path, CM4 power/ground fan-out, and the current-sense (shunt)
connections -- priorities 1-6 of the routing brief. Lower-priority digital
signal fan-out (I2C/UART/SPI/USB/GPIO) is intentionally left as ratsnest;
see docs/ROUTING_STATUS.md for the exact, honest breakdown of what is and
isn't copper in this revision, and why (this project tried blind
point-to-point routing once before, in an earlier revision, and a
self-check caught it shorting across unrelated pads once the layout
changed -- that failure mode is exactly what the verification pass below
exists to prevent from recurring).

Every candidate track segment is checked against every pad NOT on its own
net, and against every previously-placed track segment on a different
net, before being committed. Nothing is written that fails that check.
"""

import sys
import pcbnew

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from design_data import NETS

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"
MM = pcbnew.FromMM


def mm(v):
    return v / 1e6


class Router:
    def __init__(self, board):
        self.board = board
        self.fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
        self.all_pads = [(fp.GetReference(), p) for fp in board.GetFootprints() for p in fp.Pads()]
        self.net_objs = {n.GetNetname(): n for n in board.GetNetInfo().NetsByNetcode().values()}
        self.placed_segments = []  # (x1,y1,x2,y2,net_name) in mm
        self.results = []

    def pad(self, ref, pin):
        fp = self.fp_by_ref[ref]
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p
        raise KeyError(f"{ref}.{pin} not found")

    def _seg_clear_of_pads(self, x1, y1, x2, y2, width_mm, net_name):
        pad_r_extra = width_mm / 2 + 0.15  # clearance margin
        for ref, p in self.all_pads:
            if p.GetNetname() == net_name:
                continue
            px, py = mm(p.GetPosition().x), mm(p.GetPosition().y)
            sz = p.GetSize()
            pad_r = max(mm(sz.x), mm(sz.y)) / 2
            d = _dist_point_seg(px, py, x1, y1, x2, y2)
            if d < (pad_r + pad_r_extra):
                return False
        return True

    def _seg_clear_of_tracks(self, x1, y1, x2, y2, width_mm, net_name):
        for (a, b, c, d, other_net) in self.placed_segments:
            if other_net == net_name:
                continue
            if _seg_seg_dist(x1, y1, x2, y2, a, b, c, d) < (width_mm / 2 + width_mm / 2 + 0.15):
                return False
        return True

    def _try_path(self, pts, width_mm, net_name):
        """pts: list of (x,y) mm waypoints. Returns True if the whole
        polyline is clear of foreign pads/tracks (checked segment by
        segment)."""
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if (x1, y1) == (x2, y2):
                continue
            if not self._seg_clear_of_pads(x1, y1, x2, y2, width_mm, net_name):
                return False
            if not self._seg_clear_of_tracks(x1, y1, x2, y2, width_mm, net_name):
                return False
        return True

    def _commit_path(self, pts, width_mm, net_name, layer=pcbnew.F_Cu):
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
            self.placed_segments.append((x1, y1, x2, y2, net_name))

    def route(self, ref_a, pin_a, ref_b, pin_b, width_mm, label=None):
        pa, pb = self.pad(ref_a, pin_a), self.pad(ref_b, pin_b)
        net_a, net_b = pa.GetNetname(), pb.GetNetname()
        if net_a != net_b:
            self.results.append((label or f"{ref_a}.{pin_a}-{ref_b}.{pin_b}", "FAIL", "net mismatch"))
            return False
        net_name = net_a
        x1, y1 = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
        x2, y2 = mm(pb.GetPosition().x), mm(pb.GetPosition().y)

        candidates = [
            [(x1, y1), (x1, y2), (x2, y2)],   # vertical first
            [(x1, y1), (x2, y1), (x2, y2)],   # horizontal first
            [(x1, y1), ((x1 + x2) / 2, y1), ((x1 + x2) / 2, y2), (x2, y2)],  # mid-channel jog (vertical mid)
            [(x1, y1), (x1, (y1 + y2) / 2), (x2, (y1 + y2) / 2), (x2, y2)],  # mid-channel jog (horizontal mid)
        ]
        # Channel-offset detours: run the "long" leg through a Y (or X) a
        # few mm off of both pins' native row/column, to get above/below
        # the row of components either pin sits in, then drop in from a
        # clear direction. Tried at increasing offsets.
        offs = (2.5, -2.5, 4.0, -4.0, 6.0, -6.0, 8.0, -8.0, 11.0, -11.0, 15.0, -15.0, 20.0, -20.0)
        for off in offs:
            candidates.append([(x1, y1), (x1, y1 + off), (x2, y1 + off), (x2, y2)])
        for off in offs:
            candidates.append([(x1, y1), (x1 + off, y1), (x1 + off, y2), (x2, y2)])
        for off in offs:
            candidates.append([(x1, y1), (x1, y2 + off), (x2, y2 + off), (x2, y2)])
        for off in offs:
            candidates.append([(x1, y1), (x2 + off, y1), (x2 + off, y2), (x2, y2)])
        for cand in candidates:
            if self._try_path(cand, width_mm, net_name):
                self._commit_path(cand, width_mm, net_name)
                self.results.append((label or f"{ref_a}.{pin_a}-{ref_b}.{pin_b}", "OK", f"{width_mm}mm"))
                return True
        self.results.append((label or f"{ref_a}.{pin_a}-{ref_b}.{pin_b}", "FAIL", "no clear path found"))
        return False


def _dist_point_seg(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    cx, cy = x1 + t * dx, y1 + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def _segs_intersect(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
    """True if segments A and B actually cross or touch (proper or
    improper intersection), via orientation tests + collinear overlap."""
    def orient(px, py, qx, qy, rx, ry):
        v = (qx - px) * (ry - py) - (qy - py) * (rx - px)
        if v > 1e-12:
            return 1
        if v < -1e-12:
            return -1
        return 0

    def on_seg(px, py, qx, qy, rx, ry):
        return (min(px, rx) - 1e-9 <= qx <= max(px, rx) + 1e-9 and
                min(py, ry) - 1e-9 <= qy <= max(py, ry) + 1e-9)

    o1 = orient(ax1, ay1, ax2, ay2, bx1, by1)
    o2 = orient(ax1, ay1, ax2, ay2, bx2, by2)
    o3 = orient(bx1, by1, bx2, by2, ax1, ay1)
    o4 = orient(bx1, by1, bx2, by2, ax2, ay2)

    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and on_seg(ax1, ay1, bx1, by1, ax2, ay2):
        return True
    if o2 == 0 and on_seg(ax1, ay1, bx2, by2, ax2, ay2):
        return True
    if o3 == 0 and on_seg(bx1, by1, ax1, ay1, bx2, by2):
        return True
    if o4 == 0 and on_seg(bx1, by1, ax2, ay2, bx2, by2):
        return True
    return False


def _seg_seg_dist(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
    # First check for an actual crossing/touch -- the true minimum
    # distance there is 0, which the endpoint-only checks below can miss
    # entirely (e.g. a "+" or "T" crossing at a non-endpoint point). This
    # bug was found by real KiCad DRC catching committed tracks that this
    # function had wrongly called "clear": two grid-aligned segments can
    # cross mid-span without either endpoint being close to the other
    # segment, which the old endpoint-distance-only check silently missed.
    if _segs_intersect(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
        return 0.0
    ds = [
        _dist_point_seg(ax1, ay1, bx1, by1, bx2, by2),
        _dist_point_seg(ax2, ay2, bx1, by1, bx2, by2),
        _dist_point_seg(bx1, by1, ax1, ay1, ax2, ay2),
        _dist_point_seg(bx2, by2, ax1, ay1, ax2, ay2),
    ]
    return min(ds)


# ---------------------------------------------------------------------------
# Priority routes: (ref_a, pin_a, ref_b, pin_b, width_mm, label)
# Widths sized per IPC-2152-style rule of thumb for 1oz copper, ~10C rise:
#  0.25mm ~= 0.5A, 0.4mm ~= 1A, 0.6mm ~= 1.5A, 0.8mm ~= 2A, 1.0mm ~= 2.5A,
#  1.2mm ~= 3A. Documented per-net current assumptions inline.
# ---------------------------------------------------------------------------
ROUTES = [
    # --- Priority 1: high-current main battery path (<=4A tap) ---
    ("J3", 1, "F1", 1, 1.0, "BATT_IN -> F1"),
    ("F1", 2, "D1", 1, 1.0, "F1 -> D1 (TVS stub)"),
    ("F1", 2, "U1", 4, 0.6, "F1 -> U1.ANODE (sense)"),
    ("F1", 2, "Q1", 2, 1.0, "F1 -> Q1.Source"),
    ("Q1", 3, "RSH1", 1, 1.0, "Q1.Drain -> RSH1"),
    ("RSH1", 1, "U6", 12, 0.5, "RSH1 -> U6.IN+1 (sense)"),
    ("U1", 8, "RSH1", 1, 0.4, "U1.CATHODE -> RSH1 (sense, same node as Q1 drain)"),

    # --- Priority 1: Terra P1 battery path (<=4A) ---
    ("F2", 2, "D2", 1, 1.0, "F2 -> D2 (TVS stub)"),
    ("F2", 2, "U2", 4, 0.6, "F2 -> U2.ANODE (sense)"),
    ("F2", 2, "Q2", 2, 1.0, "F2 -> Q2.Source"),
    ("Q2", 3, "RSH2", 1, 1.0, "Q2.Drain -> RSH2"),
    ("RSH2", 1, "U6", 15, 0.5, "RSH2 -> U6.IN+2 (sense)"),
    ("U2", 8, "RSH2", 1, 0.4, "U2.CATHODE -> RSH2 (sense)"),

    # --- Priority 2: 5V buck converter loop (~3A) ---
    ("RSH1", 2, "C3", 1, 1.0, "VBAT_BUS -> C3 (buck input cap)"),
    ("C3", 1, "U4", 7, 1.0, "C3 -> U4.VIN"),
    ("U4", 8, "L1", 1, 1.0, "U4.PH -> L1"),
    ("L1", 2, "RSH3", 1, 1.0, "L1 -> RSH3"),
    ("RSH3", 2, "C4", 1, 1.0, "RSH3 -> C4 (+5V0)"),
    ("U4", 1, "C18", 2, 0.4, "U4.BOOT -> C18 (bootstrap cap)"),
    ("C18", 1, "L1", 1, 0.4, "C18 -> L1 (bootstrap cap other leg, PH node)"),
    ("U4", 8, "D5", 1, 1.0, "U4.PH -> D5 catch diode cathode (non-sync buck, added this audit pass)"),
    ("D5", 2, "U4", 6, 0.6, "D5 catch diode anode -> GND"),
    ("U4", 4, "R1", 2, 0.3, "U4.VSENSE -> R1/R2 divider"),
    ("R1", 1, "C4", 1, 0.3, "R1 -> +5V0"),
    ("R2", 2, "U4", 6, 0.3, "R2 -> GND (feedback divider bottom)"),

    # --- Priority 2: 3V3 LDO loop (~0.6A) ---
    ("C4", 1, "C5", 1, 0.4, "+5V0 -> C5 (LDO input cap)"),
    ("C5", 1, "U5", 1, 0.4, "C5 -> U5.VIN"),
    ("U5", 5, "C6", 1, 0.4, "U5.VOUT -> C6 (+3V3)"),

    # --- Priority 3: dock charging path (~1.5A) ---
    ("J4", 1, "F3", 1, 0.6, "DOCK_PWR+ -> F3"),
    ("F3", 2, "D3", 2, 0.6, "F3 -> D3 (Schottky anode)"),
    ("D3", 1, "D4", 1, 0.6, "D3 -> D4 (TVS)"),
        ("D3", 1, "U3", 9, 0.3, "DOCK_OK -> U3.VAC1 (sense)"),
    ("D3", 1, "Q5", 2, 0.6, "DOCK_OK -> Q5.Source"),
    ("Q5", 3, "Q6", 3, 0.6, "Q5.Drain -> Q6.Drain (back-to-back mid node)"),
    ("Q6", 2, "C7", 1, 0.6, "Q6.Source -> VBUS_IN"),
    ("Q6", 2, "U3", 2, 0.6, "VBUS_IN -> U3.VBUS(2)"),
    ("U3", 2, "U3", 3, 0.6, "U3.VBUS(2) -> U3.VBUS(3)"),
    ("U3", 11, "R19", 1, 0.3, "U3.ACDRV1 -> R19 (gate resistor)"),
    ("R19", 2, "Q5", 1, 0.3, "R19 -> Q5.Gate"),
    ("Q5", 1, "Q6", 1, 0.3, "Q5.Gate -> Q6.Gate"),
    ("U3", 4, "C22", 1, 0.3, "U3.BTST1 -> C22"),
    ("C22", 2, "D3", 1, 0.3, "C22 -> DOCK_OK (bootstrap reference)"),
    ("U3", 28, "L2", 1, 0.8, "U3.SW1 -> L2"),
    ("U3", 26, "L2", 2, 0.8, "U3.SW2 -> L2"),
    ("U3", 22, "C21", 1, 0.8, "U3.BAT -> C21"),
    ("U3", 23, "U3", 22, 0.8, "U3.BAT(23) -> U3.BAT(22)"),
    ("C21", 1, "Q1", 2, 0.8, "U3.BAT -> BATT_F node (charges main pack, upstream of Q1)"),
    ("U3", 29, "C10", 1, 0.6, "U3.PMID -> C10"),
    ("U3", 25, "C8", 1, 0.6, "U3.SYS -> C8"),
    ("U3", 5, "C9", 1, 0.3, "U3.REGN -> C9"),

    # --- Priority 5: current-sense (INA3221 remaining channels) ---
    ("L1", 2, "U6", 2, 0.3, "5V0_PRE -> U6.IN+3 (sense)"),
    ("C4", 1, "U6", 1, 0.3, "+5V0 -> U6.IN-3 (sense)"),
    ("RSH1", 2, "U6", 11, 0.3, "VBAT_BUS -> U6.IN-1 (sense)"),
    ("RSH1", 2, "U6", 14, 0.3, "VBAT_BUS -> U6.IN-2 (sense)"),
]

# --- Priority 4/6: CM4 power fan-out (short hops to the nearby decoupling caps) ---
CM4_POWER_ROUTES = [
    ("J1", 77, "C11", 1, 0.6, "CM4 +5V0 pin77 -> C11"),
    ("J1", 79, "C12", 1, 0.6, "CM4 +5V0 pin79 -> C12"),
    ("J1", 81, "C13", 1, 0.6, "CM4 +5V0 pin81 -> C13"),
    ("J1", 83, "C14", 1, 0.8, "CM4 +5V0 pin83 -> C14"),
    ("J1", 85, "C15", 1, 0.8, "CM4 +5V0 pin85 -> C15"),
]


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    r = Router(board)

    for ref_a, pin_a, ref_b, pin_b, w, label in ROUTES + CM4_POWER_ROUTES:
        r.route(ref_a, pin_a, ref_b, pin_b, w, label)

    ok = sum(1 for _, s, _ in r.results if s == "OK")
    fail = sum(1 for _, s, _ in r.results if s == "FAIL")
    print(f"Routed OK: {ok}   Failed (left as ratsnest): {fail}")
    for label, status, info in r.results:
        if status == "FAIL":
            print(f"  FAIL: {label} ({info})")

    board.BuildConnectivity()
    pcbnew.SaveBoard(PCB_PATH, board)
    print(f"Saved {PCB_PATH}")
    return r.results


if __name__ == "__main__":
    main()
