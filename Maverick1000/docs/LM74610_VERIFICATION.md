# LM74610-Q1 Verification — Rev A (post-audit correction)

## Why this document exists

Rev A's first draft modeled the LM74610-Q1 as a 6-pin SOT-23-6 part with
invented pin names (`SNS`, `GND`, `VCAP`, `GATE`, `SUP`, `NC`) and ordered
it as `LM74610QDBVRQ1` (the `DBV` suffix is TI's SOT-23 package code).
**This was wrong.** The real orderable part in this family is
`LM74610QDGKRQ1` — an **8-pin VSSOP** (`DGK` = TI's VSSOP-8 package code).

## Verification

`ti.com` access remains blocked in this environment. The correction was
made by cross-referencing **two independent open-source KiCad symbol
libraries** for `LM74610QDGKRQ1`, from unrelated repositories
(`BlueJayRacing/22xt_kicad`, a university Formula SAE electric vehicle
project, and `beaked99/air-scales`), which **agree exactly** on all 8 pin
numbers and names:

| Pin | Name | Type |
|---|---|---|
| 1 | VCAPL | output |
| 2 | GATE_PULL_DOWN | bidirectional |
| 3 | NC | no_connect |
| 4 | ANODE | bidirectional |
| 5 | NC | no_connect |
| 6 | GATE_DRIVE | output |
| 7 | VCAPH | output |
| 8 | CATHODE | bidirectional |

One of the two sources additionally lists the TI SnapEDA package
metadata: `VSSOP-8`, footprint family `SOP65P490X110-8N` (0.65 mm pitch,
~4.90 mm lead span, 1.10 mm max height) — a standard package with a
direct stock-KiCad-library match, `Package_SO:VSSOP-8_3.0x3.0mm_
P0.65mm` (no exposed pad, matching this reference — neither source
lists one).

## What was wrong and what changed

1. **Package**: SOT-23-6 (6-pin) -> VSSOP-8 (8-pin). Different footprint
   entirely.
2. **No ground pin.** The real part is a floating, parasitically-powered
   controller (TI's own description: "zero IQ automotive ideal diode
   controller") — it derives its bias from the voltage across `ANODE`/
   `CATHODE` and does not need, and does not have, a separate ground
   connection. The original design tied a fictional "pin 2 GND" to the
   board's ground plane; that pin does not exist on the real part.
3. **Charge-pump cap topology.** The original design placed the VCAP
   bypass cap from a single "VCAP" pin to ground. The real part has two
   pins, `VCAPL` and `VCAPH`, with the capacitor connected **between**
   them (a charge-pump/doubler cap, not a simple decoupling cap to
   ground). `C16` (U1) / `C17` (U2) are now wired accordingly.
4. **Sense pin names**: `ANODE` (battery/source side) and `CATHODE`
   (bus/drain side) replace the invented `SNS`/`SUP` names — same
   electrical role (senses across the external pass FET to control ideal-
   diode behavior), correct real names.
5. **`GATE_PULL_DOWN`**: a second gate-related pin not present in the
   original 6-pin model at all. **Documented assumption**: tied to the
   same node as `GATE_DRIVE` (both pins are named for gate control; no
   primary datasheet text was available to confirm whether they must be
   separate). This is flagged as a residual risk, not asserted as
   datasheet-confirmed.

## Residual risk

The `GATE_PULL_DOWN` handling (tied together with `GATE_DRIVE`) is a
reasonable, low-risk default given the pin's name, but was not confirmed
against primary datasheet text (which was not accessible in this
environment). If TI's actual application circuit uses `GATE_PULL_DOWN`
differently (e.g. as a separate fast-discharge path to the FET source
rather than tied to the drive output), this connection should be revised
before fabrication. This is listed in `docs/FINAL_DESIGN_AUDIT.md`.
