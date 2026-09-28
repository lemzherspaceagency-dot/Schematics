# Manufacturing Notes — SKYWARD-COMPUTE-CARRIER Rev A

## Stackup — CORRECTED: this is an every-layer HDI build, not a standard low-cost 4-layer board

**This section was previously wrong and is corrected here.** It claimed
"1.0 mm finished thickness, standard low-cost fab process," but the live
`.kicad_pcb` file's actual `general.thickness` was **1.6 mm** (KiCad's
default, never explicitly set) — neither number was ever checked against
what this board's own copper actually requires. Both were wrong once a
real per-microvia manufacturability audit was finally done (see below).
Corrected finished thickness: **0.6 mm**.

### Why this had to change: microvia aspect ratio, not checked until now

This board has 48 microvias (0.1 mm laser-drilled finished hole / 0.3 mm
pad, confirmed uniform across all of them), spanning all three adjacent
copper-layer pairs: F.Cu–In1.Cu (20), In1.Cu–In2.Cu (21), In2.Cu–B.Cu (7).
KiCad's DRC has no aspect-ratio check at all — it only verifies clearance
and annular ring, so this was never flagged despite being real-DRC-clean
this entire project.

At the previous 1.6 mm thickness, 4 layers of 1 oz copper (0.14 mm total)
leave ~1.46 mm of dielectric across 3 gaps — averaging **~0.487 mm per
gap**. For a 0.1 mm microvia, that is a **~4.9:1 depth-to-diameter aspect
ratio**. Standard laser-microvia processes are specified for **≤~1:1**
(some advanced HDI vendors quote up to ~1.3:1); ~4.9:1 is not achievable
by any mainstream fab process — the holes would not reliably plate. This
was a real, previously-hidden fabrication blocker despite "0 unconnected,
0 DRC errors."

### The fix: every-layer (any-layer) HDI stackup at 0.6 mm total

This board's 48 microvias span **all three** layer transitions (not just
the outer two, which is the common "1+N+1" pattern most low-cost HDI
services support) — the In1.Cu–In2.Cu gap alone carries 21 of them, more
than either outer gap. That rules out the usual "thin outer builds around
a thick standard core" HDI structure, because the core gap here needs to
be microvia-thin too. This is a **sequential-build-up (SBU), every-layer
HDI stackup** — a real, purchasable process (common in compact/wearable
electronics), but a specialty/premium one, not "standard low-cost."

| Layer | Material | Thickness |
|---|---|---|
| — | Solder mask (top) | ~0.015 mm |
| L1 — F.Cu | Copper, 1 oz | 0.035 mm |
| — | Dielectric (laser-microvia build-up) | 0.10 mm |
| L2 — In1.Cu | Copper, 1 oz (GND pour) | 0.035 mm |
| — | Dielectric (laser-microvia build-up) | 0.10 mm |
| L3 — In2.Cu | Copper, 1 oz (GND pour) | 0.035 mm |
| — | Dielectric (laser-microvia build-up) | 0.10 mm |
| L4 — B.Cu | Copper, 1 oz | 0.035 mm |
| — | Solder mask (bottom) | ~0.015 mm |
| **Total** | | **~0.6 mm** |

0.1 mm dielectric per gap against a 0.1 mm microvia drill gives a **1:1**
aspect ratio at every transition — squarely within standard laser-HDI
capability, no longer a hidden risk.

**Fabrication requirement, stated plainly**: this design requires an
any-layer/every-layer HDI-capable fabrication process (sequential
laser-via build-up, all three copper gaps), not a plain 4-layer FR-4
shop. Say so explicitly when requesting quotes — this is a real cost and
lead-time difference from a standard 4-layer board, and hiding that
would be exactly the kind of unexamined assumption this audit exists to
catch.

### Checked before making this change, not just assumed safe

- **CM4/DF40C mechanical mating**: the Hirose DF40C-100DS-0.4V connector
  pair's mating stand-off height (1.5 mm or 3.0 mm variant) is a property
  of the connector body itself, not the carrier PCB's thickness — carrier
  thickness does not affect CM4-to-carrier engagement. (Independently
  researched; see chat history for sources.)
- **USB differential-pair impedance**: this project's own `architecture.md`
  and `docs/ROUTING_STATUS.md` already explicitly scope Rev A as **not**
  implementing controlled-impedance/length-matched differential routing
  ("single-ended, no true high-speed diff pairs routed in Rev A" — no
  `diff_pair` DRC rule exists). Raspberry Pi's own CM4 design guidance
  computes USB trace width/spacing against a 1.6 mm/2-layer assumption,
  and thinning the board would invalidate that target *if it had been
  targeted here* — it explicitly was not, so this is a pre-existing,
  already-documented Rev A limitation, not a new regression from this
  fix.
