# Maverick 1000 — SKYWARD-COMPUTE-CARRIER

**Frontier Robotics** | Internal codename: **SKYWARD** | Product: **Maverick 1000**
**Board:** SKYWARD-COMPUTE-CARRIER, **Rev A**, audited 2026-09-21

This is the main avionics/compute PCB for the Maverick 1000 autonomous
aerial robotics platform: a real, editable KiCad 7 project (not a rendering
or a mockup), generated end-to-end by the Python scripts in `python/` from
a single source-of-truth netlist/component list.

## Fabrication status: NOT FABRICATION READY

**Read `docs/FINAL_DESIGN_AUDIT.md` before doing anything else.** This
project went through a full engineering audit pass (component/pinout
verification against real datasheets, footprint dimension verification,
real KiCad DRC, priority-ordered routing) and the honest conclusion is
that this board is **not ready to send to a fab**. The schematic-level
design (component selection, pinouts, netlist) has been verified correct;
the PCB *layout* is not finished — most nets are unrouted, there is no
ground-plane copper, and real DRC found 90 pad-clearance violations from
tight component placement. None of this is hidden: every finding is
documented, with evidence, in the files below.

## Opening this project

1. Install [KiCad](https://www.kicad.org/) 7.0 or newer (this project was
   built and audited against 7.0.11; a normal desktop install, not a
   headless one, is required for the next steps).
2. Copy this entire `Maverick1000` folder to your machine (paths inside
   the project are relative, so it works from anywhere).
3. Open `kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pro`.
4. The custom parts library (`SKYWARD_Custom`) resolves automatically via
   the project-local library tables — you do not need to add it manually.
5. **First thing to do in the PCB editor:** press **B** (Fill Zones) or
   Edit > Fill All Zones — the GND pour zones are defined but shipped
   unfilled. KiCad's zone filler segfaults when called from Python in the
   headless environment this project was built in (confirmed, not just
   assumed — see `docs/ERC_STATUS.md`); it works normally as a GUI
   keypress in a real desktop KiCad install.
6. **Second thing to do:** finish routing. 13 of the 59 highest-priority
   connections (battery/converter/charging paths) are real copper; the
   rest — including every power-converter switch node — are ratsnest. See
   `docs/ROUTING_STATUS.md` for the exact connection-by-connection list of
   what's done and what isn't.
