# Documented Assumptions & Remaining Risks — Rev A

Ordered by risk to a first-fabrication build.

1. **RESOLVED (was: CM4 J1/J2 exact pin numbers not re-verified).** This
   build environment's outbound network access to
   `datasheets.raspberrypi.com` remains blocked (confirmed again in the
   audit pass), so the primary PDF still could not be fetched directly.
   Instead, every CM4 pin used in this design was re-derived from the
   official `raspberrypi/linux` kernel device tree (authoritative for GPIO
   ALT-function pin muxing) and cross-checked pin-for-pin against a shipped
   commercial CM4 product's open-source schematic (Home Assistant Yellow)
   plus five further independent open-source CM4 carrier board projects.
   This caught and fixed a real error: the original draft assumed 5
   independent UART instances were available and invented pin numbers for
   all of them; the CM4 actually has only 3 UART instances free of I2C0/
   SPI0 pin conflicts. All CM4 net assignments in `design_data.py` were
   corrected accordingly. Full methodology, sources, and the corrected pin
   table are in `docs/CM4_PIN_VERIFICATION.md`. **Residual, non-blocking
   risk:** this table has still not been diffed against the primary PDF
   directly -- recommended once before a production (not prototype) run,
   see `docs/FINAL_DESIGN_AUDIT.md`.

2. **RESOLVED (was: DF40C-100DS-0.4V footprint geometry a documented
   approximation).** Pitch (0.4mm), row spacing (3.08mm, was modeled as
   3.0mm), and pad size (0.2mm x 0.7mm, was modeled oversized at 0.25mm x
   0.9mm) are now confirmed against two independent real shipped-product
   KiCad footprints (`NabuCasa/yellow`, `hatlabs/HALPI2-hardware`) that
   both cite Hirose's own official 2D-drawing document URL and agree
   byte-for-byte. J1/J2 on the live board were updated to these real
   values (`python/fix_df40c_dimensions.py`). See
   `docs/DF40C_FOOTPRINT_VERIFICATION.md`.

3. **Terra P1 battery chemistry/voltage assumed identical class to the main
   pack (4S LiHV)** so it can be safely ORed onto the same bus at the same
   nominal voltage. If Terra P1's actual cell design differs, the ORing
   input protection component values (fuse rating, TVS clamp voltage) need
   re-sizing, but the topology itself does not change.

4. **Propulsion system is explicitly not selected by this board** per the
   brief. The 30-minute-plus endurance requirement is primarily a
   propulsion/airframe/battery-capacity problem; this board's job is to not
   waste energy and to give accurate real-time energy telemetry. Final
   motor/ESC/prop/battery selection remains an open system-level task.

5. **BN-220, ELRS RX, and Toothpick F4 exact connector pinouts on their own
   PCBs** are assumed to be the common wire-pigtail style used across the
   existing prototype (UART TX/RX/PPS/power/ground); this board provides a
   JST-GH pigtail landing point on the carrier side, so the actual mating
   is a wire harness, not a rigid connector-to-connector mate — low risk,
   easily adapted per the exact module purchased.

6. **VL53L5CX implemented as the ST VL53L5CX-SATEL satellite module**, not a
   bare-die reflow, per `connector_pinouts.md`. XSHUT default state
   (free-running vs. CM4-controlled reset) is a solder-jumper option on the
   PCB, not hard-wired, specifically so this can be decided without a
   respin.