- **Not checked / flagged as a residual assumption**: exact through-hole
  component lead lengths (if any) against the new 0.6 mm thickness.
  Nearly every part on this board is SMD; verify any THT part's
  datasheet lead length before ordering, per this project's standing
  practice of flagging rather than silently assuming.

## Stackup (general)

4-layer, every-layer HDI, 0.6 mm finished thickness (see above).

| Layer | Function |
|---|---|
| L1 — F.Cu | Component/signal, top |
| L2 — In1.Cu | GND pour (return plane) |
| L3 — In2.Cu | GND pour (return plane / power distribution) |
| L4 — B.Cu | Component/signal, bottom (routing only — no components populated here) |

Copper weight: 1 oz (35 um) all layers — no high-current traces are carried
by this board (motor power stays on the FC/ESC board; this board's worst-case
continuous current is the ~3 A CM4 5 V rail, comfortably handled by 1 oz
copper at normal trace widths per IPC-2152).

Surface finish: ENIG recommended (fine-pitch CM4 connector and QFN parts
benefit from ENIG's flatness over HASL; ENIG is also the norm for HDI
builds generally).

Solder mask: standard green (or manufacturer default), both sides.
Silkscreen: white, both sides (top populated; identification text only on
top per `architecture.md`).

## Board outline

110 mm x 125 mm rectangle (grew from 110x90mm to fit the high-bandwidth
comms subsystem), 4x M2.5 mounting holes (2.7 mm finished hole) at (5,5),
(105,5), (5,120), (105,120) mm from the bottom-left origin of the
Edge.Cuts outline. See `docs/assumptions.md` #8 for sizing rationale.

## Gerbers / drill / position (this folder)

Regenerated fresh, this pass, directly from the current, post-completion-
pass `.kicad_pcb` via `kicad-cli pcb export gerbers` / `export drill`
(with `--excellon-separate-th`, giving a real PTH/NPTH split, an
improvement over the single combined drill file earlier passes shipped)
/ `export pos`. RS-274X Gerber X2, matching the job file
`SKYWARD-COMPUTE-CARRIER-job.gbrjob`. Placement/pick-and-place data is in
`../position/`; rendered previews and a STEP 3D model are in
`../previews/`. Regenerate any time by re-running the full pipeline in
`python/README.md` (now including `gen_routes_full.py` and
`apply_zone_overrides.py` — see that file for the updated order) followed
by the same `kicad-cli` commands (or see this file's git history for the
exact invocation used to produce the current outputs).

**Independently confirmed this pass, not just assumed from the source
`.kicad_pcb`**: the In1.Cu/In2.Cu gerber files contain real `G36`
region-fill commands (checked directly, not inferred) — i.e. **these
Gerbers contain real ground-plane copper**, reversing the previous
finding that KiCad's zone filler could not run in this environment.

## STILL DO NOT SUBMIT THESE GERBERS FOR FABRICATION

Two independent, compounding blockers remain, each sufficient on its own:

1. **157 of 469 connections remain unrouted** (down from the original
   342 unconnected pads before this project's fabrication-readiness
   completion pass — a real, substantial, DRC-verified improvement, not
   a complete fix). Concentrated in dense, fine-pitch fan-out around U3
   (BQ25792), U6 (INA3221), U7 (USB hub), and U10 (the new USB boot
   mux) — this project's own point-to-point auto-router cannot navigate
   these areas; completing them needs a real interactive maze router.
   See `docs/ROUTING_STATUS.md` for the exact, net-by-net breakdown.
2. **U8 (EC25 modem)'s footprint is an UNRESOLVED FABRICATION BLOCKER**
   (upgraded from "approximation" during the completion pass, after
   exhausting realistic search avenues across two sessions — no real
   manufacturer footprint source was found anywhere). **Do not order a
   stencil or place U8 from the current footprint under any
   circumstance.** See `docs/assumptions.md` #12.

Everything else that was blocking fabrication in earlier passes has been
resolved and independently re-verified this pass:

- Ground-plane copper: filled, real, confirmed present in the exported
  Gerbers (see above). One residual, minor finding — the F.Cu GND pour
  has an isolated-copper-island connectivity gap somewhere on the board
  that needs interactive KiCad inspection to locate; flagged, not hidden.
