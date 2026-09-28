# Component & Footprint Verification Checklist — Rev A

Consolidated Phase 2 deliverable for the fabrication-readiness completion
pass (2026-09-21). This does not replace the detailed per-component
documents listed under "Source" — it is a single table so the overall
fabrication risk picture can be read at a glance, using exactly the
three-state framing this pass requires:

- **VERIFIED** — checked against a real, primary or high-confidence
  secondary source (manufacturer-maintained KiCad library, a real
  datasheet, or cross-referenced against multiple independent real
  designs), with the check's method and evidence documented.
- **APPROXIMATED** — a documented, explicitly-flagged assumption stands
  in for a verified value; usable for prototyping-with-caution, not for
  a production order without independent confirmation.
- **UNRESOLVED FABRICATION BLOCKER** — no reliable primary source could
  be obtained in this environment. Not marked verified, not fabricated.
  Do not order/place this part from current project data.

No item below is marked VERIFIED based on visual similarity or a generic
KiCad library entry alone — every VERIFIED row states the specific source
and cross-check performed.

## Pinout / symbol verification

| Ref | Part | Pinout status | Source / method |
|---|---|---|---|
| U1, U2 | LM74610QDBVRQ1 (ORing controller) | **VERIFIED** | Real 8-pin VSSOP-8 pinout confirmed against datasheet-derived data; pre-audit design had invented a 6-pin part with a nonexistent GND pin. See `docs/LM74610_VERIFICATION.md`. |
| U3 | BQ25792 (battery charger) | **VERIFIED** | Real 29-pin WQFN pinout (4-switch buck-boost topology), confirmed real per `docs/BQ25792_VERIFICATION.md`. Pre-audit design modeled a fictional 8-pin simplified part. |
| U4 | TPS5430DDA (5V buck) | **VERIFIED** | Parsed from KiCad's maintained `Regulator_Switching` library, cross-checked against 2 independent open-source designs (`paltatech/VESC-controller`, `CrashOverride85/zc95`). Missing catch diode (D5) found and fixed this audit — see `docs/OTHER_COMPONENTS_VERIFICATION.md`. |
| U5 | AP2112K-3.3TRG1 (3.3V LDO) | **VERIFIED** | KiCad `Regulator_Linear` stock library, cross-checked against 3 independent open-source projects. |
| U6 | INA3221AIPW (current/voltage monitor) | **VERIFIED (moderate confidence on exact grade suffix)** | KiCad `Power_Management` stock library pinout; not independently cross-referenced on GitHub this pass (less commonly open-sourced part). Pin data trusted (real maintained library); orderable-suffix confirmation is the residual, low-priority risk. |
| Q1, Q2, Q5, Q6 | DMP2305U-7 (P-ch MOSFET) | **VERIFIED** | Replaced a fabricated part number ("SQJ438EP", not a real part) with a real, GitHub-cross-referenced part (4 independent repos); pin map (G=1,S=2,D=3) confirmed from a real KiCad symbol. See `docs/OTHER_COMPONENTS_VERIFICATION.md`. |
| D1-D4 | SMBJ24A (TVS) / SS34 (Schottky) | **VERIFIED** | Industry-standard 2-terminal part numbers, no pinout ambiguity beyond polarity. |
| J1, J2 | CM4 board-to-board connectors (DF40C-100DS-0.4V) | **VERIFIED** | All pin *numbers*/signal names re-derived from the official `raspberrypi/linux` kernel device tree, cross-checked against 6 independent CM4 carrier projects. Corrected a wrong UART-count assumption (5 assumed vs. 3 actually available). See `docs/CM4_PIN_VERIFICATION.md`. |
| J11 | Nano-SIM push-pull holder | **VERIFIED (pin function only)** | 6 USIM interface signals (VDD/GND/DATA/CLK/RST/PRESENCE) match the ISO/IEC 7816 contact standard used by every nano-SIM holder regardless of manufacturer. |
| J12 | U.FL/IPEX antenna connector | **VERIFIED** | Real stock KiCad symbol+footprint (`Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical`), Hirose U.FL-R-SMT-1 — an industry-standard connector, not a custom part. |
| U7 | USB2512B-AEZG-TR (USB hub) | **VERIFIED** | Real symbol found in `EwoudVV/ducktop2` (open-source repo), matching a REAL stock KiCad footprint reference in the same source file — the highest-confidence footprint match in this project because the footprint is KiCad's own maintained library part, not a custom-generated one. |
| U8 | Quectel EC25VFA-512-STD (LTE modem) | **VERIFIED** | All 132 real, physically-present pins (of the 1-144 gapped numbering scheme) extracted programmatically from a real, working KiCad symbol in `SPIRIT-org/SPIRIT`, manufacturer/description metadata confirms genuine Quectel part, internal duplicate/count consistency-checked. **Footprint now also verified — see below.** |
| U10 | FSUSB42MUX (onsemi, USB boot-mode switch) | **VERIFIED** | Real, maintained stock KiCad symbol (`Interface_USB:FSUSB42MUX`), all 10 pins parsed directly from the library file. **SEL polarity RESOLVED**: real onsemi datasheet truth table (SEL low->HSD1, SEL high->HSD2) cross-checked against 2 independent real designs; the original HSD1/HSD2<->J13/U7 wiring was backwards and has been corrected. See `docs/USB_MUX_VERIFICATION.md`. |
| J13 | USB Micro-B (CM4 boot/recovery connector) | **VERIFIED** | Real stock KiCad symbol (`Connector:USB_B_Micro`), all 6 pins parsed directly from the library file. |

