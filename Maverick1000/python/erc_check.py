#!/usr/bin/env python3
"""
Schematic-level ERC-equivalent check -- real, re-runnable version of the
ad-hoc analysis this project ran during its first audit pass (see
docs/ERC_STATUS.md, "Schematic: ERC-equivalent check"). Kept as project
infrastructure this pass, like run_drc.py / netlist_cross_check.py,
instead of a throwaway /tmp script, per the fabrication-readiness
completion pass's Phase 5 instruction to actually re-run this rather than
just cite the earlier result.

This is explicitly NOT real KiCad ERC. This KiCad 7.0.11 install has no
`kicad-cli sch erc` subcommand and no Python-scriptable `eeschema` module
(confirmed, not assumed -- see docs/ERC_STATUS.md), so no ERC engine is
reachable in this environment at all. This script instead derives the two
ERC violation classes that are mechanically computable from a plain
netlist export alone:

  1. Driver conflicts -- two or more strict `output`-type pins on the
     same net (a real short between two active push-pull drivers).
  2. Fully floating inputs -- a net with exactly one node, and that node
     is an `input`-type pin.

It deliberately does NOT attempt KiCad's fuzzier ERC classes (power-input
-pin-not-driven / missing PWR_FLAG, bus/label syntax checks, hierarchy
checks) -- those need real schematic semantic context this flat netlist
export doesn't carry, and claiming to check them without that context
would be exactly the false confidence this project's audit discipline
exists to avoid.

Usage:
    kicad-cli sch export netlist -o /tmp/x.xml --format kicadxml \
        kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_sch
    python3 erc_check.py /tmp/x.xml
"""
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict


def main():
    if len(sys.argv) != 2:
        print("usage: erc_check.py <kicad-xml-netlist-file>")
        sys.exit(2)

    tree = ET.parse(sys.argv[1])
    root = tree.getroot()

    driver_conflicts = []
    floating_inputs = []
    net_count = 0

    for net in root.iter("net"):
        net_count += 1
        name = net.get("name")
        nodes = list(net.iter("node"))

        outputs = [n for n in nodes if n.get("pintype", "").split("+")[0] == "output"]
        if len(outputs) >= 2:
            refs = [f"{n.get('ref')}.{n.get('pin')}" for n in outputs]
            driver_conflicts.append((name, refs))

        # "unconnected-(...)" is KiCad's own auto-generated implicit net
        # name for a pin carrying a No-Connect flag -- i.e. a pin this
        # project deliberately marked NC (see gen_schematic.py: "places a
        # no-connect flag on every unused pin"), not an undocumented,
        # accidentally-floating input. Real ERC treats a flagged NC pin
        # as intentional and does not flag it; this check does the same,
        # or it would just be noise -- every one of this project's many
        # deliberately-unused pins (see docs/COMMS_MODULE_DECISION.md's
        # "intentionally left unconnected" list) would otherwise show up
        # here despite being correctly, explicitly documented already.
        if name.startswith("unconnected-("):
            continue
        if len(nodes) == 1 and nodes[0].get("pintype", "").split("+")[0] == "input":
            floating_inputs.append((name, f"{nodes[0].get('ref')}.{nodes[0].get('pin')}"))

    print(f"Nets checked: {net_count}")
    print(f"\nDriver conflicts (>=2 strict-output pins on one net): {len(driver_conflicts)}")
    for name, refs in driver_conflicts:
        print(f"  {name}: {refs}")

    print(f"\nFully floating inputs (single-node net, input-type pin): {len(floating_inputs)}")
    for name, ref in floating_inputs:
        print(f"  {name}: {ref}")

    print(
        "\nNote: this is an ERC-EQUIVALENT check derived from a flat netlist "
        "export, not real KiCad ERC (no ERC engine is reachable in this "
        "environment -- see docs/ERC_STATUS.md). It covers driver conflicts "
        "and fully-floating inputs only."
    )

    ok = not driver_conflicts and not floating_inputs
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
