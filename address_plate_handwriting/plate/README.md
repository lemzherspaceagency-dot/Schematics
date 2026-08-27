# The blend

`build_plate.py` reads `../alyvu_g4_handwriting.json` (the file
`capture_handwriting.py` writes) and fuses the two writers into one piece of
joined-up cursive: `alyvu_g4.svg` (the plate) and `compare.svg` (each hand
next to the blend, for checking).

```bash
python3 build_plate.py                      # uses the defaults below
python3 build_plate.py --weight 0.3         # 30% toward the second writer
python3 build_plate.py --height-mm 45 --stroke-min-mm 1.0 --stroke-max-mm 2.6
```

Every run prints a per-writer report first: sample/stroke/point counts,
pressure mean and peak, total ink time, the slant it measured, and any role
(crossbar, ogonek, g, period, four) it couldn't find cleanly in any sample.

## How the fusion works

1. **Normalise.** Every sample is put in the same frame: baseline at y=0, y
   flipped to point up, scaled so one x-height = 1.0. Both writers now live
   on the same footing regardless of how big either of them wrote.
2. **Segment.** Each sample's strokes are sorted into six roles by position
   and shape: the flowing word itself (`body`), the A's `crossbar`, the
   `ogonek` hook under ų, the `g`, its `period`, and the `four`. Real
   handwriting doesn't always draw every role the same way twice — a
   crossbar might get merged into the body stroke, an ogonek might be
   skipped — so a role missing from one sample is just filled in from
   whichever of that writer's other samples has it.
3. **Average within a writer.** A writer's own 2-3 repeats of the same role
   are resampled by arc length and averaged together, which cancels out
   ordinary hand tremor and gives one clean shape per writer per role.
4. **Measure slant separately.** Per-segment angle is far too noisy on a
   curvy cursive line (a loopy stroke has near-vertical segments pointing
   in every direction). Instead, slant comes from whichever raw strokes are
   long, straight and steep — a stem, an ascender — using each stroke's
   own start-to-end direction, weighted by how much vertical distance it
   covers.
5. **Match and blend.** Each writer's averaged role gets un-sheared to
   upright, then matched to the other writer's version of the same role
   with dynamic time warping (in a size-invariant space, so a writer who
   writes bigger doesn't just win) and mixed point-for-point at `--weight`.
   The **g** gets special handling: it's really two loops (a bowl above the
   baseline, a tail below it) joined by a stem, and the two people can
   spend very different fractions of their pen time on each half, in
   either order. Matching the whole path index-for-index conflates the two
   loops and the blend collapses into a small blob. Splitting at the
   baseline, blending the bowl to the bowl and the tail to the tail, and
   stitching the result back together avoids that.
6. **Re-lean.** The blended weight of the two writers' slants is applied
   once, to the finished shape.
7. **Width from pressure.** `width = stroke-min + (stroke-max - stroke-min)
   * pressure ** gamma`, per point, from the blended pressure trace.
8. **Scale to size and export.** The whole composition is scaled so its
   ascender-to-descender height matches `--height-mm`, then written out as
   an SVG in real millimetres with two layers: `centreline` (thin reference
   lines) and `outline` (the actual filled, cuttable shape).

## Flags

| Flag | Default | What it does |
|---|---|---|
| `--weight` | 0.5 | 0.0 = first writer only, 1.0 = second writer only |
| `--height-mm` | 60 | letter-block height, ascender to descender |
| `--stroke-min-mm` | 1.2 | width at the lightest recorded pressure |
| `--stroke-max-mm` | 3.2 | width at full pressure |
| `--gamma` | 1.0 | pressure curve; >1 leans thin, <1 leans thick |
| `--margin-mm` | 12 | white space kept around the text |
| `--no-outline` | off | skip the filled layer, keep only the centreline |
| `--out` | `alyvu_g4.svg` | plate output path |
| `--compare-out` | `compare.svg` | comparison output path |

If more than two writers are ever in the capture file, the first two
(alphabetically) are used and the rest are named but ignored.

## Before you cut anything

- **Check `compare.svg` first.** It's the fast way to see whether the blend
  actually looks like a fusion of both hands rather than a distortion of
  either one.
- **1.2mm is already thin** for most laser or CNC engraving. If your
  shop's minimum is higher, raise `--stroke-min-mm` (and probably
  `--stroke-max-mm` to keep the same ratio) before sending the file out.
- **The outline layer can self-overlap at sharp cusps** — a tight turn
  where the letter reverses direction can pinch the offset polygon into a
  small self-intersection (visible as a tiny gap or notch right at the
  cusp, e.g. the top of a tall stroke). This is a known limitation of
  offsetting a centreline directly rather than doing a full polygon union.
  It's cosmetic in the vast majority of letters here, but before cutting,
  zoom into the sharp points and, if a shop's software is picky about
  self-intersecting paths, run the `outline` layer through a "union" /
  "simplify path" operation in Inkscape or similar first.
- Nothing here reads a font or any file outside the capture JSON — every
  curve you see came from the two of you actually writing it.

## Needs

Python 3 and `numpy`. Nothing else — no fonts, no network, no ML.
