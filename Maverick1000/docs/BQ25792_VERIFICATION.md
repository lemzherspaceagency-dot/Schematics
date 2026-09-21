# BQ25792 Verification — Rev A (post-audit correction)

## Why this document exists

Rev A's first draft modeled the BQ25792 as an 8-pin part with invented pin
names (`SW`, `VDD_LOGIC`, `PGND`) that do not exist on the real device, on
a QFN-24 footprint. **This was wrong on every count**: the real part is a
**29-pin WQFN** (package code RQM, TI's own designation `RQM0029A`), a
4-switch buck-boost charger with a materially more complex application
circuit than a simple buck charger. This document records the correction.

## Package size correction

Direct access to `ti.com` (including the BQ25792 datasheet PDF) is blocked
in this build environment. The correct package was established via:

1. A **WebSearch** snippet independently describing the part as "a 29-pin
   4mm x 4mm QFN package."
2. **Cross-referencing 15+ independent GitHub repositories** (different
   authors, different projects, spanning 2022-2026) that all use a
   `QFN-29_L4.0-W4.0-P0.40-TL-BQ25792RQMR` footprint or equivalent,
   including `M17-Project/LinHT-hw` (a shipped ham-radio handset product),
   `manuelkasper/kxusbc2`, `TheCacophonyProject/kicad-library`, and a
   `tscircuit` machine-readable chip dataset entry that independently
   lists `pin29: ["PMID"]`.
3. TI's own package-code convention (`RQM0029A` — package family `RQM`,
   pin count `0029`) appearing in an unrelated repo's footprint
   description, matching (3).

This many independent, unrelated sources agreeing on "29" leaves very
little room for coincidence.

## Pin table

Pin **names and numbers** were cross-checked between two independent,
unrelated open-source KiCad libraries for `BQ25792RQMR`:

- `M17-Project/LinHT-hw` `parts/parts.kicad_sym` (a shipped product)
- `tscircuit/dataset-srj10` `imports/BQ25792RQMR.tsx` (an independently
  machine-authored chip definition)