7. **UPDATE (fabrication-readiness completion pass): routing coverage was
   substantially extended this pass** (58 additional non-GND connections
   routed via a new two-layer auto-router, `python/gen_routes_full.py`,
   plus GND satisfied by a real filled zone pour — see
   `docs/ROUTING_STATUS.md` for full detail, the real router bugs found
   and fixed while building it, and exactly which 149 pads remain
   unconnected). **Still a fabrication blocker** — routing is not
   complete — but meaningfully less severe than the original finding
   below, which is preserved for the historical record of the priority-
   only pass.

   *(Original finding, partially superseded above): Routing completeness (Rev A audit pass): the board is PARTIALLY
   routed, most nets remain ratsnest, and this is a fabrication blocker.*
   This package places all 86 components with zero courtyard overlaps and
   zero out-of-board footprints (both verified programmatically against
   the actual KiCad footprint geometry), defines all 71 nets with pads
   correctly assigned (cross-checked pin-for-pin against
   `python/design_data.py` and `kicad-cli sch export netlist`), and pours
   (unfilled, see #10) GND zones on all 4 copper layers.

   During this audit pass, a purpose-built point-to-point router
   (`python/gen_routes.py`) was used to attempt the highest-priority
   connections (main battery paths, ORing, buck/LDO converter loops, the
   dock charging path including the BQ25792 application circuit, and
   current-sense taps) in priority order, verifying every candidate track
   against every foreign-net pad and every already-placed foreign-net
   track segment before committing it — never routing a connection it
   could not prove collision-free. **That self-verification initially had
   a real bug** (its segment-distance check missed the case of two tracks
   crossing mid-span, not just near an endpoint) which real KiCad DRC
   caught as actual 0.0 mm-clearance short circuits between placed tracks
   on different nets — the router's own "verified collision-free" claim
   was wrong for 5 of its first 18 successes (of 57 attempted at that
   point). The bug is fixed (see `docs/ROUTING_STATUS.md` for the geometry
   detail) and the board re-routed with the corrected, stricter checker; a
   second real-DRC run confirms zero track-vs-track clearance violations
   remain. Separately, the power-path review (see #11 below) found U4's
   buck converter was missing a required catch diode; fixing it added a
   component (D5) and 2 more priority connections, for 59 total attempted.
   Final, honest result: **13 of 59 succeeded as real, DRC-confirmed-clean
   copper; 46 remain ratsnest, including every power-converter switch
   node** (TPS5430 PH→L1, the new PH→D5 catch-diode connection, both
   BQ25792 SW1/SW2→L2 nodes, the BQ25792 BAT→main-pack return, and the
   charger VBUS input). **Every net outside that priority set — all of
   I2C, UART, SPI, USB, and GPIO/control, the large majority of the
   board's 307 total connections — was never attempted and remains pure
   ratsnest.** The full connection-by-connection breakdown, the collision-
   checker bug, and why the router could not do better (tight,
   non-router-aware component placement inherited from the original
   layout; this is a simple point-to-point router, not a maze router — it
   cannot hop layers or rip up a placed track to make room), is in
   `docs/ROUTING_STATUS.md`. Completing the copper — most urgently the
   five unrouted power-converter switch/catch-diode/VBUS nodes — with
   KiCad's real interactive router is the single largest remaining task
   before this board is fabrication-ready. Real KiCad DRC (see
   `docs/ERC_STATUS.md`) also found 90 real pad-to-pad clearance
   violations from tight component placement, independent of routing — a
   second, separate blocker that a placement rework needs to address.

   The placement itself follows a deliberate zone plan (documented in
   `python/gen_pcb.py`): CM4 connectors + decoupling at the top, the power
   section (battery inputs, ORing, regulation, charging, telemetry) in the
   lower-left, Terra/status/test-point components in the lower-right, and
   all field-wired connectors (battery, dock, FC, GNSS, ELRS, ToF, Terra)
   on the board perimeter for post-assembly cable access, with the GNSS
   connector kept on the opposite side of the board from the switching
   regulators per the EMI guidance in `architecture.md`.

8. **Board outline (110 x 125 mm, confirmed from the live board's edge-cuts
   bounding box) and 4x M2.5 mounting hole pattern (100 x 115 mm, at
   (5,5)/(105,5)/(5,120)/(105,120)) are a reasonable placeholder** sized to
   fit the CM4 module footprint, all connectors, and the full 118-component
   count with zero courtyard overlap, not taken from an existing airframe
   CAD model (none was provided). Grew further from the original 80x65 mm
   `architecture.md` §4 target (and the 110x90mm figure once recorded here)
   as later passes added the comms module and completed real routing --
   shrinking it back down (tighter component pitch, 2-sided placement, or
   a non-rectangular outline that follows the airframe) is a reasonable
   Rev B optimization once the real mass budget is checked against
   `architecture.md` §7.

9. **RESOLVED (was: BQ25792 simplified to 8 fictional pins on a QFN-24
   footprint).** The real part is a 29-pin WQFN (not 24), with pin names
   that bear no resemblance to the placeholder used in the first draft.
   The schematic and footprint now carry the real, verified 29-pin
   pinout (plus the exposed pad) with a complete single-input application
   circuit (input blocking FET pair, bootstrap network, buck-boost
   inductor, TS/ILIM_HIZ/PROG biasing, I2C, interrupt routed to a spare
   CM4 GPIO). Full detail, sources, and the specific remaining
   uncertainties (the BTST1 bootstrap cap reference node, and the exact
   ILIM_HIZ/PROG/TS resistor values, which need the datasheet's sizing
   equations, not just its pinout) are in `docs/BQ25792_VERIFICATION.md`.

10. **UPDATE (fabrication-readiness completion pass): re-tested, and this
    finding no longer holds.** `pcbnew.ZONE_FILLER.Fill()` was re-run in
    this same headless environment and completed successfully, producing
    real, verified filled copper on all 4 GND zones (confirmed by direct
    inspection of the saved `.kicad_pcb`, not just a boolean return value
    -- see `docs/ROUTING_STATUS.md` for the detail). This project has no
    explanation for why the same call now succeeds where it previously,
    repeatedly did not — it is reported as a re-tested, current fact for
    this board and session, not a general claim that the underlying
    engine limitation is fixed. **Any future session must re-verify this
    before relying on it.** The original finding is preserved below for
    the record.

    *(Original finding, superseded above): Copper zones (GND pour, all 4
    layers) are written unfilled, and this
    audit pass confirmed there is no automated way to fill them in this
    environment — treat it as a hard fabrication blocker, not a cosmetic
    gap.* KiCad 7.0.11's `ZONE_FILLER.Fill()` reliably segfaults when
    called from this headless Python environment; this was re-confirmed
    during the audit both as a direct call and under `xvfb-run`, with
    `faulthandler` showing the crash is deep inside KiCad's C++ zone-fill
    code, not something catchable or retriable from Python. It was also
    confirmed during this audit that `kicad-cli pcb export gerbers` does
    **not** fill zones as part of exporting — inspecting the actual
    generated F_Cu Gerber content shows only pad-flash (D03) commands, no
    region-fill (G36/G37) commands. **This means Gerbers generated from
    this project today contain zero ground-plane copper on every layer**,
    regardless of the zone boundaries being correctly defined in the
    `.kicad_pcb` source. The zone outlines, layers and net assignment are
    all correctly written and will fill correctly the moment the project
    is opened in a normal (non-headless) KiCad install and saved, or via
    Edit > Fill All Zones (hotkey B) — but until that happens at least
    once and the result is re-exported, no ground plane exists in any
    output this project can currently produce. See
    `docs/ROUTING_STATUS.md` for how this compounds with the routing gap
    in #7.

11. **RESOLVED (was: undiscovered — U4's TPS5430 buck converter had no
    catch diode).** Found during this audit's dedicated power-path review:
    TPS5430 is a non-synchronous buck (integrated high-side switch only),
    confirmed by cross-referencing 6 independent open-source designs on
    GitHub that all place an external Schottky catch diode from the
    switch node (PH) to GND. The pre-audit design had none at all — the
    converter could not have regulated correctly if fabricated as-is.
    Fixed: added D5 (SS34) from `5V0_SW` to `GND`. See
    `docs/OTHER_COMPONENTS_VERIFICATION.md` and
    `docs/power_architecture.md`.

12. **RESOLVED (was: U8 (Quectel EC25 modem) footprint an unresolved
    fabrication blocker).** A subsequent session located and used a real,
    independently-published EG25-G (the same physical LCC-132 land
    pattern family as EC25, per Quectel's own shared mechanical design
    across the EC25/EG25 series) footprint from the OLIMEX open-hardware
    project, and parsed its exact pad coordinates (144 positions, 132 real
    + 12 non-copper documentation markers matching the real 73-84 pin
    gap) directly into `kicad/libraries/footprints/SKYWARD_Custom.pretty/
    LCC-132_EC25_verified.kicad_mod`, replacing the old proportional-
    distribution approximation entirely. Body outline corrected to
    29.0 x 32.0mm from the same real source (superseding the earlier
    29.0 x 32.8mm estimate). See `docs/EC25_FOOTPRINT_VERIFICATION.md`
    for the full sourcing record, cross-check methodology, and the one
    residual honestly-stated risk tier (no direct Quectel PDF obtained;
    confidence rests on an independently-published, internally
    cross-checked real land pattern, not a primary-source drawing).
13. **J11 (SIM holder) footprint is generic, not tied to a specific
    verified manufacturer part.** Nano-SIM push-pull holders vary in
    exact footprint between manufacturers even though the SIM card
    contact standard (ISO/IEC 7816) is standardized. Verify/replace
    against a specific chosen product before fabrication.
14. **U7 (USB2512B hub) bias/filter/crystal component values are typical-
    for-class, not independently verified.** The hub's real *pinout* and
    real *footprint* are both verified (footprint is KiCad's own
    maintained stock QFN-36-1EP part, matching the source symbol's own
    footprint reference exactly — the highest-confidence footprint
    verification in this project). What is NOT verified: the crystal
    frequency (24 MHz assumed, typical for this IC class), and the
    RBIAS/CRFILT/PLLFILT passive values (typical-for-class placeholders).
    Getting these wrong would likely affect USB PHY signal integrity/
    timing margin rather than cause an outright short or non-function —
    lower risk than #12, but still flagged rather than assumed correct.
    See `docs/COMMS_MODULE_DECISION.md`.
