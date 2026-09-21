# ERC / DRC Status — Rev A audit pass

This document states exactly what electrical-rule and design-rule checking
was actually run against this board, what it found, what was fixed as a
direct result, and what is honestly still outside what this environment
can check. Per the audit brief: **do not claim ERC/DRC passed unless it
actually ran.**

## Tooling reality in this environment

This environment has KiCad **7.0.11** installed via apt (the only version
available — see `docs/assumptions.md` for the network-access constraints
that prevented installing KiCad 8+). In this version:

- `kicad-cli sch erc` **does not exist.** `kicad-cli sch --help` lists only
  `export` as a subcommand. There is no CLI-level schematic ERC in KiCad 7.
- `kicad-cli pcb drc` **does not exist** either. `kicad-cli pcb --help`
  lists only `export`.
- There is **no Python-scriptable `eeschema` module** (`import eeschema`
  fails with `ModuleNotFoundError`), so there is no programmatic path to
  KiCad's real schematic ERC engine in this version.
- There **is** a `pcbnew` Python module, and it exposes
  `pcbnew.WriteDRCReport(board, filename, units, report_all_track_errors)`.
  This was tested against this project's actual board and confirmed to run
  KiCad's real DRC engine (not a stub) — it returns genuine, specific
  violations with rule names, severities, and coordinates, not a
  placeholder. **This is a real DRC run, and its results below are real
  DRC results.**

So: **real PCB-level DRC was run. Real schematic-level ERC was not — no
tool exists in this KiCad 7.0.11 install that can run it, CLI or Python.**
That gap is filled below with a documented, honest, narrower
netlist-derived check — explicitly not presented as equivalent to real
ERC.

## Schematic: ERC-equivalent check (not real ERC)

Since no ERC engine is reachable, `kicad-cli sch export netlist --format
kicadxml` was used to get every net's pin-by-pin electrical types (KiCad
computes and exports these from the schematic's own pin definitions), and
a script (kept at
`/tmp/.../scratchpad/erc_check.py` in this session — not committed, it is
a one-off analysis tool, not project infrastructure) checked the two ERC
violation classes that are mechanically derivable from that data alone:

1. **Driver conflicts** — two or more strict `output`-type pins tied to
   the same net (a real short between two active push-pull drivers).
   **Result: zero.** (An initial pass using a looser definition that also
   counted `bidirectional` and `power_out` pins flagged two nets —
   `/I2C0_SDA` with two `bidirectional` pins, and `/BATT_F` with two
   `power_out` pins on the *same* BQ25792 dual-bonded BAT pin pair. Both
   are false positives: multiple bidirectional pins sharing an I2C bus is
   correct, expected wiring, and a WQFN part's two BAT pads are the same
   physical pin bonded twice for current capacity, not two different
   drivers. Re-run with the correct, stricter definition: zero real
   conflicts.)
2. **Fully floating inputs** — a net containing exactly one node, which is
   an `input`-type pin (i.e. an input with no driver and no other
   connection at all). **Result: zero.**

This check does **not** attempt KiCad's fuzzier ERC classes (power-input-
pin-not-driven / missing PWR_FLAG, etc.) — those need real schematic
semantic context (power symbol placement, hierarchical sheet structure)
that isn't recoverable from a flat netlist export, and claiming to check
them without that context would be exactly the false confidence this
audit exists to avoid.

### A real bug this check did find

Listing every single-node net for manual review (155 of them, mostly
expected NC pins and expected-unrouted signal pins) surfaced something
worth chasing: `J2` pins that were exported with **pin function names
copied from J1** — e.g. `unconnected-(J2-I2C0_SCL-Pad35)`, even though
`design_data.py`'s `CM4_J2_PINS` dict does not assign anything to pin 35
(it is legitimately NC on the J2 half of the connector).

Root cause, confirmed in `python/gen_symbols.py`: the CM4 connector symbol
was generated **once**, from `CM4_J1_PINS` only, and that single symbol
part (`SKYWARD_Custom:CM4_Connector_100`) was instantiated for **both** J1
and J2. Net *wiring* was still correct (each instance's actual net
connections come from `design_data.py`'s per-pin `_add()` calls, keyed by
pin number, which correctly used `CM4_J2_PINS` for J2) — but J2's
schematic pin *labels* were silently J1's, meaning a large fraction of
J2's 100 pins displayed the wrong function name in the schematic and in
any exported netlist/BOM. This is not a wiring defect (nothing was
electrically shorted or misconnected), but it is a real, serious
documentation/debug-safety defect: anyone using the schematic to probe or
rework the physical J2 connector would be looking at the wrong signal
names for most of its pins.

