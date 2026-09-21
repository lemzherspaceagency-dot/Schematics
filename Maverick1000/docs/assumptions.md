# Documented Assumptions & Remaining Risks — Rev A

Ordered by risk to a first-fabrication build.

1. **CM4 J1/J2 exact pin numbers not re-verified against the live datasheet.**
   This build environment's outbound network access to
   `datasheets.raspberrypi.com` (and mirrors on seeedstudio.com, pi4j.com)
   was blocked by the sandbox's egress proxy, so the ~45 CM4 signals used
   in this design were pin-mapped from the engineer's working knowledge of
   the published Raspberry Pi CM4 pinout rather than a live re-check of the
   PDF. **Action required before fabrication:** cross-reference every
   `CM4_J1_*` / `CM4_J2_*` net in the schematic against the official
   Raspberry Pi Compute Module 4 Datasheet pinout table (J1/J2 tables).
   The functional signal list itself (which UARTs/I2C/SPI/GPIO are used)
   is correct; only the exact physical pin numbers need the final check.
   This is a datasheet cross-reference task, not a redesign.

2. **DF40C-100DS-0.4V footprint geometry is a documented approximation.**
   The generated footprint uses 0.4 mm pitch, 2 rows x 50 contacts per
   connector, and a row-to-row spacing/pad size based on the published
   Hirose DF40C series family dimensions. Verify against Hirose's official
   DF40C-100DS-0.4V(51) mechanical drawing (or request a verified KiCad
   footprint from the connector distributor) before ordering boards —
   getting this one footprint wrong is the single highest-consequence
   manufacturing mistake possible on this board, since it is a fine-pitch,
   high pin-count part.

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

7. **Routing completeness (Rev A deliverable scope): no copper traces are
   pre-routed.** This Rev A package places all 75 components with zero
   courtyard overlaps and zero out-of-board footprints (both verified
   programmatically against the actual KiCad footprint geometry), defines
   all 60 nets with pads correctly assigned (cross-checked pin-for-pin
   against `python/design_data.py`), and pours (unfilled, see #10) GND
   zones on all 4 copper layers. Every net is therefore visible as
   ratsnest/airwires when the project is opened in KiCad, ready to route.
   An earlier version of this generator also drew ~40 "critical power
   path" tracks by connecting pads that were logically adjacent in the
   netlist. When the component layout was reworked to eliminate courtyard
   overlaps (see below), a self-check that compares every track segment
   against every pad not on its own net caught that several of those
   blindly-drawn tracks now crossed unrelated pads — i.e. the script would
   have silently shipped latent shorts. Rather than hand-verify ~40 routes
   against a layout with no visual feedback loop, all pre-routing was
   removed. Completing the copper (power path first, then signal fan-out)
   in KiCad's interactive router, or with an autorouter, is the main
   remaining task before this board is fabrication-ready — see the
   "Remaining Risks" list in the final project report.

   The placement itself follows a deliberate zone plan (documented in
   `python/gen_pcb.py`): CM4 connectors + decoupling at the top, the power
   section (battery inputs, ORing, regulation, charging, telemetry) in the
   lower-left, Terra/status/test-point components in the lower-right, and
   all field-wired connectors (battery, dock, FC, GNSS, ELRS, ToF, Terra)
   on the board perimeter for post-assembly cable access, with the GNSS
   connector kept on the opposite side of the board from the switching
   regulators per the EMI guidance in `architecture.md`.

8. **Board outline (110 x 90 mm) and 4x M2.5 mounting hole pattern
   (100 x 80 mm)** are a reasonable placeholder sized to fit the CM4 module
   footprint plus connector clearance and the full component count on a
   250 g-class airframe central stack, not taken from an existing airframe
   CAD model (none was provided). This is larger than the original 80x65 mm
   target in `architecture.md` §4 because laying out 75 real components
   with verified zero courtyard overlap needed the extra room -- shrinking
   it back down (tighter component pitch, 2-sided placement using the
   bottom copper layer, or a non-rectangular outline that follows the
   airframe) is a reasonable Rev B optimization once routing is complete
   and the real mass budget is checked against `architecture.md` §7.

9. **BQ25792 charger schematic symbol is simplified to the 8 nets used in
   Rev A** (VAC1, GND, SW, VDD_LOGIC, SDA, SCL, PROG, PGND) rather than its
   full 24-pin QFN pinout, since no correct pin-accurate KiCad symbol for
   this recent part was available in this environment's offline library.
   The footprint IS the real 24-pin QFN-24 1EP package. Before fabrication,
   reconcile the schematic pin-for-pin against the BQ25792 datasheet
   (most of the remaining pins are GND/NC/additional VAC2-USB-input pins
   not used by this design's single-input charge path) and update the
   footprint pad-to-net assignment for the currently-unassigned pads.

10. **Copper zones (GND pour, all 4 layers) are written unfilled.** KiCad
    7.0.11's `ZONE_FILLER.Fill()` reliably segfaults when called from this
    headless Python environment (reproduced in isolation with a trivial
    single-zone board, unrelated to this design's content -- looks like a
    missing GUI-context dependency in this specific KiCad build). The zone
    outlines, layers and net assignment are all correctly written to the
    `.kicad_pcb` file; opening the project in a normal KiCad install and
    saving (or Edit > Fill All Zones, hotkey B) fills them immediately --
    this is standard, expected KiCad behavior and not a sign of an
    incomplete design.