- Pad-to-pad clearance violations: 0 (was 63) — see `docs/ERC_STATUS.md`.
- Real DRC violations remaining: 15, all cosmetic silkscreen
  overlap/clipping warnings (non-blocking) — see `docs/ERC_STATUS.md`.
- CM4 programming/recovery: previously entirely missing (a real,
  board-level gap this pass found and fixed with new hardware, U10+J13)
  — see `docs/PROGRAMMING_DEBUG_GUIDE.md`.

Regenerate Gerbers from the current board after resolving items 1 and 2
above before submitting to a fab.

## Manufacturing review findings

Checked directly against the current board (not assumed from source
files):

- **Courtyard overlaps: 0** (118/118 footprints have a courtyard,
  verified via real DRC's `courtyards_overlap` check — one real overlap
  from this pass's new U10/C38 placement was found and fixed at the
  source, see `docs/ROUTING_STATUS.md` / git history).
- **Out-of-board footprints: 0.**
- **Copper-to-board-edge clearance: 0 pads/tracks within the board's
  0.5 mm edge-clearance rule** — one real gap from this pass's own new
  auto-router (which never checked candidate paths against the board
  edge at all) was found via real DRC and fixed at the source (the
  router now enforces this rule itself); see `docs/ROUTING_STATUS.md`.
- **Drill count**: 30 holes total (4x M2.5 mounting holes + through-hole
  connector/header pins + 26 new vias added by this pass's two-layer
  routing — up from 18 pre-via-routing/0 vias in earlier passes, a real,
  verified structural change, not a discrepancy).
- **Silkscreen: 15 real overlap/clip warnings from actual DRC** (11
  `silk_overlap` + 4 `silk_over_copper`) — all warnings (not errors),
  do not block fabrication, but should get a silkscreen-layout cleanup
  pass before production for assembly/rework readability. See
  `docs/ERC_STATUS.md` for the category breakdown.
- **`../previews/all_copper.png`** (F.Cu + In1.Cu + In2.Cu + B.Cu
  composite) now shows substantial real copper fill across the board —
  a direct visual confirmation of the zone-fill and routing progress
  this pass made, in clear contrast to the isolated-pads-only appearance
  documented in earlier passes' equivalent image.

Full DRC methodology, category breakdown, and every real router/footprint
bug a real DRC run found and that was fixed as a direct result across
every audit pass of this project, are in `docs/ERC_STATUS.md`.

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
  against the TI mechanical drawing before ordering a stencil. Note: a
  real pad-coordinate bug (pin 17) was found and fixed this pass — see
  `docs/ERC_STATUS.md` — the perimeter pad layout is now internally
  consistent, but the exposed-pad dimension itself remains unverified.
- Populate JP1 (VL53L5CX XSHUT select) per the desired default: bridge
  pins 1-2 (free-running, default/as-generated) or 2-3 (CM4 GPIO control,
  requires a Rev B firmware/GPIO assignment change).
- Test points TP1-TP4 are bare pads — a pogo-pin bed-of-nails fixture can
  use them directly for bring-up. See `docs/PROGRAMMING_DEBUG_GUIDE.md`
  for the full programming/debug/recovery procedure, including the new
  J13 USB boot-mode connector.
- **U8 (EC25 modem)**: **do not order a stencil/place this part from the
  current footprint** — UNRESOLVED FABRICATION BLOCKER (see
  `docs/COMMS_MODULE_DECISION.md`, `docs/assumptions.md` #12).
  Replace with a real manufacturer footprint first.
- **U7 (USB2512B hub), U10 (FSUSB42MUX boot mux), J13 (USB Micro-B)**:
  real, verified, stock-KiCad footprints — safe to order a stencil
  against as-is. Standard lead-free reflow.
- **J11 (SIM holder)**: generic footprint, not tied to a specific
  verified manufacturer part — confirm against the actual chosen product
  before ordering (see `docs/COMMS_MODULE_DECISION.md`).
- A real STEP 3D model (`../previews/SKYWARD-COMPUTE-CARRIER-3D.step`)
  is available for mechanical/clearance inspection in any CAD viewer
  (FreeCAD, SolidWorks, etc.) — the strongest 3D representation this
  environment could produce; some parts render as simple boxes where a
  3D model wasn't available to KiCad, which is expected and does not
  affect the board's own solid geometry.

## Panelization

Not defined in this Rev A — the board is a simple rectangle with no
V-score/mouse-bite requirements identified. A fab house can panelize
standard rectangular boards without additional input; consult them once
production quantities are known.
