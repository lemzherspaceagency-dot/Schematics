# Remaining Component Verification — Rev A audit pass

Covers TPS5430DDA, AP2112K-3.3TRG1, INA3221AIPW, the P-channel MOSFETs, and
the diodes. (LM74610, BQ25792 and the CM4 connectors have their own
dedicated verification documents — this covers everything else flagged in
the audit brief.)

## TPS5430DDA (U4, 5V buck regulator)

**Pin data source**: parsed directly from the `.kicad_sym` file shipped
with the installed KiCad 7.0.11 `Regulator_Switching` stock library — not
hand-typed. That library is maintained by the KiCad project against real
datasheets and used by a large community; this is a reliable source.
**Independently cross-checked** against `paltatech/VESC-controller` and
`CrashOverride85/zc95` (two unrelated open-source hardware projects),
which both confirm `TPS5430DDA` uses the `TI_SO-PowerPAD-8_ThermalVias`
footprint — the exact same footprint already used in this design. Pin
map (BOOT=1, NC=2/3, VSENSE=4, EN=5, GND=6, VIN=7, PH=8, GNDPAD=9) is
unchanged from the pre-audit design and confirmed correct.

**A real circuit-topology defect was found and fixed during this audit
pass**: pin data alone doesn't say whether a buck IC is synchronous
(needs no external catch diode) or non-synchronous (needs one, or the
converter cannot function and the switch node can ring well past the
IC's rating). The pre-audit design had never checked this and had **no
catch diode at all** on the PH/switch node. Checked this pass by cross-
referencing 6 independent open-source hardware projects on GitHub that
use TPS5430/TPS5431 (`Ethansuttor/drone_PCB` — 3 separate documents,
`BenSeverson/bisque`, `Zergie/Klipper_SensorBoard`,
`simon446/opencanopy`) — every single one places an external Schottky
catch diode (cathode -> PH, anode -> GND) at the switch node, with one
explaining explicitly: "Non-synchronous buck, so this carries the
inductor current for ~79% of every cycle - it is not optional and it is
not a snubber." **Fixed**: added D5 (SS34, `Diode_SMD:D_SMA`, matching
the current/voltage class of this design's other Schottkys) from `5V0_SW`
(PH) to `GND` — see `python/design_data.py` and
`docs/power_architecture.md`.

## AP2112K-3.3TRG1 (U5, 3.3V LDO)

**Pin data source**: parsed from the installed KiCad `Regulator_Linear`
stock library (`extends AP2204K-1.5` base pinout: VIN=1, GND=2, EN=3,
NC=4, VOUT=5). **Independently cross-checked** against 3 unrelated
open-source projects (`pointhi/HighPower-Mechaduino`, `uru-card/uru-card-pcb`,
`ErichStyger/mcuoneclipse`), which confirm the part is a real Diodes Inc.
SOT-23-5, 600 mA, fixed 3.3 V LDO — matching this design's footprint and
usage exactly.

## INA3221AIPW (U6, 3-channel current/voltage monitor)

**Pin data source**: parsed from the installed KiCad `Power_Management`
stock library (17-pin including EP, IN+/IN- x3, VS, GND, A0, SCL, SDA,
VPU, WARNING, CRITICAL, PV, TC). Not independently found on GitHub during
this pass (a less commonly open-sourced part), but the `AIPW` suffix
follows TI's standard grade/package naming (A = accuracy grade, I =
industrial temperature, PW = TSSOP-16) consistent with a real orderable
variant, and the stock KiCad symbol is a maintained, datasheet-derived
source. **Confidence: high on pin data (real library source), moderate
on exact orderable suffix** (not independently cross-checked against a
second source) — lowest priority remaining risk on this board, since a
current-sense front end is easy to bring up and debug in isolation if the
exact grade differs slightly.

## P-channel MOSFETs (Q1, Q2, Q5, Q6) — corrected during this audit

**The pre-audit design specified "SQJ438EP" (Vishay Siliconix), which
does not appear to be a real part number** — it was not found via GitHub
code search (which does find the real, similarly-numbered SQJ457EP and
SQJ463EP) nor via general web search, while a related real part
(SQJ138EP) turned out to be an 8-pin SO-8 N-channel device, not a SOT-23
P-channel device as the design required. This was a fabricated part
number and has been **replaced** with **DMP2305U-7** (Diodes
Incorporated), a real, independently-verified part:

- Confirmed real via 4 independent open-source repositories on GitHub
  (including a spacecraft/flight-computer project), all describing it as
  a SOT-23 P-channel MOSFET.
- Pin map confirmed directly from a real KiCad symbol file: **pin 1 =
  Gate, pin 2 = Source, pin 3 = Drain** — this exactly matches the
  `Device:Q_PMOS_GSD` pin convention (G=1, S=2, D=3) already used
  throughout this design, so **no schematic net rewiring was needed**,
  only the part number/manufacturer fields.
- **Voltage margin note**: DMP2305U-7 is rated -30 V Vds. This design's
  TVS clamps (SMBJ24A, 24 V standoff) clamp transients to roughly
  26-33 V depending on surge current, which is close to the FET's 30 V
  rating. This was true of the original (fictional) part choice too, so
  it is not a new problem, but it is now visible and should be reviewed
  — consider a 40 V-rated SOT-23 P-FET in the same DMP23xxU-class family
  if the margin is judged too thin after reviewing the actual transient
  environment (e.g. inductive kickback from the dock connector).

## Diodes: SMBJ24A (TVS), SS34 (Schottky)

Both are long-established, extremely widely second-sourced industry-
standard part numbers (SMBJ series TVS and SS3x series Schottky are
offered by essentially every diode manufacturer with near-identical specs
and the same part numbering — this is an industry-standard naming
convention, not a single-vendor proprietary number). Not independently
re-verified pin-for-pin in this pass (2-terminal parts have no pinout
ambiguity beyond polarity, which is a footprint/silkscreen concern, not a
netlist-correctness one) — low risk.

## Q_PMOS_GSD (KiCad stock generic symbol) and Fuse/R/C/L stock symbols

All parsed directly from the installed KiCad `Device.kicad_sym` stock
library, the same authoritative source used throughout this project.
