#!/usr/bin/env python3
"""
Generate kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_sch --
a real, flat, single-sheet KiCad 7 schematic built entirely from
python/design_data.py (component list + netlist), using symgen.py to render
every symbol with correct real pin numbers/names/electrical types.

Connectivity model: every used pin gets a short stub wire ending in a local
label carrying the net name (same-named labels are electrically one net
anywhere on a flat sheet); every unused pin gets a no-connect flag. Nets
that contain a `power_in` pin with no `power_out` pin on the same net get a
PWR_FLAG symbol added automatically so ERC doesn't false-positive on
"power pin not driven".
"""

import uuid as uuidlib

from design_data import COMPONENTS, NETS, COMP_BY_REF
from libparse import get_pins_for_lib_id
import symgen

PROJECT = "SKYWARD-COMPUTE-CARRIER"
OUT_PATH = f"/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/{PROJECT}.kicad_sch"
ROOT_UUID = "b6f1a001-0000-4000-8000-000000000001"

STUB = 5.08


def u():
    return str(uuidlib.uuid4())


# ---------------------------------------------------------------------------
# Reverse index: (ref, pin) -> net name
# ---------------------------------------------------------------------------
PIN_NET = {}
for _net, _conns in NETS.items():
    for _ref, _pin in _conns:
        PIN_NET[(_ref, _pin)] = _net

# ---------------------------------------------------------------------------
# Render every distinct lib_id once
# ---------------------------------------------------------------------------
RENDERED = {}
for c in COMPONENTS:
    if c.lib_id not in RENDERED:
        RENDERED[c.lib_id] = symgen.render(c.lib_id)

# ---------------------------------------------------------------------------
# Determine which nets need a PWR_FLAG (contain a power_in pin, no power_out)
# ---------------------------------------------------------------------------
NEEDS_FLAG = set()
for net, conns in NETS.items():
    has_power_in = False
    has_power_out = False
    for ref, pinnum in conns:
        comp = COMP_BY_REF.get(ref)
        if comp is None:
            continue
        rs = RENDERED[comp.lib_id]
        # find the pin's etype by number
        pins = get_pins_for_lib_id(comp.lib_id)
        p = next((pp for pp in pins if pp.number == pinnum), None)
        if p is None:
            continue
        if p.etype == "power_in":
            has_power_in = True
        if p.etype == "power_out":
            has_power_out = True
    if has_power_in and not has_power_out:
        NEEDS_FLAG.add(net)

print("Nets needing PWR_FLAG:", sorted(NEEDS_FLAG))

# ---------------------------------------------------------------------------
# Layout: flowing grid per group
# ---------------------------------------------------------------------------
GROUP_ORDER = ["cm4_conn", "power", "cm4", "periph", "tp", "mech"]
GROUP_TITLE = {
    "cm4_conn": "CM4 MODULE CONNECTORS",
    "power": "POWER: BATTERY INPUTS, ORING, REGULATION, CHARGING, TELEMETRY",
    "cm4": "CM4 SUPPORT: BOOT/RESET STRAPS, DECOUPLING, DEBUG HEADER",
    "periph": "PERIPHERALS: FC / GNSS / ELRS / TOF / TERRA",
    "tp": "TEST POINTS",
    "mech": "MECHANICAL",
}


def group_of(c):
    if c.ref in ("J1", "J2"):
        return "cm4_conn"
    return c.group


placements = {}  # ref -> (x, y)
section_y = 20.0
texts = []  # (text, x, y)

for grp in GROUP_ORDER:
    refs = [c.ref for c in COMPONENTS if group_of(c) == grp]
    if not refs:
        continue
    texts.append((GROUP_TITLE[grp], 20.0, section_y))
    section_y += 12.0

    if grp == "cm4_conn":
        cell_w, cell_h, cols = 260.0, 140.0, 2
    elif grp == "mech":
        cell_w, cell_h, cols = 40.0, 40.0, 8
    else:
        cell_w, cell_h, cols = 90.0, 60.0, 8

    row = 0
    col = 0
    for ref in refs:
        x = 20.0 + cell_w / 2 + col * cell_w
        # Symbol origin = pin 1 (top of body), body hangs downward from it
        # (see symgen.py), so anchor near the TOP of the cell, not centered.
        y = section_y + 15.0 + row * cell_h
        placements[ref] = (x, y)
        col += 1
        if col >= cols:
            col = 0
            row += 1
    rows_used = row + (1 if col > 0 else 0)
    section_y += rows_used * cell_h + 25.0