They agree on all 29 pins (one minor cosmetic difference: the tscircuit
source splits pin 22/23 as `BAT2`/`BAT1`, the KiCad source calls both
`BAT` — same physical function, multiple package pins for current
sharing, as is normal for a 5 A charger's battery connection).

| Pin | Name | Pin | Name | Pin | Name |
|---|---|---|---|---|---|
| 1 | STAT | 11 | ACDRV1 | 21 | ~INT |
| 2 | VBUS | 12 | ~QON | 22 | BAT |
| 3 | VBUS | 13 | ~CE | 23 | BAT |
| 4 | BTST1 | 14 | SCL | 24 | SDRV |
| 5 | REGN | 15 | SDA | 25 | SYS |
| 6 | D+ | 16 | TS | 26 | SW2 |
| 7 | D- | 17 | ILIM_HIZ | 27 | GND |
| 8 | VAC2 | 18 | BATP | 28 | SW1 |
| 9 | VAC1 | 19 | BTST2 | 29 | PMID |
| 10 | ACDRV2 | 20 | PROG | 30 | EP (assumption, see below) |

Pad-level mechanical coordinates for the footprint were taken directly
from the M17-Project footprint file (`QFN-29_L4.0-W4.0-P0.40-TL-
BQ25792RQMR.kicad_mod`), not re-derived from a generic QFN formula, so
the perimeter pad positions in `kicad/libraries/footprints/
SKYWARD_Custom.pretty/QFN-29_L4.0-W4.0-P0.40-BQ25792RQMR.kicad_mod` match
that independently-authored footprint pin-for-pin.

**Documented assumption — exposed pad (EP):** the reference footprint
that supplied the perimeter pad coordinates did not include a center
thermal/ground pad. WQFN packages in this TI family normally have one; a
conservative 2.4mm x 2.4mm EP was added rather than omitted (omitting a
real EP would be the worse error for a 5 A charger IC — floating an EP
that should be grounded risks both thermal failure and, on many WQFN
charger ICs, loss of the internal ground reference). **Verify the true EP
size against TI's mechanical drawing before fabrication.**

## Architecture correction: this is a 4-switch buck-boost charger

The pre-audit design modeled this part as if it were a simple synchronous
buck charger (single `SW` node, `VDD_LOGIC`/`PGND` pins that don't exist).
The real device has:

- **Input path**: `VAC1`/`VAC2` are high-impedance input-presence sense
  pins; the actual input current flows through the `VBUS` pins, gated by
  an **external** back-to-back P-FET pair (`ACFET`+`RBFET`) that the
  application circuit must provide — the IC only drives their gates
  (`ACDRV1`/`ACDRV2`) via a bootstrapped high-side driver (`BTST1`/
  `BTST2`).
- **Buck-boost power stage**: `SW1` and `SW2` are the two switching nodes
  of a 4-switch buck-boost converter, with a single inductor connected
  **between** them (not a simple buck inductor to a fixed rail).
  `PMID` is the internal intermediate bus between the input FETs and the
  buck-boost stage.
- **Outputs**: `SYS` is the regulated system-power output; `BAT` is the
  battery charge/discharge connection (separate from `SYS`).
- **Support**: `REGN` is the chip's internal LDO output, needs its own
  decoupling cap; `TS` is a thermistor input for JEITA charge-current
  foldback; `ILIM_HIZ` and `PROG` are resistor-programmed input-current-
  limit and charge-current-monitor pins; `QON`/`CE` are manual-power and
  chip-enable inputs; `STAT`/`~INT` are status/interrupt outputs;
  `SDRV` drives an optional external ship-mode FET (not populated).

## Implemented circuit (single input: VAC1/dock only)

Since this design only has one charge input (the dock), the second input
path is disabled per TI's documented convention for an unpopulated input:
`VAC2` tied to GND, `ACDRV2`/`BTST2` left unpopulated/NC. Implemented:

| Net/component | Connection | Confidence |
|---|---|---|
| Q5 (ACFET1) + Q6 (RBFET1) | Back-to-back P-FETs, `DOCK_OK` -> Q5 S/D -> Q6 D/S -> `VBUS_IN` (into U3 VBUS pins); gates driven together from `ACDRV1` through a 10R series resistor R19 | Structurally sound (standard back-to-back blocking topology, same pattern as the main/P1 ORing FETs elsewhere on this board); exact gate resistor value is a reasonable default, not datasheet-derived |
| C22 (BTST1 bootstrap cap) | `BTST1` <-> `DOCK_OK` (the input-side rail) | **Lowest confidence connection on this board.** The bootstrap cap's correct reference node (input rail vs. VBUS post-FET) was not independently verified against the primary datasheet application schematic. Verify before fab; wiring it to the wrong reference could prevent the gate driver from turning the FETs on at all (safe failure: charger simply won't charge) rather than damage anything, but this should still be confirmed. |
| CE | Tied to GND | High (near-universal active-low chip-enable convention) |
| QON | Pulled to +3V3 through R20 (inactive default) | High (no manual power button populated in Rev A) |
| BATP | Tied directly to the `BAT`/`BATT_F` node | **Function not independently confirmed from primary datasheet text** — tied as a conservative default that cannot make things worse; confirm BATP's actual purpose before relying on any feature that might depend on it (e.g. battery-presence detection) |
| TS | Fixed 10k/10k divider from REGN to GND (~half REGN) | Documented placeholder approximating "room temperature" to disable JEITA foldback; replace with the battery pack's real NTC divider if one is available |
| ILIM_HIZ, PROG | 5.6k to GND (placeholder) | **Values not derived from the datasheet equation** — flagged TBD in the BOM, confirm before relying on the resulting current limits |
| REGN, PMID, SYS, BAT | Each independently decoupled (1uF, 10uF, 10uF, 10uF respectively) | Standard practice, reasonable default values |
| SW1/SW2 | Existing 2.2uH inductor (L2) bridges them, per the 4-switch buck-boost topology | Structurally correct; exact inductor value not re-derived from the datasheet's power/ripple equations for this specific application |
| STAT, SDRV, D+/D- | Left NC (not implemented in Rev A) | Intentional scope reduction — no status LED consumer, no ship-mode FET, no USB PD/BC1.2 detection needed |
| ~INT | Pulled up (R21), routed to a spare CM4 GPIO (GPIO26, J1 pin24) as `GPIO_CHG_INT` | New capability added during this audit — gives the CM4 real charge-fault visibility it didn't have before |

## Summary

This is now a **structurally complete, real 29-pin representation** of
the BQ25792 with every pin accounted for (connected, or explicitly and
intentionally NC), replacing a fictional 8-pin placeholder. The pin
**identity** (name/number) is well-verified (two independent sources
agree). The **circuit topology** around the input blocking FETs and
bootstrap network is standard-pattern but not datasheet-equation-verified,
and is called out as the top remaining electrical risk in
`docs/FINAL_DESIGN_AUDIT.md`. Component **values** for TS/ILIM_HIZ/PROG
are explicitly flagged as placeholders pending the datasheet's sizing
equations, not hidden as if they were final.