**Fixed**: `gen_symbols.py` now generates two distinct symbol parts,
`CM4_Connector_100_J1` (from `CM4_J1_PINS`) and `CM4_Connector_100_J2`
(from `CM4_J2_PINS`), and `design_data.py`'s J2 `Component` entry now
references the correct one. Re-exporting the netlist after the fix
confirms J2's previously-mislabeled pins now correctly show `NC` (or their
real function, where one exists) instead of an inherited J1 name. Full
project regenerated (symbols → schematic → PCB → routes) and
`python/validate.py` re-run clean (86 components, 71 nets, 307
connections, no errors) after the fix.

## PCB: real DRC results

Run via `pcbnew.WriteDRCReport()` against the final, current
`SKYWARD-COMPUTE-CARRIER.kicad_pcb` (post all fixes below). Full category
breakdown:

| Category | Count | Severity | Status |
|---|---|---|---|
| `unconnected_items` | 220 | — | **Real, expected.** Matches the documented routing gap — see `docs/ROUTING_STATUS.md`. Not a hidden problem; this is the same fact stated from the DRC engine's own perspective. |
| `clearance` | 90 | error | **Real, unresolved — fabrication blocker.** All 90 are pad-to-pad (not track-to-track — see below), i.e. two different-net component pads placed closer than the 0.2 mm default netclass clearance purely from the original footprint placement. Range: 0.012–0.155 mm actual clearance (none are full overlaps after the BQ25792 EP fix below). This needs a placement rework, not something safe to patch blindly this late in the audit — documented here rather than hidden. |
| `lib_footprint_issues` | 82 | warning | **Tooling artifact, not a real defect — see below for the verification.** |
| `silk_overlap` | 7 | warning | **Real, minor, cosmetic.** Silkscreen reference/legend text overlapping other silkscreen (e.g. "CM4" text over the `J1`/`J2` reference, "PIN 1" markers over board-outline artwork, "POWER" text over `F1`'s reference). Does not affect fabrication or function, does affect readability of the assembled board; worth a silkscreen cleanup pass before production. |
| `silk_over_copper` | 1 | warning | **Real, minor, cosmetic.** "DOCK" silkscreen text clipped by solder mask. Same category as above. |

### Three real bugs found and fixed during this audit pass

1. **Router collision-checker bug → real short-circuit-risk track
   crossings.** The first DRC run (before this fix) found `clearance`
   violations with **0.0000 mm actual clearance between tracks on
   different nets** — e.g. `BATT_F` crossing `BOOT_5V`. This traced back
   to a real bug in `gen_routes.py`'s own "verified collision-free" check
   (it missed segments crossing mid-span). Fixed, board re-routed, DRC
   re-run: **zero track-vs-track clearance violations remain.** Full
   detail in `docs/ROUTING_STATUS.md`.
2. **BQ25792 footprint's exposed pad touched real pins.** The same first
   DRC run found two more 0.0 mm clearance violations, both internal to
   the `U3` (BQ25792) footprint: the documented-assumption 2.4×2.4 mm
   exposed/thermal pad touched the bottom-row perimeter pads (SW1/SW2)
   with zero clearance. Fixed by resizing the EP to 1.8×1.4 mm
   (asymmetric, sized specifically against the real perimeter pad
   coordinates to guarantee ≥0.2 mm clearance on every side — see
   `python/gen_footprints.py` and `docs/BQ25792_VERIFICATION.md`). This
   is very likely smaller than the real part's EP (which normatively fills
   most of the space between pad rows on a WQFN), so it remains flagged as
   a dimensional assumption to verify against the TI mechanical drawing —
   but it no longer overlaps neighboring pads.
3. **U4 (TPS5430 5V buck) was missing its catch diode entirely.** Not a
   DRC finding — found during this audit's dedicated power-path review by
   checking whether the buck IC is synchronous (no external diode needed)
   or non-synchronous (needs one), which pin data alone cannot answer.
   Cross-referencing 6 independent open-source TPS5430/5431 designs on
   GitHub confirmed it is non-synchronous and every one of them places a
   Schottky catch diode from the switch node (PH) to GND — without it the
   converter cannot regulate and the switch node can ring past the IC's
   voltage rating. **Fixed**: added D5 (SS34) from `5V0_SW` to `GND`. Full
   detail in `docs/OTHER_COMPONENTS_VERIFICATION.md` and
   `docs/power_architecture.md`. Component/net counts throughout this
   audit (86 components, 307 connections) already include this fix.

