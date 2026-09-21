# Maverick 1000 — SKYWARD-COMPUTE-CARRIER

**Frontier Robotics** | Internal codename: **SKYWARD** | Product: **Maverick 1000**
**Board:** SKYWARD-COMPUTE-CARRIER, **Rev A**, 2026-09-21

This is the main avionics/compute PCB for the Maverick 1000 autonomous
aerial robotics platform: a real, editable KiCad 7 project (not a rendering
or a mockup), generated end-to-end by the Python scripts in `python/` from
a single source-of-truth netlist/component list.

## Opening this project (Windows + KiCad)

1. Install [KiCad](https://www.kicad.org/) 7.0 or newer.
2. Copy this entire `Maverick1000` folder to your PC (paths inside the
   project are relative, so it works from anywhere).
3. Open `kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pro`.
4. The custom parts library (`SKYWARD_Custom`) resolves automatically via
   the project-local library tables — you do not need to add it manually.
5. **First thing to do:** open the PCB editor and press **B** (Fill Zones)
   or Edit > Fill All Zones — the GND pour zones are defined but shipped
   unfilled (KiCad's zone filler is not scriptable headlessly in the
   environment this was built in; filling takes one keypress in the GUI).
6. Read `docs/assumptions.md` before doing anything else — it lists,
   ranked by risk, exactly what still needs a human engineering pass
   before this board is sent to a fab (CM4 pin-number verification against
   the datasheet, connector footprint verification, and — the biggest
   remaining task — interactive copper routing; nothing is pre-routed).

## Directory structure

```
Maverick1000/
├── kicad/
│   ├── SKYWARD-COMPUTE-CARRIER/     <- open THIS .kicad_pro in KiCad
│   │   ├── SKYWARD-COMPUTE-CARRIER.kicad_pro
│   │   ├── SKYWARD-COMPUTE-CARRIER.kicad_sch
│   │   ├── SKYWARD-COMPUTE-CARRIER.kicad_pcb
│   │   ├── sym-lib-table / fp-lib-table   (project-local, portable)
│   │   └── full.net                        (exported netlist, for verification)
│   └── libraries/
│       ├── symbols/SKYWARD_Custom.kicad_sym
│       └── footprints/SKYWARD_Custom.pretty/
├── python/            <- every generator script; re-run to regenerate the project
├── docs/               <- architecture, power, connector pinouts, assumptions
├── bom/BOM.csv
└── manufacturing/      <- gerbers, drill file, stackup/fab notes
```

## What's real here

- Real `.kicad_pro` / `.kicad_sch` / `.kicad_pcb`, openable and editable in
  stock KiCad — verified in this build environment (KiCad 7.0.11) by
  round-tripping through KiCad's own netlist exporter and cross-checking
  every one of the 60 nets, pin-for-pin, against the Python source of
  truth (`python/design_data.py`) — zero mismatches.
- Real footprints with real pads on 75 placed components, zero courtyard
  overlaps and zero footprints extending off the board outline (both
  checked programmatically against actual KiCad footprint geometry, not
  eyeballed).
- Real net assignment: every pad's net was cross-checked against the
  design data — zero mismatches.
- Real board outline, 4x M2.5 mounting holes, 4-layer stackup, GND zones
  (defined, see above for filling), silkscreen identification
  (FRONTIER ROBOTICS / MAVERICK 1000 / SKYWARD-COMPUTE-CARRIER / REV A)
  and per-interface labels (CM4/FC/GNSS/ELRS/TOF/TERRA/POWER/BATT/DOCK).
- Real manufacturing outputs: Gerber X2 + Excellon drill, generated
  directly from the `.kicad_pcb` via `kicad-cli`.

## What's not done yet (see `docs/assumptions.md` for the full, ranked list)

1. CM4 J1/J2 pin numbers need a final check against the official Raspberry
   Pi CM4 datasheet (this build environment's network access to
   datasheets.raspberrypi.com was blocked; the functional signal
   assignment is correct, only exact pin numbers need verifying).
2. The DF40C-100DS-0.4V and DF13-22DP-1.25V footprints are dimensionally
   reasonable approximations of the published connector series geometry —
   verify against the manufacturer drawing before ordering boards.
3. **No copper is routed.** Every net is fully defined and will appear as
   ratsnest in KiCad; routing (power path first, then signal fan-out) is
   the main remaining task. See `python/README.md`'s debugging notes for
   why a blind auto-routing pass was deliberately not shipped.
4. GND zones are defined but unfilled (one keypress in KiCad, see above).

## Documentation index

- `docs/architecture.md` — system architecture, design decisions and why
- `docs/power_architecture.md` — battery/dock power topology in detail
- `docs/connector_pinouts.md` — every connector, pin-by-pin
- `docs/assumptions.md` — every assumption made and risk, ranked
- `bom/BOM.csv` — full bill of materials with real manufacturer part numbers
- `manufacturing/stackup_and_fab_notes.md` — stackup, assembly, fab notes
- `python/README.md` — how the generators work, how to re-run them
