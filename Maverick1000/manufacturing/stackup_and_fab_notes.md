# Manufacturing Notes — SKYWARD-COMPUTE-CARRIER Rev A

## Stackup

4-layer, 1.0 mm finished thickness, FR-4, standard low-cost fab process.

| Layer | Function |
|---|---|
| L1 — F.Cu | Component/signal, top |
| L2 — In1.Cu | GND pour (return plane) |
| L3 — In2.Cu | GND pour (return plane / power distribution) |
| L4 — B.Cu | Component/signal, bottom |

Copper weight: 1 oz (35 um) all layers — no high-current traces are carried
by this board (motor power stays on the FC/ESC board; this board's worst-case
continuous current is the ~3 A CM4 5 V rail, comfortably handled by 1 oz
copper at normal trace widths per IPC-2152).

Surface finish: ENIG recommended (fine-pitch CM4 connector and QFN parts
benefit from ENIG's flatness over HASL).

Solder mask: standard green (or manufacturer default), both sides.
Silkscreen: white, both sides (top populated; identification text only on
top per `architecture.md`).

## Board outline

110 mm x 90 mm rectangle, 4x M2.5 mounting holes (2.7 mm finished hole) at
(5, 5), (105, 5), (5, 85), (105, 85) mm from the bottom-left origin of the
Edge.Cuts outline. See `docs/assumptions.md` #8 for sizing rationale.

## Gerbers / drill / position (this folder, Rev A audit pass)

Generated directly from the real, current `.kicad_pcb` via `kicad-cli pcb
export gerbers` / `export drill` / `export pos` (RS-274X Gerber X2,
Excellon drill, CSV placement, matching the job file
`SKYWARD-COMPUTE-CARRIER-job.gbrjob`). Regenerate any time by re-running
`python/gen_pcb.py` + `python/gen_routes.py`, then the same `kicad-cli`
commands documented in `python/README.md` / this file's git history.
Placement/pick-and-place data is in `../position/`; rendered top/bottom
composite previews are in `../previews/`.

**DO NOT SUBMIT THESE GERBERS FOR FABRICATION.** This Rev A audit pass
found the board is not fabrication-ready, for reasons independent of and
in addition to each other:

1. **Only 13 of 57 targeted priority connections are real copper** — every
   power-converter switch node (TPS5430 PH, both BQ25792 SW1/SW2 nodes,
   the charger VBUS input, the charger BAT return) is unrouted. All of
   I2C/UART/SPI/USB/GPIO is unrouted. See `docs/ROUTING_STATUS.md` for the
   full connection-by-connection breakdown.
2. **Zero ground-plane copper.** The In1.Cu/In2.Cu gerbers in this folder
   are empty (confirmed by direct inspection — no G36/G37 region-fill
   commands, only board-outline-adjacent artifacts) because KiCad's zone
   filler cannot run in this headless environment. See
   `docs/ROUTING_STATUS.md` and `docs/ERC_STATUS.md`.
3. **90 real pad-to-pad clearance violations** from tight component
   placement, confirmed by an actual KiCad DRC run (not just a
   self-reported check) — see `docs/ERC_STATUS.md`.

Regenerate and re-run the checks in `docs/ERC_STATUS.md` after addressing
all three before submitting to a fab.

## Manufacturing review findings (Rev A audit pass)

Checked directly against the current board (not assumed from source
files):

- **Courtyard overlaps: 0** (85/85 footprints have a courtyard, verified
  programmatically).
- **Out-of-board footprints: 0.**
- **Copper-to-board-edge clearance: 0 pads within 0.3 mm of the outline.**
- **Drill count: 18 holes** (4x M2.5 mounting holes + through-hole
  connector/header pins). **Vias: 0** (all current copper is single-layer
  F.Cu; the routing gap above means most nets never reach a layer
  transition at all).
- **Silkscreen: 8 real overlap/clip warnings from actual DRC** (7
  `silk_overlap` + 1 `silk_over_copper`), independently confirmed by
  visually inspecting the rendered top-composite preview in
  `../previews/top_composite.png` — the "POWER" zone-label text visibly
  overlaps the `F1`/`R1` silkscreen reference designators in the power
  section, and "CM4" overlaps the `J1`/`J2` reference labels. All are
  warnings (not errors) and do not block fabrication by themselves, but
  should get a silkscreen-layout cleanup pass before production for
  readability during assembly/rework.
- **`../previews/all_copper.png`** (F.Cu + In1.Cu + In2.Cu + B.Cu
  composite) is the clearest single piece of evidence for the routing/
  ground-plane gap: it shows isolated component pads and a handful of
  short traces, with the two inner layers completely empty.

Full DRC methodology, category breakdown, and the two real router/
footprint bugs that a real DRC run found and that were fixed as a direct
result, are in `docs/ERC_STATUS.md`.

## Assembly notes

- CM4 connectors (J1, J2) are the tightest-tolerance parts on the board
  (0.4 mm pitch) — reflow with a stencil-printed paste process, not hand
  soldering, and inspect under magnification / X-ray if available before
  first power-on.
- U3 (BQ25792, WQFN-29 with exposed pad, real verified pinout — see
  `docs/BQ25792_VERIFICATION.md`) and U6 (INA3221, TSSOP-16) both need a
  normal lead-free reflow profile; no unusual thermal handling required.
  U3's exposed pad footprint dimension is a documented assumption (see
  `docs/BQ25792_VERIFICATION.md` and `python/gen_footprints.py`) — verify
  against the TI mechanical drawing before ordering a stencil.
- Populate JP1 (VL53L5CX XSHUT select) per the desired default: bridge
  pins 1-2 (free-running, default/as-generated) or 2-3 (CM4 GPIO control,
  requires a Rev B firmware/GPIO assignment change).
- Test points TP1-TP4 are bare pads — a pogo-pin bed-of-nails fixture can
  use them directly for bring-up.

## Panelization

Not defined in this Rev A — the board is a simple rectangle with no
V-score/mouse-bite requirements identified. A fab house can panelize
standard rectangular boards without additional input; consult them once
production quantities are known.