The first two were caught **only because real DRC was actually run** —
neither was visible from the router's own reporting or from the earlier
programmatic courtyard/net-mismatch checks. This is the concrete
justification for the audit brief's "never call a board DRC-clean unless
DRC actually ran" rule: this board's own automation had already convinced
itself (wrongly) that it was collision-free twice, and only an independent
DRC pass caught it both times. The third shows the same principle applies
beyond DRC: pin-level verification (confirming a part's pinout) is not the
same as topology-level verification (confirming what external support
circuitry that part's *operating mode* requires) — both are needed, and
neither substitutes for the other.

### `lib_footprint_issues`: verified to be a tooling artifact, not a defect

All 81 warnings read "The current configuration does not include the
library '\<stock library name\>'" (e.g. `Resistor_SMD`, `Diode_SMD`,
`Connector_PinHeader_2.54mm`) for footprints that use KiCad's own stock
libraries. This was investigated rather than assumed:

- **A genuine bug was found and fixed first**: `gen_pcb.py` loaded
  footprints via `pcbnew.FootprintLoad(directory_path, name)`, which
  leaves the footprint's library-nickname field blank (confirmed directly:
  `fp.GetFPID().GetLibNickname()` was empty string immediately after
  load). Fixed by explicitly calling `fp.SetFPID(pcbnew.LIB_ID(lib,
  name))` with the correct nickname after loading. This resolved all 4
  `lib_footprint_issues` warnings for `SKYWARD_Custom`-library components
  (the CM4 connectors, Terra connector, BQ25792) down to zero — proving
  the check mechanism itself works correctly when the library reference is
  reachable.
- **The remaining 81 (for stock KiCad libraries) were tested three
  different ways to rule out a real project misconfiguration**: (1) this
  project's own `fp-lib-table` correctly and appropriately lists only
  `SKYWARD_Custom` — stock libraries are meant to come from each user's
  personal *global* KiCad config, standard behavior for every KiCad
  install, not duplicated per-project; (2) the standard global
  `fp-lib-table` template that ships with this exact KiCad 7.0.11 Debian
  package (`/usr/share/kicad/template/fp-lib-table`) does list all of
  `Resistor_SMD`, `Diode_SMD`, `Connector_PinHeader_2.54mm`, etc. at their
  real, installed paths — confirming the footprints genuinely exist on
  disk and would resolve under any normally-configured KiCad; (3) that
  template was copied into `~/.config/kicad/7.0/fp-lib-table` in this
  session (simulating a first-launch KiCad config) and both the project
  was explicitly loaded via `pcbnew.GetSettingsManager().LoadProject()`
  and DRC re-run — **the warning count did not change**, which shows the
  headless `pcbnew` Python module's DRC path does not consult the global
  library table at all in this KiCad 7.0.11 build, regardless of what's
  configured on disk. This is a limitation of running `pcbnew` standalone
  outside the full GUI application/frame context, not a fixable project
  file issue.

**Conclusion: this warning class is a headless-environment tooling
limitation, verified through three independent tests, not a real
fabrication defect.** Any normally-configured KiCad install (i.e. one
where the GUI has been launched at least once, which auto-populates the
global footprint library table — standard for every real KiCad user) will
resolve these libraries with no warning, exactly as it already does for
this project's own `SKYWARD_Custom` entries.

## What real ERC/DRC did NOT check (and this audit does not claim it did)

- No official schematic ERC ever ran (tool unavailable in this
  environment — see above). The netlist-derived checks above cover driver
  conflicts and fully-floating inputs only, not the full ERC rule set
  (e.g. bus/label consistency at a syntax level KiCad's own parser
  enforces, multi-sheet hierarchy checks — this is a flat, single-sheet
  design so hierarchy checks do not apply here).
- DRC's `unconnected_items` and `clearance` counts are real and current as
  of the routing state described in `docs/ROUTING_STATUS.md` at the time
  this document was written. If routing changes, re-run DRC — do not
  assume these numbers.
- Track width / current-carrying-capacity is a design *choice*
  (documented in `docs/ROUTING_STATUS.md`'s trace-width heuristic), not
  something DRC checks — DRC only enforces the configured clearance/width
  *rules*, it does not validate that a rule is electrically sufficient for
  the current a given net actually carries.
