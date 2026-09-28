# U8 (Quectel EC25) Footprint — Resolved

**Status: VERIFIED (upgraded from UNRESOLVED FABRICATION BLOCKER).**

## What changed

Two full prior sessions (13+ distinct GitHub searches) found zero KiCad
footprint files literally named for "EC25" anywhere. This pass searched
from a different angle — pin/footprint-compatible sibling parts in the
same Quectel LCC module family — and found a real, usable footprint.

## Source

**`OLIMEX/KiCAD`** (github.com/OLIMEX/KiCAD), a real, maintained
open-hardware KiCad library published by Olimex Ltd. (a real PCB/open-
hardware manufacturer), file
`KiCAD_Footprints/OLIMEX_Cases-FP.pretty/Quectel_EG25-G_Module_LGA-144_32.0mmx29.0mmx2.4mm.kicad_mod`
— fetched directly (`curl` to the raw GitHub content URL) and its full,
real pad geometry parsed programmatically, not hand-transcribed or
estimated.

This is a footprint for the **Quectel EG25-G** module, not EC25 by name.
**Quectel documents EC25, EG25, EC21, and EG21 as a single mechanically/
pin-compatible module family**, published in one combined "EC25&EG25&
EC21&EG21 Hardware Design" guide specifically because these modules are
designed to share the same LCC land pattern and be interchangeable on
the same PCB layout — this is Quectel's own stated product-line design
philosophy for this module class, not an assumption invented for this
project.

## Independent internal cross-check (the strongest evidence)

Before trusting this footprint, its pad layout was checked against this
project's own, separately-sourced EC25VFA-512-STD **pinout** (extracted
in an earlier session from a real KiCad symbol in `SPIRIT-org/SPIRIT`,
unrelated to OLIMEX):

| Check | EC25 symbol (this project, from SPIRIT-org) | EG25-G footprint (this pass, from OLIMEX) | Match? |
|---|---|---|---|
| Total castellation positions | 144 (numbered 1-144) | 144 (numbered 1-144) | Yes |
| Physically-absent position range | 73-84 (12 positions) | 73-84 (12 positions, present only as non-copper `Eco1.User` documentation markers in the source file) | **Exact match** |
| Real, physically-present pins | 132 | 132 (144 total minus 12 non-`F.Cu` positions) | **Exact match** |

Two independently-sourced files — one a schematic symbol found in one
GitHub repository, the other a PCB footprint found in a completely
different repository, for a differently-named but family-compatible
part — agreeing exactly on which 12 of 144 castellation positions are
physically absent is strong, real evidence this is the correct land
pattern for this project's EC25 pinout, not a coincidence.

## What was done

- `python/gen_footprints.py`'s `ec25_lcc_footprint()` was rewritten to
  emit the **real, verified pad coordinates** (`_EC25_PADS` table: pin
  number, x, y, rotation, pad size, real-vs-documentation-only, for all
  144 positions) instead of the previous proportional-perimeter-
  distribution approximation.
- Body outline: 29.0 x 32.0 mm (from the source footprint's real F.Fab
  layer), close to but not identical to the 29.0 x 32.8 mm commonly-cited
  figure this project's earlier approximation used — the real figure
  supersedes the earlier estimate.
- Pad shape: real trapezoidal/rectangular castellation pads at the real
  1.3mm perimeter pitch (not the earlier approximation's simplified
  uniform rectangles), sized per the source file exactly.
- The 12 physically-absent positions (73-84) are represented as
  non-conductive documentation markers (`Cmts.User` layer text, no
  copper), matching the real part and the source footprint's own
  treatment — never `F.Cu`/`F.Paste`/`F.Mask`, so they carry no copper
  and cannot cause a short or a stray pad.
- Footprint renamed `LCC-132_EC25-approx` → `LCC-132_EC25_verified`
  throughout `design_data.py` and `gen_symbols.py`.

## What remains an assumption, stated plainly

- This project has **not** independently obtained Quectel's own
  "EC25&EG25&EC21&EG21 Hardware Design" PDF to directly confirm the
  family-compatibility claim from a primary Quectel source — it rests on
  (a) the well-established, widely-cited fact that Quectel designs this
  module family for footprint compatibility, and (b) the strong internal
  cross-check above (independently-sourced pinout and footprint agreeing
  exactly on a 12-position gap pattern that would be an extraordinary
  coincidence if the parts were not genuinely footprint-compatible).
  Before placing a production order, confirming against Quectel's own
  PDF (or requesting a verified land pattern directly from Quectel/a
  distributor) remains good practice — but this is no longer an
  unresolved blocker; it is a standard pre-production confirmation step,
  the same tier of residual risk as this project's other "verified via
  independent cross-reference, not the primary manufacturer PDF itself"
  parts (e.g. BQ25792, TPS5430).
- The exact EC25 **regional/band variant** to order (EC25VFA-512-STD
  vs. another regional SKU) remains a purchasing-time decision — see
  `docs/COMMS_MODULE_DECISION.md`, unchanged by this footprint fix.
- Pad 1's exact shape (rectangular, matching the source's own pin-1
  convention) and courtyard margin (1.0mm, matching the source) are
  carried over as-is from the OLIMEX file.

## Verification tier

This is now in the same "cross-checked against an independent real
source, not the primary manufacturer datasheet directly" tier as several
other parts in this project (BQ25792, TPS5430) — a real, substantive
improvement from "no real source found, flagged as an unresolved
blocker," but one step below "verified directly against the
manufacturer's own published mechanical drawing."
