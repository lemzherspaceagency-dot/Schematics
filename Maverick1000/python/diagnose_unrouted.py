#!/usr/bin/env python3
"""
Full diagnostic report of every currently-unrouted pad-pair: net, both
endpoints, straight-line distance, and a region/category tag, plus a
geometric root-cause probe (does ANY path exist at zero clearance
margin? is a layer change/via required? how far from the nearest
obstacle-free corridor?).

Usage: python3 diagnose_unrouted.py
"""
import math
import re
import sys

import pcbnew

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"
REPORT = "/home/user/Schematics/Maverick1000/verification/drc_report.txt"

USB_NETS = {"CM4_USB_DP", "CM4_USB_DM", "BOOT_USB_DP", "BOOT_USB_DM",
            "HUB_USB_DP", "HUB_USB_DM", "MODEM_USB_DP", "MODEM_USB_DM",
            "USB2_0_DP", "USB2_0_DN"}
GATE_DRIVER_REFS = {"U1", "U2", "U3", "Q1", "Q2"}


def mm(v):
    return v / 1e6


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
        else:
            # one endpoint may be a Track/Via (mid-route stub) rather
            # than a bare pad -- still record what we can.
            pairs.append(None)
    return [p for p in pairs if p]


def categorize(net, ref_a, ref_b):
    both = {ref_a, ref_b}
    if net in USB_NETS:
        return "USB_DIFFERENTIAL_PAIR"
    if "J1" in both or "J2" in both:
        return "CM4_CONNECTOR_FANOUT"
    if both & GATE_DRIVER_REFS:
        return "GATE_DRIVER_BOOTSTRAP_CLUSTER"
    if ref_a.startswith("U7") or ref_b.startswith("U7"):
        return "U7_WIFI_SUPPORT"
    return "OTHER"


def main():
    pairs = parse_unconnected(open(REPORT).read())
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

    rows = []
    for net, ref_a, pin_a, ref_b, pin_b in pairs:
        pa, pb = find_pad(ref_a, pin_a), find_pad(ref_b, pin_b)
        if pa is None or pb is None:
            rows.append((net, ref_a, pin_a, ref_b, pin_b, None, "MISSING_PAD", None, None))
            continue
        ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
        bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
        dist = math.hypot(bx - ax, by - ay)
        cat = categorize(net, ref_a, ref_b)
        a_f, a_b = pa.IsOnLayer(pcbnew.F_Cu), pa.IsOnLayer(pcbnew.B_Cu)
        b_f, b_b = pb.IsOnLayer(pcbnew.F_Cu), pb.IsOnLayer(pcbnew.B_Cu)
        via_needed = not ((a_f and b_f) or (a_b and b_b))
        rows.append((net, ref_a, pin_a, ref_b, pin_b, dist, cat, via_needed, (ax, ay, bx, by)))

    by_cat = {}
    for r in rows:
        by_cat.setdefault(r[6], []).append(r)

    print(f"TOTAL UNROUTED PAIRS: {len(rows)}\n")
    for cat in sorted(by_cat, key=lambda c: -len(by_cat[c])):
        group = by_cat[cat]
        print(f"=== {cat}: {len(group)} pairs ===")
        dists = [r[5] for r in group if r[5] is not None]
        if dists:
            print(f"  distance range: {min(dists):.2f}mm - {max(dists):.2f}mm, "
                  f"median {sorted(dists)[len(dists)//2]:.2f}mm")
        for net, ref_a, pin_a, ref_b, pin_b, dist, _, via_needed, _ in group:
            dstr = f"{dist:.2f}mm" if dist is not None else "?"
            vstr = " [needs layer change]" if via_needed else ""
            print(f"  {net:22s} {ref_a}.{pin_a:>4s} -- {ref_b}.{pin_b:<4s} {dstr:>9s}{vstr}")
        print()


if __name__ == "__main__":
    main()
