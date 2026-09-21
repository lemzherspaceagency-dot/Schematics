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

## Gerbers / drill (this folder)

Generated directly from the real `.kicad_pcb` via `kicad-cli pcb export
gerbers` / `export drill` (RS-274X Gerber X2, Excellon drill, matching the
job file `SKYWARD-COMPUTE-CARRIER-job.gbrjob`). Regenerate any time from the
KiCad project with File > Fabrication Outputs, or re-run
`python/gen_pcb.py` followed by the same `kicad-cli` commands documented in
`python/README.md`.

**Before sending to a fab:** this Rev A ships with zero pre-routed copper —
see `docs/assumptions.md` #7. The F.Cu/In1.Cu/In2.Cu/B.Cu gerbers in this
folder therefore currently contain only pads and (once filled) the GND
pour, no signal traces. **Do not submit these gerbers for fabrication until
routing is complete** — regenerate them after routing in KiCad.

## Assembly notes

- CM4 connectors (J1, J2) are the tightest-tolerance parts on the board
  (0.4 mm pitch) — reflow with a stencil-printed paste process, not hand
  soldering, and inspect under magnification / X-ray if available before
  first power-on.
- U3 (BQ25792, QFN-24 1EP) and U6 (INA3221, TSSOP-16) both need a normal
  lead-free reflow profile; no unusual thermal handling required.
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
