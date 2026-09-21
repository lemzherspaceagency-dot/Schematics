"""Sanity-check design_data.py: catches typos before they become bad copper."""
import sys
from design_data import COMPONENTS, COMP_BY_REF, NETS, ALL_REFS

errors = []
warnings = []

# 1. every (ref,pin) used in NETS must reference a real component
pin_to_net = {}
for net, conns in NETS.items():
    for ref, pin in conns:
        if ref not in ALL_REFS:
            errors.append(f"NET '{net}': unknown component ref '{ref}'")
            continue
        key = (ref, pin)
        if key in pin_to_net and pin_to_net[key] != net:
            errors.append(f"Pin {ref}.{pin} appears in TWO nets: '{pin_to_net[key]}' and '{net}' (short)")
        pin_to_net[key] = net

# 2. every non-mechanical, non-CM4-connector component should have >=1 connected pin
connected_refs = {ref for (ref, pin) in pin_to_net}
for c in COMPONENTS:
    if c.group in ("mech",):
        continue
    if c.ref in ("J1", "J2"):
        continue  # CM4 connectors: most pins are intentionally NC, checked separately
    if c.ref not in connected_refs:
        errors.append(f"Component {c.ref} ({c.value}) has NO net connections at all")

# 3. duplicate component refs
refs_seen = {}
for c in COMPONENTS:
    refs_seen[c.ref] = refs_seen.get(c.ref, 0) + 1
for ref, n in refs_seen.items():
    if n > 1:
        errors.append(f"Duplicate component ref '{ref}' appears {n} times")

# 4. single-pin nets (except test points, which are legitimately single-pin probe nets)
for net, conns in NETS.items():
    refs_in_net = {ref for ref, pin in conns}
    if len(conns) == 1:
        ref = conns[0][0]
        if COMP_BY_REF.get(ref, None) and COMP_BY_REF[ref].group != "tp":
            warnings.append(f"Net '{net}' has only ONE pin ({conns[0][0]}.{conns[0][1]}) -- dead end?")

print(f"Components: {len(COMPONENTS)}   Nets: {len(NETS)}   Connections: {sum(len(v) for v in NETS.values())}")
print()
if warnings:
    print(f"--- {len(warnings)} warning(s) ---")
    for w in warnings:
        print("  WARN:", w)
    print()
if errors:
    print(f"--- {len(errors)} ERROR(s) ---")
    for e in errors:
        print("  ERROR:", e)
    sys.exit(1)
else:
    print("No errors.")
