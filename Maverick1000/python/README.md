# Python generators — SKYWARD-COMPUTE-CARRIER

Everything in this folder is a real code generator, not a mockup. The whole
KiCad project is reproducible from scratch by running these in order:

```
python3 validate.py          # sanity-checks design_data.py (no shorts, no orphans)
python3 gen_symbols.py       # -> kicad/libraries/symbols/SKYWARD_Custom.kicad_sym
python3 gen_footprints.py    # -> kicad/libraries/footprints/SKYWARD_Custom.pretty/*.kicad_mod
python3 gen_schematic.py     # -> kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_sch
python3 gen_pcb.py           # -> kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb
python3 gen_project.py       # -> .kicad_pro, sym-lib-table, fp-lib-table
python3 gen_bom.py           # -> bom/BOM.csv
```

Requires KiCad's own Python (`pcbnew` module) and a KiCad 7 symbol/footprint
library install (this was built and tested against KiCad 7.0.11 on Ubuntu
24.04, `apt install kicad kicad-symbols kicad-footprints`).

## File map

- **`design_data.py`** — the single source of truth: every component
  (with real manufacturer part numbers) and every net. Both the schematic
  and the PCB are generated from this one file, so they cannot disagree
  with each other. If you need to change a connection or add a part, edit
  this file and re-run the generators above.
- **`libparse.py`** — parses real KiCad `.kicad_sym` files (stock and our
  custom library) to get authoritative pin numbers/names/electrical types.
  Used so this project's nets are checked against the *actual* library
  data, not hand-typed pinouts.
- **`symgen.py`** — renders every symbol used in the schematic (stock or
  custom) as a simple, uniform rectangle-with-pins symbol using the real
  pin data from `libparse`. This sidesteps correctly resolving KiCad's
  `extends` inheritance on hand-drawn stock symbol artwork; it does **not**
  affect electrical correctness (pin numbers/names/types are preserved
  exactly), only cosmetic appearance.
- **`gen_symbols.py`**, **`gen_footprints.py`** — build the custom parts
  not in KiCad's stock libraries: the CM4 100-pin connectors, the Terra
  22-pin connector, and simplified LM74610 / BQ25792 symbols.
- **`gen_schematic.py`** — hand-authors the `.kicad_sch` S-expression file:
  places every component, draws a stub wire + net label at every used pin
  (same-named labels are electrically one net on a flat sheet in KiCad),
  places a no-connect flag on every unused pin, and adds a `PWR_FLAG`
  wherever a net would otherwise fail ERC's "power pin not driven" check.
- **`gen_pcb.py`** — uses the real `pcbnew` Python API to build the
  `.kicad_pcb`: loads real footprints, places them in a deliberately
  zoned, collision-checked layout, draws the board outline + mounting
  holes, adds silkscreen identification, and defines (unfilled) GND zones
  on all 4 copper layers. See `docs/assumptions.md` for what's
  intentionally left for interactive completion (copper routing, zone
  fill) and why.
- **`gen_project.py`** — writes `.kicad_pro` plus project-local
  `sym-lib-table` / `fp-lib-table` so the custom library resolves via a
  relative path (`${KIPRJMOD}/...`), making the whole `kicad/` folder
  portable to any machine.
- **`gen_bom.py`** — derives `bom/BOM.csv` directly from `design_data.py`.
- **`validate.py`** — catches typos in `design_data.py` before they become
  bad copper: unknown refs, a pin wired into two nets (a short), a
  component with zero connections, duplicate reference designators.

## Debugging notes worth keeping

Two real bugs were found and fixed during development by cross-checking
`kicad-cli sch export netlist` output against `design_data.NETS`
pin-for-pin (see `git log` / the comments in `symgen.py` and
`gen_schematic.py`):

1. A symbol's local pin Y offset must be **subtracted** from the placed
   instance's Y (not added) — KiCad's library coordinate convention has
   Y+ up, but sheet placement is Y+ down.
2. Never derive a pin coordinate by dividing an odd multiple of a
   sub-0.01mm-precision pitch by 2 (e.g. `49 * 1.27 / 2 = 31.115`) — the
   3rd decimal digit rounds inconsistently depending on whether KiCad sums
   two independently-rounded numbers or this generator rounds a single
   unrounded sum, silently reassigning a wire to the wrong physical pin.
   Every coordinate in `symgen.py` is now a clean integer multiple of the
   pitch, so this class of bug cannot recur.

Both were caught, not shipped — see `python/validate.py`'s companion
cross-check performed against the exported netlist before this project was
considered done.
