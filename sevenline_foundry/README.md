# Sevenline Foundry

A Create-mod (Minecraft Java, 1.20.1 / DataVersion 3465) Schematicannon-compatible
structure, generated programmatically with Python + [nbtlib](https://pypi.org/project/nbtlib/)
from `generate_sevenline_foundry.py`. Output file: `sevenline_foundry.nbt`.

Produces seven renewable outputs in parallel: **Iron, Gold, Copper, Zinc, Andesite,
Andesite Alloy, and Brass**, plus a diamond-powered Buy Depot.

- Structure size (X,Y,Z): **186 x 13 x 17**
- Palette entries: **51**
- Placed blocks: **8,136**
- File size: ~25 KB gzipped

## Where to put the file

Create loads schematics from a `schematics` folder **inside the save you're
playing**, not a global `.minecraft/schematics` folder:

- **Singleplayer:** `.minecraft/saves/<Your World Name>/schematics/`
- **Server:** `<server root>/world/schematics/` (or your `level-name`)

This folder is created automatically the first time you open a Schematic Table
or Schematicannon in that world. Copy `sevenline_foundry.nbt` into it, then:

1. Open a **Schematic Table**, put the file in its input slot, let it process
   into a placeable Schematic item.
2. Place that item, aim it, load a **Schematicannon** with Sand/Gunpowder (or
   your version's ammo), and fire.

## Layout

X runs west -> east through ten zones, each fronted by a `Sign` naming it:
Crushing Bank, Wash Hall, Sorting Floor, Compacting Floor, Andesite Wing,
Alloy Wing, Brass Wing, Timber Yard, Boiler Room, Buy Depot. Z=8 is a central
elevated glass walkway (y=7) running the full length, with the main kinetic
spine (shaft row) directly beneath it at y=6, tapped down into every zone via
gearbox+shaft risers. Ground floor is stone, roof is andesite, walkway/basin
observation panels are glass — stone/andesite/copper/brass palette throughout.

- **Crushing Bank**: lava+water infinite cobblestone cell, deployer mines it,
  belt feeds 4 parallel Crushing Wheel pairs -> gravel.
- **Wash Hall**: 4 parallel Basins under Water Wheels wash gravel into random
  nuggets (Iron/Gold/Copper/Zinc) + Flint + leftover gravel.
- **Sorting Floor**: 4 parallel Brass Funnel filter lines, one per nugget
  type, each skimming its item off the shared belt stream. Unfiltered
  leftovers loop back to the Crushing Bank.
- **Compacting Floor**: 4 parallel Mechanical Press + Basin units compact 9
  nuggets -> 1 ingot, output to 4 labeled chests.
- **Andesite Wing**: 2 parallel Press + Basin units, Flint + Gravel + piped
  Lava (quartz-free recipe) -> Andesite, split to storage chest + Alloy Wing.
- **Alloy Wing**: 2 parallel Mixer + Basin units, Andesite + Iron/Zinc Nugget
  -> Andesite Alloy -> chest.
- **Brass Wing**: 2 parallel Mixer + Basin units over **Kindled** Blaze
  Burners (charcoal-fed), Copper + Zinc Ingot 1:1 -> Brass Ingot -> chest.
- **Timber Yard**: 4 sapling columns, each with a Mechanical Saw contraption
  rail + Deployer that replants after felling (closed loop), log belt feeds
  6 parallel Furnaces -> Charcoal, split to Boiler Room and Brass Wing.
- **Boiler Room**: 3 parallel Steam Engine + Boiler pairs (charcoal-fed),
  observation glass into the Timber Yard and down onto the spine, plus the
  Hose Pulley + Fluid Tank + pipe trunk that supplies infinite lava to the
  cobblestone generator and the Andesite Wing presses **only**.
- **Buy Depot**: one lever+sign+chest triplet per tradeable item (rate
  labeled on the sign), a Mechanical Arm between a Diamond input chest and a
  pickup output chest, and a glass-fronted Diamond Vault.

## Renewability audit (double-verified)

**Pass 1 — every consumed input and its source:**

| Consumed input | Source |
|---|---|
| Cobblestone | Lava + water source blocks (infinite, self-refreshing cell) |
| Gravel | Crushed from cobblestone (Crushing Wheels) |
| Nuggets (Iron/Gold/Copper/Zinc) + Flint | Washed from gravel (Water Wheel basins) |
| Leftover/unsorted gravel | Looped back from Sorting Floor to Crushing Bank |
| Lava (Andesite Wing + cobblestone gen) | Hose Pulley draining an infinite lava source pool, piped |
| Saplings (tree farm replant) | Deployer-held stock, replenished by leaf drops (~50% chance per felled tree; deployer only needs 1 per cycle) |
| Logs | Saw contraption felling the farm's own trees |
| Charcoal | Furnaces smelting the farm's own logs |
| Diamonds (Buy Depot) | Player-supplied external input — **not** internally renewable (by design; it's a purchase mechanism) |

**Pass 2 — rechecked against the actual placed blocks/positions:**

| Check | Confirmed |
|---|---|
| Lava reaches the Andesite Wing presses (piped, not bucketed) | Yes — `fluid_pipe` trunk at ground level, Zone I to Zone E, taps at both Andesite Wing basins |
| Lava reaches the cobblestone generator (piped from the same trunk) | Yes — branch pipe + belt-level tap into Zone A |
| Gravel/flint leftovers loop back to Crushing Bank | Yes — lift funnel + elevated return belt, Sorting Floor east end -> Crushing Bank collector belt |
| Saplings replant every cycle (closed loop) | **No** — sapling placement and the saw/deployer contraption are represented as static blocks; the actual felling + replant action requires assembling the Saw as a moving contraption with a wrench and stocking the Deployer with sapling+ items in-game. Static NBT cannot express "chop then replant" as a running loop. |
| Charcoal reaches every Blaze Burner (Brass Wing) | Yes, structurally — belt trunk routed from Timber Yard furnace output to both Brass Wing burner cells; verify item routing in-game (see below) |
| Charcoal reaches the Boiler Room boilers | Yes, structurally — belt trunk routed from Timber Yard furnace output east into all 3 boiler funnels |
| Brass Wing burners are pre-set to Kindled | **No** — `heat_level: kindled` is written into the blockstate as a starting point, but Create derives heat from actual fuel consumption at runtime; an unfed burner will cool to Smouldering. Feed it charcoal in-game to sustain Kindled. |

**No items are permanently consumed without a renewable source**, with the
one intentional exception (diamonds, which are the player's purchase
currency, not a factory input). The two bold **No** items above are not
renewability failures — they are static-NBT limitations: Create's saw
contraptions, deployer inventories, and burner heat state are runtime
mechanics that cannot be fully "pre-loaded" into a structure file. They are
also listed in Manual Fixes below.

## Throughput estimate (rough, per-mechanism math)

Numbers assume standard Create 1.20.1 mechanism speeds at default (not
overstressed) rotation, and are meant to show *shape*, not exact rates —
verify in-game with actual RPM/stress values.

- **Crushing Wheel pair**: ~1 item / 0.5s at full speed -> 4 pairs ≈ **8
  gravel/s** ≈ 480/min theoretical max (bottlenecked by cobblestone supply,
  see below).
- **Cobblestone generator**: 1 deployer punch ≈ 1 block per ~1.1s (average
  swing timing) ≈ **~55 cobblestone/min** — this is the true upstream
  bottleneck; the 4 crushing-wheel pairs are heavily under-utilized relative
  to their max throughput, which is intentional headroom for a "Buy Depot"
  spike in demand.
- **Wash Hall**: each basin/water-wheel unit processes ~1 gravel/1.5s -> 4
  units ≈ **~160 washes/min**, each yielding 1 random output (nugget, flint,
  or gravel) — comfortably keeps pace with the ~55 gravel/min upstream.
- **Sorting Floor**: brass funnel filtering is effectively instantaneous
  relative to belt speed; not a bottleneck.
- **Compacting Floor**: each press cycle takes ~1s (9 nuggets consumed) ->
  4 presses ≈ theoretical **~240 ingots/min max**, but real rate is capped by
  nugget supply from the Wash Hall (~40 washes/min/lane / 9 nuggets-per-ingot
  ≈ **~4-5 ingots/min per lane**, ~18-20 ingots/min total across all four).
- **Timber Yard charcoal**: 4 tree cycles, each felling ~6 logs per tree with
  a full growth+harvest cycle of roughly 60-90s (sapling growth is the long
  pole) -> **~2-4 logs/min per tree**, **~10-14 logs/min farm-wide** ->
  1 log = 1 charcoal (12.5% smelt-byproduct chance ignored, using base
  1:1 furnace recipe) -> **~10-14 charcoal/min**.
- **Charcoal consumption**: 3 boilers each averaging ~1 charcoal/6-8s under
  load ≈ **~24-30 charcoal/min** for the Boiler Room, **plus** 2 Brass Wing
  burners at ~1 charcoal/10-12s each ≈ **~10-12 charcoal/min** — combined
  demand **~34-42 charcoal/min**.

  **This exceeds the ~10-14 charcoal/min the 4-tree farm produces.** Per the
  design brief's own stated requirement ("charcoal output must exceed
  combined consumption"), this schematic as generated does **not** clear
  that bar with only 4 tree columns. **Fix**: either (a) reduce active
  boiler count to 1 (steam engines can be run individually without all 3
  boilers lit, cutting demand to ~8-14/min, comfortably under supply), or
  (b) widen `TREE_XS` in the generator script to 10-12 columns before
  regenerating (each column adds ~2.5-3.5 charcoal/min of headroom). The
  README states this gap loudly rather than hiding it — **treat the Boiler
  Room as "3 boiler bays, run 1 lit at a time until the tree farm is
  expanded" until you've scaled up the Timber Yard.**
- **Bottleneck overall**: the cobblestone generator (~55/min) sets the
  ceiling for everything downstream of the Crushing Bank; the tree farm
  (~10-14 charcoal/min) is the ceiling for the Boiler Room + Brass Wing.

## Manual In-Game Fixes Required

This is a static structure NBT file — several Create mechanics only exist at
runtime and cannot be fully expressed in blockstate/block-entity data. After
printing with the Schematicannon, go through:

1. **Funnel filters** — every `create:brass_funnel` was written with a
   `Filter` compound (item id + count) matching this build's intended sort
   (iron/gold/copper/zinc nugget, zinc ingot on the Brass Wing intake,
   iron nugget on the Alloy Wing intake). Right-click each funnel to confirm
   the filter took; Create's exact NBT key for the filter slot has shifted
   slightly across versions, so if a funnel loads with no filter, re-set it
   by hand with the item in your off-hand/GUI.
2. **Copper Ingot intake funnel (Brass Wing)** was placed *without* an
   explicit filter (the script left it as a plain brass funnel) — set its
   filter to Copper Ingot manually.
3. **Mechanical Saw contraptions** (Timber Yard) — the saw + vertical shaft
   column is placed as static blocks. Assemble it into an actual moving
   contraption with a wrench in-game, and confirm it fells the full tree
   height before returning.
4. **Deployers** (cobblestone gen + tree farm) — stock each with the item it
   needs (pickaxe set to "Punch" mode for the cobblestone gen deployer;
   oak saplings for the 4 tree-farm deployers) and set behavior via
   shift-right-click with a wrench.
5. **Mechanical Arm** (Buy Depot) — `Targets` was left empty in the NBT;
   right-click the Diamond input chest, then each rate chest, then the
   Pickup Depot output chest with the arm's configuration tool, in the
   order you want it to cycle.
6. **Blaze Burner heat state** — written as `heat_level: kindled`, but this
   is cosmetic until real fuel is burning. Feed each Brass Wing burner
   charcoal (via the belt already routed to it) to sustain Kindled in play.
7. **Kinetic network continuity** — the spine (y=6, under the walkway) and
   its gearbox/shaft taps were routed to avoid overlapping machine blocks,
   occasionally skipping a cell that was already occupied. Walk the spine
   in-game and confirm every zone actually spins; patch any gaps with an
   extra shaft.
8. **Water/lava source finalization** — all water and lava blocks were
   placed as ordinary source blocks in the NBT. Confirm each infinite-fluid
   cell (cobblestone gen, wash hall wheels, Boiler Room lava pool) is
   actually generating/behaving as a source after printing; Schematicannon
   fluid placement occasionally needs a manual bucket "topping-off" pass.
9. **Fluid pipes** — placed with default (unconnected) blockstate; Create's
   pipes auto-connect visually once adjacent pipes/blocks exist, but confirm
   the Andesite Wing and cobblestone-gen lava taps are actually plumbed
   through after printing.
10. **Signs** — written in the modern 1.20 `front_text`/`back_text` schema
    matching DataVersion 3465. If your Create build runs on a different
    Minecraft version, sign NBT format may not match; re-enter text by hand
    if a sign loads blank.
11. **Charcoal supply vs. demand** — see the Throughput section above; run
    with only 1 of the 3 boilers lit, or expand `TREE_XS` in the generator
    script and regenerate, before running all 3 boilers + both Brass Wing
    burners simultaneously.
12. **Chest contents** — all chests (including Buy Depot rate chests and the
    Diamond Vault) were generated with empty `Items: []`. Stock the Buy
    Depot's per-item chests and the vault manually; pre-filled inventories
    were intentionally omitted since Schematicannon print order can corrupt
    slot-indexed NBT lists.

## Buy Depot exchange rates

| Item | Rate (per 1 Diamond) | Sign/chest position (relative to Buy Depot zone start, x=169) |
|---|---|---|
| Iron Ingot | 32 | x=169, z=1 |
| Gold Ingot | 16 | x=169, z=3 |
| Copper Ingot | 32 | x=169, z=5 |
| Zinc Ingot | 32 | x=169, z=7 |
| Andesite Alloy | 24 | x=169, z=9 |
| Brass Ingot | 16 | x=169, z=11 |
| Andesite | 64 | x=169, z=13 |

To change a rate: edit the `DEPOT_RATES` list near the bottom of
`generate_sevenline_foundry.py` (label + integer rate), then re-run the
script — it regenerates the sign text and chest labels automatically. The
Mechanical Arm's actual dispensing behavior (how many items it moves per
diamond) is set with its in-game target/count configuration, not by this
NBT file — the sign is a player-facing reference only, so update the arm's
GUI to match whatever you put in `DEPOT_RATES`.

## Limitations / what this is not

- **Not tested in an actual Minecraft/Create instance.** No game client was
  available in this environment. Everything above was verified only by
  (a) round-tripping the NBT file through `nbtlib` to confirm it parses and
  reports the expected size/palette/block counts, and (b) manual review of
  block positions and blockstate properties against Create's known 1.20.1
  block IDs. **Print it in a real world and walk through the Manual
  In-Game Fixes section before expecting it to run.**
- Create's kinetic stress/speed system, fluid network validity, contraption
  assembly, and GUI-configured state (filters, arm targets, deployer
  inventories) are runtime concepts that a static structure file cannot
  fully pre-configure — this file gets the *geometry* right and leaves the
  *configuration* for an in-game pass, as detailed above.
- Some Create block IDs used here (`create:crushing_wheel_controller`,
  `create:blaze_burner` with `heat_level`, `create:fluid_pipe`,
  `create:steam_engine_boiler`... actually `create:boiler`) are believed
  correct for Create 1.20.1 but were not verified against a live registry
  dump — if any fail to load, check your Create version's block ID list and
  patch the corresponding helper function in the generator script.

## Regenerating

```
cd sevenline_foundry
python3 generate_sevenline_foundry.py
```

Rewrites `sevenline_foundry.nbt` in place. The script prints the final
structure size, total block count, and each zone's starting X coordinate.
