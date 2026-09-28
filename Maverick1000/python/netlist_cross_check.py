#!/usr/bin/env python3
"""
Source-of-truth cross-check: compares python/design_data.py's NETS (the
single source of truth for this project) against a freshly-exported real
KiCad netlist (kicad-cli sch export netlist), pin-for-pin. This is the
same check used throughout this project's audit history -- kept here as a
real, re-runnable script instead of a one-off shell command, so its
output is reproducible and its logic is reviewable.

Usage:
    kicad-cli sch export netlist -o /tmp/x.net kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_sch
    python3 netlist_cross_check.py /tmp/x.net

Exits 0 and prints "MISMATCHES: 0" on success; exits 1 and lists every
mismatch otherwise.
"""
import re
import sys

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
import design_data as dd


def parse_kicad_netlist(path):
    text = open(path).read()
    parts = re.split(r'\(net \(code "\d+"\) \(name "([^"]*)"\)', text)
    pin_to_net = {}
    for i in range(1, len(parts), 2):
        name = parts[i].lstrip("/")
        body = parts[i + 1]
        nodes = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', body)
        for ref, pin in nodes:
            pin_to_net.setdefault((ref, pin), set()).add(name)
    return pin_to_net


def main():
    if len(sys.argv) != 2:
        print("usage: netlist_cross_check.py <kicad-netlist-file>")
        sys.exit(2)

    kicad_pin_to_net = parse_kicad_netlist(sys.argv[1])

    dd_pin_to_net = {}
    for net, conns in dd.NETS.items():
        for ref, pin in conns:
            dd_pin_to_net.setdefault((ref, pin), set()).add(net)

    mismatches = []
    for (ref, pin), nets in dd_pin_to_net.items():
        kn = kicad_pin_to_net.get((ref, pin))
        if kn is None:
            mismatches.append((ref, pin, "MISSING_FROM_KICAD", nets, None))
        elif kn != nets:
            mismatches.append((ref, pin, "NET_MISMATCH", nets, kn))

    print(f"design_data.py pin-net assignments: {len(dd_pin_to_net)}")
    print(f"KiCad netlist pin-net assignments:   {len(kicad_pin_to_net)}")
    print(f"MISMATCHES: {len(mismatches)}")
    for ref, pin, kind, dd_nets, k_nets in mismatches:
        print(f"  {kind}: {ref}.{pin}  design_data={dd_nets}  kicad={k_nets}")

    sys.exit(0 if not mismatches else 1)


if __name__ == "__main__":
    main()