SHEET_W = 20.0 + 8 * 90.0 + 40.0
SHEET_H = section_y + 40.0

# ---------------------------------------------------------------------------
# Emit body: symbol instances, stub wires, labels, no-connects, PWR_FLAGs
# ---------------------------------------------------------------------------
body_parts = []
used_lib_ids = set()

flag_lib_id = "power:PWR_FLAG"
RENDERED[flag_lib_id] = symgen.render(flag_lib_id)


def emit_instance(ref, lib_id, value, footprint, x, y, extra_props=None):
    rs = RENDERED[lib_id]
    used_lib_ids.add(lib_id)
    pins = get_pins_for_lib_id(lib_id)
    parts = [
        f'  (symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} 0) (unit 1)\n'
        f'    (in_bom yes) (on_board yes) (dnp no)\n'
        f'    (uuid {u()})\n'
        f'    (property "Reference" "{ref}" (at {x:.2f} {y - 3:.2f} 0)\n'
        f'      (effects (font (size 1.27 1.27)))\n'
        f'    )\n'
        f'    (property "Value" "{value}" (at {x:.2f} {y - rs.height - 3:.2f} 0)\n'
        f'      (effects (font (size 1.27 1.27)))\n'
        f'    )\n'
        f'    (property "Footprint" "{footprint}" (at {x:.2f} {y:.2f} 0)\n'
        f'      (effects (font (size 1.27 1.27)) hide)\n'
        f'    )\n'
        f'    (property "Datasheet" "~" (at {x:.2f} {y:.2f} 0)\n'
        f'      (effects (font (size 1.27 1.27)) hide)\n'
        f'    )\n'
    ]
    for p in pins:
        parts.append(f'    (pin "{p.number}" (uuid {u()}))\n')
    parts.append(
        f'    (instances\n'
        f'      (project "{PROJECT}"\n'
        f'        (path "/{ROOT_UUID}"\n'
        f'          (reference "{ref}") (unit 1)\n'
        f'        )\n'
        f'      )\n'
        f'    )\n'
        f'  )\n'
    )
    body_parts.append("".join(parts))

    # per-pin: stub+label if net exists, else no-connect
    for p in pins:
        lx, ly, lrot = rs.pin_pos[p.number]
        # KiCad negates a symbol's local Y when placing an instance on the
        # sheet (library Y+ is up, sheet Y+ is down) -- confirmed empirically
        # via kicad-cli netlist export (see git history / debugging notes).
        abs_x, abs_y = x + lx, y - ly
        net = PIN_NET.get((ref, p.number))
        if net is None:
            body_parts.append(f'  (no_connect (at {abs_x:.2f} {abs_y:.2f}) (uuid {u()}))\n')
            continue
        # extend stub outward in the pin's own direction
        dx = {0: STUB, 180: -STUB, 90: 0, 270: 0}[lrot]
        dy = {0: 0, 180: 0, 90: STUB, 270: -STUB}[lrot]
        end_x, end_y = abs_x + dx, abs_y + dy
        body_parts.append(
            f'  (wire (pts (xy {abs_x:.2f} {abs_y:.2f}) (xy {end_x:.2f} {end_y:.2f}))\n'
            f'    (stroke (width 0) (type solid)) (uuid {u()})\n'
            f'  )\n'
        )
        justify = "left" if lrot == 0 else ("right" if lrot == 180 else "left")
        label_rot = 0
        body_parts.append(
            f'  (label "{net}" (at {end_x:.2f} {end_y:.2f} {label_rot})\n'
            f'    (effects (font (size 1.016 1.016)) (justify {justify} bottom))\n'
            f'    (uuid {u()})\n'
            f'  )\n'
        )


for c in COMPONENTS:
    x, y = placements[c.ref]
    emit_instance(c.ref, c.lib_id, c.value, c.footprint, x, y)

