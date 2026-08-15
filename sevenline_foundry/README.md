# Sevenline Foundry

A Create-mod (Minecraft Java 1.20.1, DataVersion 3465) Schematicannon-compatible
structure, generated programmatically with Python + [nbtlib](https://pypi.org/project/nbtlib/).

| | |
|---|---|
| Output file | `sevenline_foundry.nbt` |
| Structure size (X, Y, Z) | **266 x 17 x 31** |
| Blocks placed | **23,314** |
| Palette entries | 60 |
| File size | ~71 KB gzipped |
| Generator | `generate_sevenline_foundry.py` |
| Verifier | `verify_sevenline_foundry.py` |

---

## Where to put the file

Create loads schematics from a `schematics` folder **inside the world you are
playing**, not a global one:

- **Singleplayer:** `.minecraft/saves/<Your World Name>/schematics/`
- **Dedicated server:** `<server root>/<level-name>/schematics/` (usually `world/schematics/`)

The folder is created the first time you open a Schematic Table or Schematicannon
in that world. Then:

1. Copy `sevenline_foundry.nbt` into that folder.
2. Open a **Schematic Table**, put a blank Schematic (or empty slot) in, and pick
   `sevenline_foundry` from the list — it writes a placeable Schematic item.
3. Hold the Schematic, position/rotate it, confirm placement.
4. Put the Schematic into a **Schematicannon**, feed the cannon materials + gunpowder,
   and turn it on.

The footprint is 266 x 31 on the ground and 17 tall. Give it a flat area and note
that X runs **west to east** as the process flow direction.

---

## 🚨 READ THIS FIRST — the one genuine renewability exception

You asked me to flag loudly if I found one. I found one, and it is not a
static-NBT technicality — it is a real recipe gap.

> **The Copper and Zinc lines are not closed loops, and therefore neither is
> the Brass Wing.**
>
> In base Create, washing (splashing) **Gravel** yields **Flint, Iron Nugget,
> and Gold Nugget**. To the best of my knowledge **Copper and Zinc nuggets are
> not in the gravel splashing table.** Copper and Zinc nuggets in Create come
> from washing *Crushed Copper Ore* / *Crushed Zinc Ore*, which require actual
> mined ore — not cobblestone.
>
> The brief's Stage 2 assumed gravel washing produces "random Iron/Gold/Copper/Zinc
> nuggets". Iron and Gold: yes. Copper and Zinc: **no, not in base Create.**

**What this breaks:** the Copper line, the Zinc line, and the Brass Wing (which
consumes 1 Copper + 1 Zinc ingot). Four of the seven outputs — Iron, Gold,
Andesite, Andesite Alloy — remain fully renewable. Three do not.

**What to do about it, in order of preference:**

1. **Check your pack first.** Many modpacks (and some Create addons/datapacks)
   *do* add copper/zinc to the gravel or crushed-stone wash table. If yours does,
   the build is already correct as printed and needs no change — the funnels and
   lines are all in place.
2. **Add a datapack recipe** giving `create:splashing` on `minecraft:gravel` a
   small chance of `create:zinc_nugget` and `create:copper_nugget`. This is the
   cleanest fix and makes the build genuinely 7/7 renewable.
3. **Feed those two lines externally.** The Copper and Zinc sorting lanes and
   the Brass Wing intake funnels are already built and filtered — just top up
   their input chests from mined ore. The rest of the factory is untouched.

Everything else in this build is a closed loop, verified twice. This one is not,
and I am not going to write "Yes" in a table to make it look tidy.

---

## Layout

X runs west → east through ten zones. Z = 15 is a central elevated glass walkway
at y = 9, with the main kinetic spine directly beneath it at y = 8, tapped down
into every zone via gearboxes and shaft risers.

| Zone | Start X | Contents |
|---|---|---|
| Crushing Bank | 0 | 4 cobblestone generators, 20 Millstones |
| Wash Hall | 30 | 24 fan-wash stations (8 lanes x 3), 8 Water Wheels |
| Sorting Floor | 56 | 8 brass-funnel filter lines (2 per metal) + loop-back |
| Compacting Floor | 84 | 8 Mechanical Press + Basin, 8 labelled chests |
| Andesite Wing | 106 | 4 Press + Basin, piped lava |
| Alloy Wing | 128 | 4 Mixer + Basin |
| Brass Wing | 148 | 4 Mixer + Basin over 4 kindled Blaze Burners |
| Timber Yard | 170 | 24 fixed-saw tree columns, 16 Furnaces |
| Boiler Room | 212 | 4 boilers (16 Blaze Burners), 16 Steam Engines, fluid networks |
| Buy Depot | 242 | 7 lever/sign selectors, Mechanical Arm, Diamond Vault |

**Machine census** (counted from the written NBT):

```
millstone         20    mechanical_saw    24    steam_engine     16
basin             20    deployer          24    fluid_tank       51
mechanical_press  12    mechanical_drill   4    encased_fan      24
mechanical_mixer   8    furnace           16    water_wheel       8
blaze_burner      20    oak_sapling       24    mechanical_pump   2
chest             35    hose_pulley        1    mechanical_arm    1
```

---

## Design corrections made against the brief

These are places where building the brief literally would have produced something
that does not work in Create. I built the working version and am telling you why.

| Brief said | What I built | Why |
|---|---|---|
| "bank of Basins under Water Wheels" washes gravel | **Encased Fan blowing down through a water source onto the gravel belt**; Water Wheels kept as the hall's visible power source | Basins do not wash anything. Bulk washing in Create is fan + water over a belt. The Water Wheels are still there and still power the hall — that is what they are actually for. |
| Crushing Wheel pairs for cobble → gravel | **20 Millstones** | The brief allows "Crushing Wheel pairs / Millstones". A wheel pair needs two wheels touching on a shared axis with the auto-generated `crushing_wheel_controller` landing in one specific adjacent air cell — geometry a static file cannot guarantee, and a mis-seated pair silently does nothing. A Millstone is one unambiguous block. |
| Deployer mines the cobblestone generator | **Mechanical Drill** | A Deployer needs a pickaxe, and pickaxes wear out. That would have made the single most upstream input in the entire factory non-renewable. A Drill has no tool and no durability. |
| Mechanical Saw on a moving contraption + Piston/Gantry rig | **Fixed horizontal Mechanical Saws** | A horizontally-placed saw fells the tree in front of it as a plain block. No wrench assembly, no contraption, no gantry — which removes the single largest "requires manual setup" exception from the audit. |
| (not mentioned) | **Infinite water pool + 1 Mechanical Pump + pipe trunk to all 4 boilers** | Create boilers **consume water**. The brief's input list never mentioned it, so it was never sourced. Without this the boilers run dry. |
| (not mentioned) | Charcoal budget accounts for **furnace fuel draw** | Smelting logs → charcoal burns charcoal. One charcoal smelts 8 items, so the bank eats 1/8 of its own output. Ignoring this is how the previous sizing came out short. |

---

## Renewability audit — double-verified

### Pass 1 — every consumed input and where it comes from

| # | Consumed input | Claimed source |
|---|---|---|
| 1 | Cobblestone | 4 lava + water generator cells, mined by Mechanical Drills |
| 2 | Gravel | 20 Millstones milling that cobblestone |
| 3 | Iron / Gold nuggets | Fan-washing the gravel |
| 4 | Copper / Zinc nuggets | Fan-washing the gravel — **see the 🚨 section above** |
| 5 | Flint | Fan-washing the gravel |
| 6 | Unsorted gravel / flint | Loop-back belt from the Sorting Floor to the generators |
| 7 | Lava (cobble gens + Andesite recipe) | Hose Pulley in an infinite lava pool → buffer tank → y=0 pipe trunk |
| 8 | Water (boiler feedwater) | Infinite 2x2 water pool → Mechanical Pump → y=6 pipe trunk |
| 9 | Water (cobble gens, wash hall) | Placed source blocks (infinite) |
| 10 | Oak saplings | Leaf drops from the farm's own trees, filtered back to the Deployers |
| 11 | Oak logs | 24 fixed Mechanical Saws felling the farm's own trees |
| 12 | Charcoal (20 Blaze Burners) | 16 Furnaces smelting those logs |
| 13 | Block-breaking tool wear | None — Mechanical Drills and Saws use no tool |
| 14 | Diamonds (Buy Depot) | Player-supplied. Intentional: it is the currency, not a factory input. |

### Pass 2 — independently re-checked against the actual placed blocks

This pass is **not** me re-reading my own notes. `verify_sevenline_foundry.py`
re-loads the written `.nbt` from disk, rebuilds the world from the palette and
block list, and proves each claim by graph connectivity (6-neighbour BFS) over
the real block positions. It does not import the generator, so a bookkeeping bug
in the generator cannot hide from it. Run it yourself:

```
python3 verify_sevenline_foundry.py
```

| # | Check re-derived from the placed blocks | Result | Confirmed |
|---|---|---|---|
| 1 | Lava network reaches all 4 cobblestone generators | 4/4 generator lava cells on the network | **Yes** |
| 2 | Lava network reaches every Andesite Wing basin | 4/4 basins adjacent to the lava-connected network (293 pipe cells) | **Yes** |
| 3 | Lava and water networks stay separate (lava only serves gens + Andesite) | lava buffer stack not on the water network | **Yes** |
| 4 | Water reaches every boiler tank stack | 16/16 tank columns on the water network (127 cells) | **Yes** |
| 5 | Charcoal path reaches every Blaze Burner | 20/20 burners (16 boiler + 4 Brass Wing) connected to the furnace-rooted item network | **Yes** |
| 6 | Harvested logs reach the furnace bank | 16/16 furnaces reachable from the tree-row collection belts | **Yes** |
| 7 | Sapling return path reaches every tree Deployer | 24/24 deployers on the same network the saplings drop onto | **Yes** |
| 8 | Every tree column has both a felling Saw and a replant Deployer | 24/24 sapling cells | **Yes** |
| 9 | Unsorted gravel loops back to the Crushing Bank | 108 generator-side belt cells reachable from the Sorting Floor return path | **Yes** |
| 10 | Cobblestone reaches every Millstone | 20/20 millstones reachable from the generator collector belts | **Yes** |
| 11 | Copper / Zinc nuggets have a renewable source | **no recipe produces them from gravel in base Create** | **🚨 NO — see the section above** |
| 12 | Block-breaking uses no consumable tool | 4 Mechanical Drills, 24 Mechanical Saws, 0 pickaxe deployers | **Yes** |

**Result: 11 of 12 confirmed. The one failure is #11**, and it is a recipe-availability
problem, not a plumbing problem — the Copper/Zinc lanes and the Brass Wing are
fully built and correctly filtered, they simply have no renewable input in base
Create. Fixes are listed in the 🚨 section.

Pass 2 found five real breaks on its first run that Pass 1 had happily asserted
were fine (lava severed at nine belt crossings, water severed by a spine shaft at
z=15, the Brass Wing charcoal trunk orphaned, saw drops landing on the floor
instead of a belt, and logs never reaching the furnace inputs). All five are fixed
in the shipped file. That is exactly why the second pass reads the file back
instead of trusting the first pass.

**What Pass 2 cannot prove:** it verifies *physical continuity* — that blocks of
the right kind form an unbroken chain in the right places. It cannot verify
Create's runtime semantics: belt travel direction, funnel polarity, kinetic stress
budget, or recipe matching. Those need the in-game pass below.

---

## Throughput — items/minute per stage, and the real bottleneck

Rates assume default Create 1.20.1 mechanism speeds at a non-overstressed network.
Treat them as *shape*, not gospel.

| Stage | Units | Rate | Notes |
|---|---|---|---|
| Cobblestone generators | 4 | **~220 cobble/min** (~55 each) | Drill-limited |
| Millstones | 20 | ~360 gravel/min capacity | Over-provisioned on purpose |
| Fan-wash stations | 24 | belt-rate limited, >>220/min | Not a constraint |
| Iron nuggets from washing | — | ~27/min (~12.5% of 220) | → **~3.0 Iron ingots/min** |
| Gold nuggets from washing | — | ~11/min (~5% of 220) | → **~1.2 Gold ingots/min** |
| Flint from washing | — | ~55/min (~25% of 220) | Feeds the Andesite Wing |
| Compacting presses | 8 | ~240 ingots/min capacity | Uses ~2% of capacity |
| Andesite Wing | 4 press+basin | **~55 Andesite/min** (flint-limited) | Highest-volume output |
| Alloy Wing | 4 mixer+basin | limited by Andesite + nugget split | |
| Brass Wing | 4 mixer+basin | **blocked — see 🚨** | Built and ready |
| Tree farm | 24 columns | ~60 logs/min gross | ~5 logs / ~120 s cycle |
| Furnace bank | 16 | 96 items/min capacity | Comfortably above 60 |
| **Charcoal net** | — | **~52.5/min** | 60 gross x 7/8 (furnaces burn 1/8) |

### The real bottleneck

**The four cobblestone generators, at ~220 cobble/min.** Everything downstream is
sized well above it — 20 millstones can chew 360/min, 8 presses can compact 240
ingots/min while actually producing about 4. The metal output rate is then
constrained a second time by the *wash drop probability* (~12.5% iron, ~5% gold),
which no amount of extra machinery fixes.

**Highest-leverage upgrade:** add more cobblestone generators. Edit `COBBLE_ZS` in
`generate_sevenline_foundry.py` (each entry adds a generator plus its 5 millstones)
and regenerate. Doubling to 8 generators roughly doubles every metal line.

### Charcoal budget — supply must exceed demand

**Demand.** Every Blaze Burner in the build is charcoal-fed:

```
Boiler Room :  4 boilers x 4 burners = 16 burners
Brass Wing  :  4 mixer cells x 1     =  4 burners
                                total = 20 burners
```

Charcoal's furnace burn time is 1600 ticks (80 s). Budgeting conservatively at
half that — ~1 charcoal per 40 s per burner to hold Kindled:

```
20 burners x 1.5 charcoal/min = 30.0 charcoal/min  DEMAND
```

**Supply.** 24 tree columns, conservative ~120 s sapling→grown→felled, ~5 logs/tree:

```
5 logs / 2 min          = 2.5 logs/min per column
x 24 columns            = 60 logs/min GROSS
x 7/8 (furnace fuel)    = 52.5 charcoal/min NET
```

```
52.5 supplied  vs  30.0 consumed  →  1.75x headroom.  CLEARS.
```

Even on a pessimistic 180 s tree cycle (40 logs/min gross → 35 net) it still
clears 30/min. Smelting is not the limit either: 16 furnaces x 6 items/min =
96/min, well above 60 logs/min.

**Why charcoal and not lava buckets, everywhere:** a charcoal-fed burner buffers
several items so heat never gaps. A lava-bucket burner runs completely dry between
refills, and on a boiler that heat gap drops the boiler level, which can pop shafts
off connected components. Piped fluid lava cannot fuel a burner at all in base
Create (addon-only). Lava here does exactly two jobs: the cobblestone generators
and the Andesite recipe.

> Optional: the **Brass Wing** burners *could* be lava-bucket-fed by a Mechanical
> Arm, since a brief heat gap there only pauses mixing harmlessly rather than
> destabilising a boiler. Charcoal is still preferred and is what is built.

---

## Manual in-game fixes required

A structure file stores blocks, blockstates, and block-entity NBT. It cannot store
GUI configuration, contraption assembly, or kinetic-network validity. After printing:

1. **Funnel filters.** Every filtered `create:brass_funnel` was written with a
   `Filter` ItemStack compound (Create 0.5.x `FilteringBehaviour` key). If a funnel
   loads unfiltered, re-apply by hand. Filters used: iron/gold/copper/zinc nugget
   (Sorting Floor + Compacting Floor), copper ingot + zinc ingot (Brass Wing intake),
   iron/zinc nugget + andesite (Alloy Wing), charcoal (all 20 burner feeds),
   oak sapling (tree farm skimmers), diamond (Buy Depot vault line).
2. **Deployer inventories.** The 24 tree Deployers were written pre-stocked with
   oak saplings. Create's `DeployerBlockEntity` inventory schema is version-sensitive
   — verify each holds a sapling, and set mode to **Use** (not Punch) so it *places*
   the sapling rather than swinging at the ground.
3. **Mechanical Drills** (cobblestone generators) need no configuration, but confirm
   each faces **down** into its cobble cell.
4. **Blaze Burner heat state.** All 20 are written as `heat_level: kindled`. That is
   the starting blockstate only — Create derives heat from real fuel at runtime. They
   will hold Kindled once the charcoal belts are running; light them once by hand to
   start, if needed.
5. **Mechanical Arm targets** (Buy Depot). `Targets` is empty in the NBT — this
   genuinely cannot be pre-baked. Right-click the Diamond Deposit chest, then each
   of the 7 stock chests, then the Pickup Depot, in the cycle order you want.
6. **Kinetic network continuity.** The spine at y=8 and its gearbox/shaft taps skip
   cells already holding a machine. Walk the walkway and confirm every zone actually
   spins; patch any visible gap with one extra shaft. Also confirm the network is
   not overstressed — 16 Steam Engines is a large budget but the machine count is high.
7. **Belt directions.** Belt `facing`/`slope`/`part` are written per segment, but
   Create rebuilds belts from their endpoints on placement. Spot-check that the
   Sorting Floor loop-back, the charcoal trunks, and the log riser ramp actually
   travel the intended way.
8. **Water/lava sources.** All fluids are placed as ordinary source blocks. Confirm
   the 2x2 lava pool (Boiler Room, ~x=235 z=20) and 2x2 water pool (~x=235 z=9) are
   behaving as infinite sources, and that the Wash Hall water wheels have *flowing*
   water — a wheel in still water does not turn.
9. **Fluid pipes** are placed with default (unconnected) blockstate and auto-connect
   on block update. Confirm the y=0 lava trunk and y=6 water trunk are actually
   plumbed end to end after printing.
10. **Signs** use the 1.20 `front_text`/`back_text` schema. On a different Minecraft
    version they may load blank — re-enter by hand.
11. **Chest contents.** All 35 chests ship with `Items: []`. Pre-filled inventories
    were deliberately omitted because Schematicannon print order can corrupt
    slot-indexed NBT. Stock the 7 Buy Depot chests manually.
12. **Copper/Zinc supply** — see the 🚨 section.

---

## Buy Depot

Player deposits Diamonds, throws the lever for the resource they want, and a
`create:mechanical_arm` moves a **fixed batch** from that resource's stock chest to
the pickup Depot. Diamonds route to a glass-fronted vault.

> **Fixed batch only.** Create has no variable-quantity dispensing. The arm moves
> whatever its configured transfer moves per activation — it cannot scale output to
> how many diamonds were inserted. The rates below are the *labelled* exchange; the
> arm must be configured to match, and a player inserting 2 diamonds gets one batch
> unless they trade twice.

| Item | Rate per 1 Diamond | Sign position | Lever | Stock chest |
|---|---|---|---|---|
| Iron Ingot | 32 | x=244, y=1, z=3 | x=245, z=3 | x=246, z=3 |
| Gold Ingot | 16 | x=244, y=1, z=7 | x=245, z=7 | x=246, z=7 |
| Copper Ingot | 32 | x=244, y=1, z=11 | x=245, z=11 | x=246, z=11 |
| Zinc Ingot | 32 | x=244, y=1, z=15 | x=245, z=15 | x=246, z=15 |
| Andesite Alloy | 24 | x=244, y=1, z=19 | x=245, z=19 | x=246, z=19 |
| Brass Ingot | 16 | x=244, y=1, z=23 | x=245, z=23 | x=246, z=23 |
| Andesite | 64 | x=244, y=1, z=27 | x=245, z=27 | x=246, z=27 |

Other Buy Depot positions:

| Element | Position |
|---|---|
| Mechanical Arm | x=250, y=2, z=15 |
| Diamond Deposit (input chest) | x=252, y=1, z=13 |
| Pickup Depot (output) | x=252, y=1, z=17 |
| Diamond Vault (behind glass) | x=256, y=1, z=15 |

**To change a rate:** edit the `DEPOT_RATES` list near the bottom of
`generate_sevenline_foundry.py` — each entry is `(label, rate, item_id)`. Re-run the
script and the sign text and chest labels regenerate. Coordinates above shift if you
add or remove entries (signs are spaced 4 blocks apart in Z starting at z=3).
**The arm's actual transfer amount is in-game GUI state, not in this file** — update
it to match whatever you set here.

---

## Limitations

- **Not tested in a running Minecraft/Create instance.** No game client was available
  in this environment. Verification was: (a) round-tripping the gzipped NBT through
  nbtlib to confirm it parses with the expected size/palette/block counts, and (b)
  the independent 12-check connectivity pass described above. Print it in a throwaway
  world and walk the manual-fixes list before trusting it in a real save.
- **Block IDs** are Create 1.20.1 names and were not checked against a live registry
  dump. If any block fails to place, check your Create version's registry and patch
  the corresponding helper in the generator.
- **Create runtime concepts** — kinetic stress and speed, fluid network validity,
  contraption assembly, and all GUI-configured state — cannot be expressed in a
  structure file. This file gets the geometry and blockstates right and leaves
  configuration to the in-game pass.

## Regenerating

```
python3 generate_sevenline_foundry.py   # rewrites sevenline_foundry.nbt
python3 verify_sevenline_foundry.py     # re-reads it and re-runs all 12 checks
```
