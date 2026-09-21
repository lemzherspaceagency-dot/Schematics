#!/usr/bin/env python3
"""Generate bom/BOM.csv directly from design_data.py -- single source of truth."""
import csv
import sys
from collections import defaultdict

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from design_data import COMPONENTS

OUT = "/home/user/Schematics/Maverick1000/bom/BOM.csv"

groups = defaultdict(list)
for c in COMPONENTS:
    key = (c.value, c.mpn, c.manufacturer, c.footprint, c.description, c.group)
    groups[key].append(c.ref)

rows = []
for (value, mpn, manufacturer, footprint, description, group), refs in groups.items():
    refs_sorted = sorted(refs, key=lambda r: (len(r), r))
    rows.append({
        "Refs": ", ".join(refs_sorted),
        "Qty": len(refs_sorted),
        "Value": value,
        "MPN": mpn,
        "Manufacturer": manufacturer,
        "Footprint": footprint,
        "Description": description,
        "Group": group,
    })

group_order = {"cm4": 0, "power": 1, "periph": 2, "tp": 3, "mech": 4, "misc": 5}
rows.sort(key=lambda r: (group_order.get(r["Group"], 9), r["Refs"]))

with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["Refs", "Qty", "Value", "MPN", "Manufacturer", "Footprint", "Description", "Group"])
    w.writeheader()
    for r in rows:
        w.writerow(r)

total_parts = sum(r["Qty"] for r in rows)
print(f"Wrote {OUT}: {len(rows)} BOM line items, {total_parts} placed parts")