# PWR_FLAGs: one per net needing a driver, placed near the top power section
flag_x = 20.0
flag_y = 5.0
for i, net in enumerate(sorted(NEEDS_FLAG)):
    fx = flag_x + i * 25.0
    fy = flag_y
    used_lib_ids.add(flag_lib_id)
    rs = RENDERED[flag_lib_id]
    fref = f"#FLG{i+1:02d}"
    body_parts.append(
        f'  (symbol (lib_id "{flag_lib_id}") (at {fx:.2f} {fy:.2f} 0) (unit 1)\n'
        f'    (in_bom no) (on_board no) (dnp no)\n'
        f'    (uuid {u()})\n'
        f'    (property "Reference" "{fref}" (at {fx:.2f} {fy-3:.2f} 0)\n'
        f'      (effects (font (size 1.016 1.016)) hide)\n'
        f'    )\n'
        f'    (property "Value" "PWR_FLAG" (at {fx:.2f} {fy+3:.2f} 0)\n'
        f'      (effects (font (size 1.016 1.016)) hide)\n'
        f'    )\n'
        f'    (property "Footprint" "" (at {fx:.2f} {fy:.2f} 0)\n'
        f'      (effects (font (size 1.27 1.27)) hide)\n'
        f'    )\n'
        f'    (property "Datasheet" "~" (at {fx:.2f} {fy:.2f} 0)\n'
        f'      (effects (font (size 1.27 1.27)) hide)\n'
        f'    )\n'
        f'    (pin "1" (uuid {u()}))\n'
        f'    (instances\n'
        f'      (project "{PROJECT}"\n'
        f'        (path "/{ROOT_UUID}"\n'
        f'          (reference "{fref}") (unit 1)\n'
        f'        )\n'
        f'      )\n'
        f'    )\n'
        f'  )\n'
    )
    lx, ly, lrot = rs.pin_pos["1"]
    abs_x, abs_y = fx + lx, fy - ly
    end_x, end_y = abs_x, abs_y - STUB  # pin points down (rot 270) into body; stub extends further down
    body_parts.append(
        f'  (wire (pts (xy {abs_x:.2f} {abs_y:.2f}) (xy {end_x:.2f} {end_y:.2f}))\n'
        f'    (stroke (width 0) (type solid)) (uuid {u()})\n'
        f'  )\n'
    )
    body_parts.append(
        f'  (label "{net}" (at {end_x:.2f} {end_y:.2f} 0)\n'
        f'    (effects (font (size 1.016 1.016)) (justify left bottom))\n'
        f'    (uuid {u()})\n'
        f'  )\n'
    )

# ---------------------------------------------------------------------------
# Section title texts
# ---------------------------------------------------------------------------
text_parts = []
for txt, x, y in texts:
    text_parts.append(
        f'  (text "{txt}" (at {x:.2f} {y:.2f} 0)\n'
        f'    (effects (font (size 2.54 2.54) bold) (justify left bottom))\n'
        f'    (uuid {u()})\n'
        f'  )\n'
    )

# ---------------------------------------------------------------------------
# Title block text
# ---------------------------------------------------------------------------
title_text = (
    '  (title_block\n'
    '    (title "SKYWARD-COMPUTE-CARRIER -- Maverick 1000 Main Avionics/Compute Board")\n'
    '    (date "2026-09-21")\n'
    '    (rev "A")\n'
    '    (company "Frontier Robotics")\n'
    '    (comment 1 "Internal codename: SKYWARD. Product: Maverick 1000.")\n'
    '    (comment 2 "See docs/assumptions.md before fabrication -- CM4 pinout and DF40C footprint need datasheet verification.")\n'
    '  )\n'
)

lib_symbols_block = "  (lib_symbols\n" + "".join(RENDERED[lid].embed_text for lid in sorted(used_lib_ids)) + "  )\n"

sch = (
    f'(kicad_sch (version 20230121) (generator eeschema)\n\n'
    f'  (uuid {ROOT_UUID})\n\n'
    f'  (paper "User" {SHEET_W:.2f} {SHEET_H:.2f})\n\n'
    f'{title_text}\n'
    f'{lib_symbols_block}\n'
    + "".join(text_parts)
    + "".join(body_parts)
    + f'\n  (sheet_instances\n    (path "/" (page "1"))\n  )\n'
    + ')\n'
)

with open(OUT_PATH, "w") as f:
    f.write(sch)

print(f"Wrote {OUT_PATH}")
print(f"Sheet size: {SHEET_W:.0f} x {SHEET_H:.0f} mm")
print(f"Components placed: {len(COMPONENTS)}   Distinct symbols embedded: {len(used_lib_ids)}")
