# Quad-Wash Ingot Factory

A Create-mod Schematicannon-compatible structure, generated programmatically
with Python + [nbtlib](https://pypi.org/project/nbtlib/) from
`build_schematic.py`. The output file is `quad_wash_ingot_factory.nbt`.

This uses the **same NBT schema Minecraft structure blocks use** (`size`,
`entities`, `blocks`, `palette`, `DataVersion`), which is also the schema
Create's own Schematic & Quill and Schematic Table save/load — that's why a
Create schematic can be dropped straight into a world's `schematics/`
folder and picked up by the Schematic Table, without going through a
structure block at all.

## Where to put the file

Create loads schematics from a `schematics` folder **inside the save
you're playing**, not a global `.minecraft/schematics` folder:

- **Singleplayer:** `.minecraft/saves/<Your World Name>/schematics/`
- **Server:** `<server root>/world/schematics/` (or whatever your
  `level-name` is set to)

Create creates this folder automatically the first time you open a
Schematic Table or Schematicannon in that world, so if it doesn't exist
yet, open either of those once and it will appear.

Copy `quad_wash_ingot_factory.nbt` into that folder, then:

1. Open a **Schematic Table**, place the file in its input slot, and let it
   process — this generates the placeable "Schematic" item.
2. Place the resulting schematic item in the world with a **Schematicannon**
   loaded with Shulker Shells / Sand / Gunpowder (whatever your Create
   version uses for the printing recipe), aim, and fire.

(If your Create build also exposes a raw `/create schematic` or "Schematic
File Loader" style flow, the same file works there too — it's a standard
structure NBT file, nothing Create-specific about the container format.)

## Layout

- **X axis** — four parallel lanes: Iron, Gold, Copper, Zinc (in that
  order, 3 blocks apart).
- **Z axis** — process stages, low→high: gravel distribution → wash
  basin/water wheel → nugget merge belt → filtered diversion → mechanical
  press → ingot chest.
- One shared kinetic **spine** (shaft/gearbox/cogwheel trunk) runs the
  length of the build. The 4 water wheels are the *only* power source in
  the schematic and drive the millstone and all 4 presses through it.

Flow: `lava+water → cobblestone → (millstone) → gravel → 4× (basin +
water wheel) → washed nuggets → merge belt → 4× brass funnel (filtered) →
side belt → (mechanical press + basin) → ingot → labeled chest`. Anything
that passes all 4 filters unmatched is lifted onto an elevated belt and
looped back to the millstone's input.

Total footprint: 26 × 6 × 9 (X × Y × Z).

## What to double-check in-game

Create's exact block/NBT schema shifts between versions (0.4 vs 0.5 vs
0.6, 1.18 vs 1.19 vs 1.20 ports), and some of this genuinely cannot be
verified without loading it in your specific version. In rough order of
"most likely to need a fix":

1. **Belts are the single biggest risk.** A working multi-block Create
   belt normally gets its start/middle/end pulley linkage and internal
   item-position data written by the game itself when you place it with a
   Wrench/Belt Connector — that link isn't fully reconstructable by hand
   from `part`/`facing`/`slope` blockstate values alone. The belts here
   are placed with what I'm confident are the right property *names and
   values* for a straight run, but if a belt run doesn't move items after
   printing, the fix is usually: break the belt run and re-drag a new one
   with a Belt Connector (or Wrench) rather than debugging the NBT. This
   applies to Spine A, Spine B, the 4 diverting belts, the elevated
   leftover-return belt, and the collector belt.

2. **Funnel filters** (`Filter` / `FilterMatchNBT` tags on the 4 brass
   funnels). I've written these using the item-filter schema I'm most
   confident matches Create's `FilterItemStack` behavior, but the exact
   tag name/shape has changed before (e.g. some versions wrap it
   differently, or use a `filters` list for multi-slot filters like the
   Attribute Filter). If a funnel places unfiltered, just right-click the
   matching nugget onto the funnel in-game (Iron/Gold/Copper/Zinc nugget
   → the funnel at each lane's filter position) — it's a 5-second fix per
   funnel.

3. **Water Wheel + Basin stacking.** Each wash basin has a water wheel
   directly above it and a water source directly above the wheel, on the
   theory that the wheel is non-solid to fluids and the flow reaches the
   basin to trigger the washing recipe while also spinning the wheel. If
   washing doesn't trigger, the water source may need to sit adjacent to
   the wheel instead of stacked through it — try moving the water block
   beside the wheel, or add a second water source directly touching the
   basin.

4. **Millstone / Mechanical Press power input side.** I've assumed both
   accept rotational power from *any* adjacent kinetic block regardless of
   axis (true for most "simple" Create kinetic consumers). If a millstone
   or press doesn't spin after printing, check the kinetic stress/RPM
   overlay (goggles or the stress-meter item) and relocate that one
   adjacent shaft/gearbox if needed.

5. **Deployer** at the cobblestone generator is placed and powered-off —
   it has no item and no mode set (Deployer inventory/mode NBT is one of
   the tags most likely to have shifted format across versions, so I
   didn't guess it). Right-click a pickaxe into it and set it to **Punch**
   mode with a Wrench. Alternatively just mine the generated cobblestone
   by hand and toss it onto the belt beside it — the rest of the line is
   fully automatic either way.

6. **Basin auto-output.** Each wash basin and each press basin is assumed
   to drop its result straight down onto the belt directly beneath it
   with no funnel needed (standard Create behavior for basin recipes). If
   items pile up in a basin instead of flowing onward, add a down-facing
   funnel under it.

7. **Mechanical Press `facing`.** Placed as `facing=down` (pressing
   downward into the basin below) — this is the standard orientation, but
   if your version doesn't expose a `facing` property on this block at
   all, Minecraft will just fall back to its default blockstate and the
   press should still work; you shouldn't need to fix anything, but it's
   worth a glance.

8. **`DataVersion`** is set to `3465` (Minecraft 1.20.1 / a common
   Create 0.5.1 target). Create's schematic loader is generally forgiving
   about this, but if you're on a different Minecraft version and
   anything looks off after printing, that's the first thing to check.

None of the above should stop the schematic from **loading and printing**
— worst case, some belts/funnels/wiring need a quick manual touch-up
after the Schematicannon finishes, exactly as flagged above.

## Regenerating

```
pip install nbtlib
python3 build_schematic.py
```

The script keeps every block placement in a single Python dict keyed by
`(x, y, z)` and raises immediately on any coordinate collision, so it's
safe to tweak coordinates/properties and re-run.
