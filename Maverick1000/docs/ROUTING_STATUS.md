# Routing Status — Rev A (honest breakdown)

**This board is NOT fully routed. Most nets remain ratsnest (unrouted).**
This document exists so nobody mistakes "the PCB file has copper on it" for
"the PCB is routed." It lists exactly which connections are real, verified
copper traces and which are not, why the router's own self-verification was
not sufficient on its own, and what real KiCad DRC found once it was
actually run (see `docs/ERC_STATUS.md` and the final audit for the full
DRC results).

## A real bug was found in the router's own collision checker

`python/gen_routes.py`'s first pass claimed 18 of 57 targeted connections
succeeded, each supposedly verified collision-free against every foreign
pad and every previously-placed foreign track before being committed.
**That verification had a real bug.** Its segment-vs-segment distance
function (`_seg_seg_dist`) only checked the four endpoint-to-opposite-
segment distances -- the standard shortcut for "are these two segments far
apart," but wrong for the case where two segments actually cross mid-span
(a "+" or "T" crossing at a point that isn't either segment's endpoint).
Two grid-aligned tracks on different nets can cross exactly like that
without either endpoint coming close to the other track, and the old
function reported those as "clear" when the true distance at the crossing
point is zero.

**This was caught by running real KiCad DRC** (via `pcbnew.WriteDRCReport`,
see `docs/ERC_STATUS.md` for how -- KiCad 7.0.11's `kicad-cli` has no
`pcb drc` subcommand, so this required finding a working Python-API path
to the real DRC engine instead of trusting the router's own claims). The
first DRC run found real `[clearance]` violations with **0.0000 mm actual
clearance** between tracks on different nets (e.g. `BATT_F` crossing
`BOOT_5V`, `VBAT_P1_OUT` crossing `BOOT_5V`, `DOCK_OK` crossing `VBUS_IN`)
-- genuine short-circuit-risk crossings that the router had wrongly
called verified-safe. This is exactly the scenario the "never call a
board DRC-clean unless DRC actually ran" rule exists for: the router's
internal self-check was not equivalent to real DRC and would have shipped
a board with real short circuits if its output had been trusted without
independent verification.

**The bug is fixed**: `_seg_seg_dist` now does a proper segment-segment
intersection test (orientation + collinear-overlap, the standard
computational-geometry approach) before falling back to the endpoint
distances, so it correctly returns 0 for any actual crossing. The board
was regenerated from scratch and re-routed with the fixed checker, then
re-verified with real DRC again: **zero track-vs-track clearance
violations remain** (confirmed by grep-level inspection of the DRC report,
not just a summary count). The honest, corrected result was fewer
successful routes than the router's original wrong result claimed --
18 of 57, not 13 of 57 -- because 5 of the original "successes" were the
short-circuited routes this bug had wrongly allowed through, and the
stricter (correct) checker refuses paths near where those crossings would
have occurred.

## A missing component was also found during this audit (D5)

Separately from routing, the power-path review for this audit found that
U4 (TPS5430DDA, the 5 V buck regulator) is a **non-synchronous** buck --
it needs an external Schottky catch diode from its switch node (PH) to
GND, which the pre-audit design did not have at all. Without it the
converter cannot regulate correctly and the switch node can ring well
past the IC's rating. This was confirmed by cross-referencing 6
independent open-source TPS5430/5431 designs on GitHub (all of which
place this diode) -- see `docs/OTHER_COMPONENTS_VERIFICATION.md` for the
detail. **Fixed**: added D5 (SS34 Schottky) from `5V0_SW` (PH) to `GND` in
`python/design_data.py`, and added it to this router's priority list
(`U4.PH -> D5`, `D5 -> GND`). Adding a component shifted the auto-placed
power-section grid (D5's neighbors all moved one cell over), which changed
which of the previously-successful routes still have a clear path --
**final count after this fix: 13 of 59** attempted connections routed (the
priority list grew from 57 to 59 with D5's two new connections).

## Method (as corrected)

For each targeted two-pin connection, the router tries a growing list of
candidate shapes (direct, L-shaped, mid-channel jogs, and channel-offset
detours out to ±20 mm in four directions) and only commits a track if the
*entire* proposed path clears every foreign-net pad and every
already-placed foreign-net track segment by a safety margin, now verified
with a correct segment-distance/intersection test. If no candidate clears,
the connection is left as ratsnest. No track is committed on a "best
effort"/partial basis.

This is still not a maze router. It cannot hop layers mid-route, cannot
rip up and reroute a placed track to make room for a later one, and cannot
route around a component by going under/around a whole footprint's
courtyard in the general case. Given the very tight, non-router-aware
component spacing inherited from the original placement, that is why the
(corrected) success rate is low -- 13/59 -- despite several rounds of
tuning (expanding candidate shapes and offset distances found zero
additional routes past this point, both before and after the collision-fix
made the checker stricter).

## Priority-1/2/3 connections attempted: 59 total

**13 succeeded — real, verified, DRC-confirmed-clean copper on the board
today** (re-confirmed by an independent real-DRC run after the fix, zero
track-vs-track clearance violations found):

| # | Connection | Net context |
|---|---|---|
| 1 | F1 → D1 | Main battery fuse to TVS stub |
| 2 | F1 → Q1.Source | Main battery fuse to ORing FET source |
| 3 | F2 → D2 | Secondary battery fuse to TVS stub |
| 4 | Q2.Drain → RSH2 | Secondary ORing FET to current-shunt |
| 5 | U4.BOOT → C18 | TPS5430 bootstrap cap, pin 1 |
| 6 | U4.VSENSE → R1/R2 divider | Buck feedback network |
| 7 | U5.VOUT → C6 (+3V3) | LDO output decoupling |
| 8 | F3 → D3 | Dock power fuse to Schottky anode |
| 9 | D3 → D4 | Dock rectifier to TVS |
| 10 | Q5.Drain → Q6.Drain | Back-to-back FET mid node |
| 11 | Q6.Source → VBUS_IN | Blocking FET pair to charger VBUS |
| 12 | CM4 +5V0 pin 81 → C13 | CM4 power-pin decoupling |
| 13 | CM4 +5V0 pin 83 → C14 | CM4 power-pin decoupling |

**46 failed — left as ratsnest (schematic-correct, physically unrouted):**

| # | Connection | Why it matters |
|---|---|---|
| 1 | BATT_IN → F1 | Main battery input to fuse |
| 2 | F1 → U1.ANODE (sense) | LM74610 ORing sense tap |
| 3 | Q1.Drain → RSH1 | Main ORing FET to shunt |
| 4 | RSH1 → U6.IN+1 (sense) | Current-sense channel 1 |
| 5 | U1.CATHODE → RSH1 | LM74610 sense, same node as Q1 drain |
| 6 | F2 → U2.ANODE (sense) | LM74610 ORing sense tap, pack 2 |
| 7 | F2 → Q2.Source | Secondary battery fuse to FET |
| 8 | RSH2 → U6.IN+2 (sense) | Current-sense channel 2 |
| 9 | U2.CATHODE → RSH2 | LM74610 sense, pack 2 |
| 10 | VBAT_BUS → C3 | ORing bus to buck input cap |
| 11 | C3 → U4.VIN | Buck input cap to regulator VIN |
| 12 | U4.PH → L1 | **Buck switch node to inductor — power path** |
| 13 | L1 → RSH3 | **Inductor to output-side shunt — power path** |
| 14 | RSH3 → C4 (+5V0) | **Buck output to bulk cap — power path** |
| 15 | C18 → L1 (PH node) | TPS5430 bootstrap cap, pin 2 |
| 16 | U4.PH → D5 (catch diode cathode) | **Buck switch node to catch diode — power path, D5 added this audit pass** |
| 17 | D5 (catch diode anode) → GND | **Catch diode return — power path** |
| 18 | R1 → +5V0 | Feedback divider top |
| 19 | R2 → GND | Feedback divider bottom |
| 20 | +5V0 → C5 | 5V rail to LDO input cap |
| 21 | C5 → U5.VIN | LDO input cap to VIN pin |
| 22 | DOCK_PWR+ → F3 | Dock connector to fuse |
| 23 | DOCK_OK → U3.VAC1 (sense) | Charger AC-presence sense |
| 24 | DOCK_OK → Q5.Source | Charger blocking-FET pair, source leg |
| 25 | VBUS_IN → U3.VBUS(2) | **Charger VBUS input — power path** |
| 26 | U3.VBUS(2) → U3.VBUS(3) | VBUS pin pair tie (same pad group) |
| 27 | U3.ACDRV1 → R19 | Charger gate-drive to gate resistor |
| 28 | R19 → Q5.Gate | Gate resistor to blocking FET gate |
| 29 | Q5.Gate → Q6.Gate | Blocking FET pair gate tie |
| 30 | U3.BTST1 → C22 | Charger bootstrap cap pin 1 |
| 31 | C22 → DOCK_OK | BTST1 bootstrap cap reference leg |
| 32 | U3.SW1 → L2 | **Charger buck-boost switch node — power path** |
| 33 | U3.SW2 → L2 | **Charger buck-boost switch node — power path** |
| 34 | U3.BAT → C21 | Charger BAT pin decoupling |
| 35 | U3.BAT(23) → U3.BAT(22) | BAT pin pair tie (same pad group) |
| 36 | U3.BAT → BATT_F node | **Charge current returns to main pack — power path** |
| 37 | U3.PMID → C10 | Charger intermediate-bus decoupling |
| 38 | U3.SYS → C8 | Charger system-rail decoupling |
| 39 | U3.REGN → C9 | Charger internal-rail decoupling |
| 40 | 5V0_PRE → U6.IN+3 (sense) | Current-sense channel 3 |
| 41 | +5V0 → U6.IN-3 (sense) | Current-sense channel 3 return |
| 42 | VBAT_BUS → U6.IN-1 (sense) | Current-sense channel 1 return |
| 43 | VBAT_BUS → U6.IN-2 (sense) | Current-sense channel 2 return |
| 44 | CM4 +5V0 pin 77 → C11 | CM4 power-pin decoupling |
| 45 | CM4 +5V0 pin 79 → C12 | CM4 power-pin decoupling |
| 46 | CM4 +5V0 pin 85 → C15 | CM4 power-pin decoupling |

**Bolded rows above are actual power-conversion current paths** (buck
switch node, buck catch diode, charger switch nodes, charger BAT return,
charger VBUS input). These are the single highest-consequence unrouted
connections on the board: they carry switching current at up to several
amps and their trace geometry directly affects EMI, IR drop, and thermal
performance. Their absence, by itself, is sufficient to call this board
**not fabrication ready** regardless of any other finding.

## What is NOT covered by this document at all

The 59 connections above are only the priority-1/2/3 set (battery paths,
converter loops, charging path, current-sense taps) that `gen_routes.py`
targeted. **Every other net on the board — all of I2C, UART, SPI, USB,
GPIO/control, and the remaining CM4 power/decoupling fan-out not listed
above — has never been attempted by the router at all and exists purely
as ratsnest.** That is priorities 7-11 from the original routing order and
represents the large majority of the board's total connection count (307
total connections per `validate.py`, vs. 59 attempted here and only 13
actually copper). Real DRC's own "unconnected pads" count (218, see
`docs/ERC_STATUS.md`) independently confirms the scale of what remains
unrouted.

## Ground plane: also not present

Independent of signal routing, **the GND copper pour zones defined on all
4 copper layers currently contain no filled copper.** `pcbnew.ZONE_FILLER
.Fill()` segfaults in this KiCad 7.0.11 headless environment (reproduced
under both a direct call and `xvfb-run`, confirmed via `faulthandler` to
crash inside the C++ zone-filling code, not recoverable from Python), and
`kicad-cli pcb export gerbers` does not fill zones itself — it only plots
what is already filled. This means **the shipped gerbers, if generated
right now, would contain zero ground-plane copper** despite the zone
boundaries being correctly defined in the `.kicad_pcb` source. See the
final design audit for how this compounds with the routing gap.

## What this means for fabrication

Do not fabricate this board revision. Three independent, compounding gaps
— 46 of 59 priority connections (including every power-conversion switch
node) unrouted, zero ground-plane copper, and (see `docs/ERC_STATUS.md`)
90 real pad-to-pad clearance violations from tight component placement —
mean a board ordered from the current Gerbers would not function. The
schematic, netlist, symbols, and footprints have been verified as
electrically correct (see the other verification documents in this
directory); what remains is physical layout work: either finish routing
with a real interactive router (KiCad's own PCB editor, used
interactively) and get zone filling working (a different KiCad
build/version, or a non-headless environment), loosen the placement to
resolve the pad-clearance violations, or accept that this repository
currently ships a verified schematic and a partially-routed board file,
not a fabrication-ready one.