7. Re-run DRC (Inspect > Design Rules Checker) after routing and zone
   filling, and resolve the 90 pre-existing pad-to-pad clearance
   violations from component placement (see `docs/ERC_STATUS.md`) before
   ordering boards.

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
├── python/             <- every generator script; re-run to regenerate the project
├── docs/                <- architecture, verification, audit, and status docs
├── bom/BOM.csv
└── manufacturing/       <- gerbers, drill, position file, previews, fab notes
```

## What has been verified (with sources — see the individual documents)

- **Every real-part pinout used in this design has been cross-checked
  against authoritative sources** — not assumed from a similarly-named
  part, not invented. This audit pass specifically found and corrected
  several pre-existing errors: the BQ25792 charger was previously modeled
  as a fictional simplified part (real part is a 29-pin WQFN with a
  4-switch buck-boost topology — `docs/BQ25792_VERIFICATION.md`); the CM4
  connector pin numbers were arbitrary rather than the real Raspberry Pi
  pin assignments, and the design had assumed 5 independent CM4 UARTs
  when only 3 are actually available due to ALT-function pin muxing
  (`docs/CM4_PIN_VERIFICATION.md`); the LM74610 ORing controller was
  modeled with an invented 6-pin package including a GND pin the real
  8-pin part doesn't have (`docs/LM74610_VERIFICATION.md`); a P-channel
  MOSFET part number ("SQJ438EP") turned out not to be a real,
  findable part and was replaced with a verified-real one
  (`docs/OTHER_COMPONENTS_VERIFICATION.md`); the DF40C-100DS-0.4V
  connector footprint used the wrong pad-numbering scheme entirely
  (sequential instead of the real odd/even scheme) — would have made the
  CM4 connection completely non-functional if fabricated as-is
  (`docs/DF40C_FOOTPRINT_VERIFICATION.md`).
- **Netlist correctness**: every net cross-checked pin-for-pin between
  `python/design_data.py` (the source of truth) and KiCad's own exported
  netlist — zero mismatches, re-verified after every fix in this audit.
  `python/validate.py` also passes clean (86 components, 71 nets, 307
  connections, no shorts/orphans/duplicates).
  86 placed components with zero courtyard overlaps and zero footprints
  extending off the board outline (checked programmatically against
  actual KiCad footprint geometry).
- **Real DRC was actually run** against the PCB (via KiCad's Python API,
  since this KiCad 7.0.11 install has no `kicad-cli pcb drc`/`sch erc`
  command — see `docs/ERC_STATUS.md` for exactly how, and why that's the
  strongest check available in this environment). It found and led to
  fixing two real bugs: a collision-checking bug in this project's own
  router that had wrongly certified some tracks as short-free when they
  actually crossed a different net, and a BQ25792 footprint pad overlap.
  It also found a schematic bug (fixed): the CM4 J2 connector's schematic
  symbol was reusing J1's pin labels, so about half its pins displayed
  the wrong signal name even though the actual wiring was correct. A
  dedicated power-path review found a third real defect: U4's 5V buck
  converter was missing a required catch diode entirely (fixed by adding
  D5) — see `docs/ERC_STATUS.md` and `docs/OTHER_COMPONENTS_VERIFICATION.md`.
- **Real manufacturing outputs** — Gerber X2, Excellon drill, and CSV
  placement data, generated directly from the current `.kicad_pcb` and
  independently inspected (not just assumed correct from the source
  files) — see `manufacturing/stackup_and_fab_notes.md` and the rendered
  previews in `manufacturing/previews/`.

## What is not done (ranked by severity — see `docs/FINAL_DESIGN_AUDIT.md`)

1. **Routing is incomplete.** 46 of the 59 highest-priority connections
   are unrouted, including every power-converter switch node. The large
   majority of the board’s 307 total connections (all digital signal
   fan-out: I2C/UART/SPI/USB/GPIO) was never attempted. See
   `docs/ROUTING_STATUS.md`.
2. **No ground-plane copper exists.** KiCad's zone filler cannot run
   headlessly in the environment this was built in; fill zones in a
   normal KiCad GUI install before fabricating. See `docs/ERC_STATUS.md`.
3. **90 real pad-to-pad clearance violations** from tight component
   placement, found by actual DRC — a placement rework is needed. See
   `docs/ERC_STATUS.md`.
4. Several dimensional assumptions remain unverified against manufacturer
   mechanical drawings (DF40C/DF13 exact pad pitch and size, BQ25792
   exposed-pad size) — flagged explicitly in each verification document
   and in `docs/assumptions.md`, not silently assumed correct.
5. 8 minor silkscreen legend overlaps (cosmetic, non-blocking) — see
   `docs/ERC_STATUS.md`.

## Documentation index

- **`docs/FINAL_DESIGN_AUDIT.md`** — the top-level audit report: what was
  checked, what was found, what the fabrication-readiness verdict is and
  why. Start here.
- `docs/architecture.md` — system architecture, design decisions and why
- `docs/power_architecture.md` — battery/dock power topology in detail
- `docs/connector_pinouts.md` — every connector, pin-by-pin
- `docs/assumptions.md` — every assumption made and risk, ranked
- `docs/CM4_PIN_VERIFICATION.md`, `docs/BQ25792_VERIFICATION.md`,
  `docs/LM74610_VERIFICATION.md`, `docs/DF40C_FOOTPRINT_VERIFICATION.md`,
  `docs/OTHER_COMPONENTS_VERIFICATION.md` — per-component real-datasheet
  verification, with sources
- `docs/ROUTING_STATUS.md` — exact connection-by-connection routing
  status and the collision-checker bug found and fixed during this audit
- `docs/ERC_STATUS.md` — ERC/DRC methodology, results, and the bugs found
  as a direct result of actually running real checks
- `bom/BOM.csv` — full bill of materials with real manufacturer part numbers
- `manufacturing/stackup_and_fab_notes.md` — stackup, assembly, fab notes,
  manufacturing review findings
- `manufacturing/previews/` — rendered top/bottom/all-copper board previews
- `python/README.md` — how the generators work, how to re-run them