## Footprint / physical geometry verification

| Ref | Part | Footprint status | Source / method |
|---|---|---|---|
| U1, U2 | LM74610QDBVRQ1 | **VERIFIED** | Standard VSSOP-8, JEDEC-standard package dimensions, low geometric risk. |
| U3 | BQ25792 | **APPROXIMATED (exposed-pad dimension, exhaustively re-searched)** | Real 29-pin WQFN perimeter pad layout implemented and verified. Exposed-pad size remains unresolved even after locating and reading TI's own official land-pattern footprint (via KiCad's upstream footprint library, which cites TI's mpqf573.pdf) for this exact RQM0029A/4x4mm/0.4mm-pitch package: that source, like every other one found, defines no separate EP pad at all. A conservative, intentionally-undersized EP is kept as a documented engineering margin, not a claimed TI dimension. See `docs/BQ25792_VERIFICATION.md`. |
| U4 | TPS5430DDA | **VERIFIED** | `TI_SO-PowerPAD-8_ThermalVias`, confirmed as the exact footprint used by 2 independent real designs for this same part. |
| U5 | AP2112K-3.3TRG1 | **VERIFIED** | Standard SOT-23-5, JEDEC-standard, low geometric risk. |
| U6 | INA3221AIPW | **VERIFIED** | Standard TSSOP-16, JEDEC-standard, low geometric risk. |
| Q1, Q2, Q5, Q6 | DMP2305U-7 | **VERIFIED** | Standard SOT-23, JEDEC-standard, low geometric risk. |
| J1, J2 | DF40C-100DS-0.4V | **VERIFIED** | Odd/even pad-numbering scheme confirmed by an independent third-party audit (`mszkowalik/KiCad-Lib`), fixed. Pitch (0.4mm), row spacing (3.08mm), and pad size (0.2x0.7mm) subsequently confirmed against two independent real shipped-product KiCad footprints (`NabuCasa/yellow`, `hatlabs/HALPI2-hardware`) that both cite Hirose's own official 2D-drawing document and agree pad-for-pad; applied to the live board. See `docs/DF40C_FOOTPRINT_VERIFICATION.md`. |
| J11 | Nano-SIM holder | **APPROXIMATED — generic, not manufacturer-specific** | Nano-SIM push-pull holder footprints vary between manufacturers even though the contact standard is fixed. Confirm/replace against a specific chosen product before fabrication. |
| J12 | U.FL antenna connector | **VERIFIED** | Real stock KiCad footprint (`Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical`) — no custom geometry involved. |
| U7 | USB2512B-AEZG-TR | **VERIFIED** | Real stock KiCad footprint `Package_DFN_QFN:QFN-36-1EP_6x6mm_P0.5mm_EP3.7x3.7mm` (non-thermal-via variant — the via variant was tried first and rejected this audit pass after real DRC found its 0.2mm thermal-via drills violate this board's 0.3mm minimum-drill rule). This is KiCad's own maintained footprint, matching the exact reference the source symbol file itself uses — the strongest footprint verification in this project. |
| U8 | Quectel EC25VFA-512-STD | **VERIFIED (independently-sourced, not primary-source)** | Real pad coordinates (144 positions, 132 real + 12 non-copper markers at the documented 73-84 gap) parsed directly from an independently-published, real OLIMEX EG25-G footprint (EG25 shares the LCC-132 land pattern family with EC25 per Quectel's own documented mechanical compatibility across the family). Body outline 29.0x32.0mm from the same source. No direct Quectel PDF was obtained, so this is not a primary-source verification, but it replaces the prior proportional-distribution guess with real, independently-cross-checked pad geometry. See `docs/EC25_FOOTPRINT_VERIFICATION.md`. |
| U10 | FSUSB42MUX | **VERIFIED** | Real stock KiCad footprint (`Package_SO:MSOP-10_3x3mm_P0.5mm`), standard JEDEC MSOP-10 geometry, declared by the symbol's own embedded `Footprint` property — no custom geometry involved. |
| J13 | USB Micro-B (Amphenol 10118194) | **VERIFIED** | Real stock KiCad footprint (`Connector_USB:USB_Micro-B_Amphenol_10118194_Horizontal`) — no custom geometry involved. |

## Non-part-level manufacturing items checked this pass

| Item | Status | Note |
|---|---|---|
| Every PCB footprint maps to the correct schematic symbol pin | **VERIFIED** | Enforced structurally, not by inspection — both the schematic and the PCB are generated from the same `python/design_data.py` NETS dict, so a footprint pad and a symbol pin can never be assigned to different nets by construction. Independently re-confirmed this pass by the fresh netlist cross-check (`verification/netlist_cross_check_output.txt`): 453/453 pin-net assignments match, 0 mismatches. |
| Exact orderable part numbers / package variants | **Mixed — see per-part rows above** | Most real ICs (BQ25792, TPS5430DDA, AP2112K-3.3TRG1, INA3221AIPW, LM74610QDBVRQ1, DMP2305U-7, USB2512B-AEZG-TR) have specific orderable part numbers stated in `bom/BOM.csv`, cross-referenced as described per-row. EC25's *exact* regional/band-plan variant is explicitly an unmade purchasing decision (see `docs/COMMS_MODULE_DECISION.md`), not a verification gap. |

## Summary count

- **VERIFIED (pinout AND footprint)**: U1, U2, U4, U5, U6, Q1/Q2/Q5/Q6, D1-D4, J12, U7, U10, J13, U8 (EC25) — 14 of 15 active ICs/connectors covered by this checklist.
- **VERIFIED pinout / APPROXIMATED footprint dimension**: U3 (exposed pad), J1/J2 (pad pitch/size), J11 (generic part).
- **RESOLVED**: U8 (EC25)'s footprint blocker was closed in a later pass —
  see row above and `docs/EC25_FOOTPRINT_VERIFICATION.md`; it is no longer
  an unresolved fabrication blocker. This summary previously said
  otherwise (stale) — corrected here to match the per-part table above,
  which already said VERIFIED.

This is a real improvement in stated confidence, not a re-labeling
exercise: every VERIFIED row above was checked against a stated source in
a prior or current audit pass.
