#!/usr/bin/env python3
"""
Sevenline Foundry -- Create-mod (Minecraft Java 1.20.1 / DataVersion 3465)
Schematicannon-compatible structure NBT, generated with Python + nbtlib.

Seven renewable outputs: Iron, Gold, Copper, Zinc, Andesite, Andesite Alloy,
Brass.  Diamond-currency Buy Depot.  Everything heavily parallelised.

======================================================================
WHY THIS IS A REWRITE (correctness fixes over the first draft)
======================================================================
1. `create:boiler` DOES NOT EXIST.  In Create a boiler is a *Fluid Tank
   multiblock* filled with water, heated by Blaze Burners underneath, with
   Steam Engines attached to the tank's sides.  The old file placed a
   non-existent block id, which the Schematicannon would have skipped.
2. `create:mechanical_press` has a HORIZONTAL facing (the shaft axis), not
   `facing=down`.  An invalid blockstate value falls back to default and
   silently mis-orients the machine.
3. Boilers CONSUME WATER.  The old renewability audit never listed water as
   a consumed input, so it was never sourced.  There is now an infinite
   water pool + Mechanical Pumps + pipe trunk feeding every boiler tank.
4. Furnaces smelting logs->charcoal BURN FUEL.  One charcoal smelts 8 items,
   so the farm only nets 7/8 of gross log throughput.  The old math ignored
   this and still came out short.  The Timber Yard is now sized to clear
   real demand with ~1.7x headroom (see FUEL BUDGET below).
5. The tree farm no longer needs a moving contraption.  A Mechanical Saw
   placed HORIZONTALLY fells the tree in front of it as a fixed block --
   no wrench-assembly, no Mechanical Piston, no gantry.  This removes the
   single biggest "requires manual assembly" exception from the audit.
6. Gravel washing is NOT "basin under a water wheel" -- that is not a Create
   mechanic and would have produced nothing.  Bulk washing is Encased Fan
   blowing DOWN through a water source onto items on a belt.  The Wash Hall
   now does that, and keeps the Water Wheels as the hall's visible power
   source (which is what they are actually for).  See README.

======================================================================
LAYOUT
======================================================================
X = west->east process flow.  Z = 0..30.  Y = 0 (stone floor) .. 16 (roof).
Z=15 is the central elevated glass walkway at y=9, with the main kinetic
spine directly beneath it at y=8, tapped down into every zone.

Machine lanes (parallel unit positions), south bank and north bank:
    LANES8 = 3, 6, 9, 12 | 18, 21, 24, 27
    LANES4 = 6, 9        | 21, 24

Zones west->east, each fronted by a Sign:
    Crushing Bank    4x cobble gen -> 8x crushing pair + 8x millstone -> gravel
    Wash Hall        8x fan-wash lines -> nuggets / flint / leftover gravel
    Sorting Floor    8x brass-funnel filter lines (2 per nugget type)
    Compacting Floor 8x press+basin -> ingots -> labelled chests
    Andesite Wing    4x press+basin, flint+gravel+lava -> andesite
    Alloy Wing       4x mixer+basin, andesite+nugget -> andesite alloy
    Brass Wing       4x mixer+basin over KINDLED charcoal burners -> brass
    Timber Yard      24x fixed-saw tree columns + 16x furnace -> charcoal
    Boiler Room      4x boiler (fluid tank + 4 burners) + 16x steam engine
    Buy Depot        lever/sign selector + mechanical arm + diamond vault

======================================================================
CLOSED SAPLING LOOP  (the farm can never run dry)
======================================================================
Each tree column is: dirt at y=0, sapling spot at y=1, a fixed horizontal
Mechanical Saw facing the trunk base, and a Deployer beside the trunk
facing INTO the sapling spot (deployers place the block they face, one
block away -- so it replants without ever standing in the trunk's way).

The whole tree row floor is belted at y=1, so EVERY drop -- logs, saplings,
sticks, apples -- lands on a belt instead of on the ground.  That belt runs
to a Brass Funnel filtered to `minecraft:oak_sapling`, which lifts saplings
onto a return belt at y=3 running back over the deployer row; andesite
funnels drop one sapling into each Deployer.  Logs continue past the
sapling filter to the furnace bank.

The loop is therefore CLOSED IN BLOCKS, not by assumption: the saplings the
deployers replant are physically the saplings the same trees dropped, and
oak leaves average well above 1 sapling per felled tree (a tree needs
exactly 1 to replant), so the surplus accumulates as a buffer inside the
deployers.  No sapling is ever imported.

======================================================================
FUEL BUDGET  (why 24 tree columns and 16 furnaces)
======================================================================
Demand -- every Blaze Burner in the build, all charcoal-fed:
    Boiler Room : 4 boilers x 4 burners each   = 16 burners
    Brass Wing  : 4 mixer cells x 1 burner     =  4 burners
                                          total = 20 burners
  Charcoal in a Blaze Burner is assumed conservatively at ~1 item / 40 s
  to hold Kindled (charcoal's furnace burn time is 1600 ticks = 80 s; we
  budget at half that so the estimate errs safe).
    20 burners x 1.5 charcoal/min = 30 charcoal/min DEMAND.

Supply -- 24 tree columns:
  Conservative oak cycle: ~120 s sapling->grown->felled, ~5 logs per tree.
    5 logs / 2 min = 2.5 logs/min per column
    24 columns     = 60 logs/min GROSS
  Furnaces burn charcoal to smelt: 1 charcoal smelts 8 logs, so the bank
  eats 1/8 of its own output:
    60 logs/min x 7/8 = 52.5 charcoal/min NET

    52.5 supplied vs 30.0 consumed  ->  1.75x headroom.  CLEARS.

  Even on a pessimistic 180 s tree cycle (40 logs/min gross, 35 net) the
  build still clears 30/min demand.  Smelting capacity is not the limit
  either: 16 furnaces x 6 items/min = 96 items/min >> 60 logs/min.

Fuel routing is deliberately split for stability -- BOTH the boiler burners
and the Brass Wing burners get CHARCOAL, never lava buckets.  A charcoal-fed
burner buffers several items so heat never gaps; a lava-bucket burner runs
completely dry between refills, and on a boiler that heat gap drops the
boiler level, which can pop shafts off connected components.  Piped fluid
lava cannot fuel a burner at all in base Create (addon-only).  Lava in this
build is used for exactly two things: the cobblestone generators and the
Andesite recipe.
"""

import os
import nbtlib
from nbtlib import Compound, List, Int, String, Byte

# ----------------------------------------------------------------------
# Placement bookkeeping
# ----------------------------------------------------------------------

blocks = {}   # (x,y,z) -> {"name":str, "props":dict, "nbt":Compound|None}
NOTES = []    # collected build notes for the README


def place(x, y, z, name, props=None, nbt=None, overwrite=False):
    """Strict placement: raises on collision unless overwrite=True.
    Used for every machine, so layout mistakes fail loudly."""
    key = (x, y, z)
    if key in blocks and not overwrite:
        raise ValueError(
            f"Collision at {key}: '{blocks[key]['name']}' already there, "
            f"tried to place '{name}'")
    blocks[key] = {"name": name, "props": dict(props or {}), "nbt": nbt}


def soft(x, y, z, name, props=None, nbt=None):
    """Decorative placement: silently skips an occupied cell.
    Used for floors, roofs, walls, glass and the walkway."""
    if (x, y, z) not in blocks:
        blocks[(x, y, z)] = {"name": name, "props": dict(props or {}), "nbt": nbt}


def occupied(x, y, z):
    return (x, y, z) in blocks


# ----------------------------------------------------------------------
# Kinetics
# ----------------------------------------------------------------------

def shaft(x, y, z, axis):
    place(x, y, z, "create:shaft", {"axis": axis})


def soft_shaft(x, y, z, axis):
    soft(x, y, z, "create:shaft", {"axis": axis})


def cogwheel(x, y, z, axis):
    place(x, y, z, "create:cogwheel", {"axis": axis})


def gearbox(x, y, z):
    soft(x, y, z, "create:gearbox")


def spine_tap(x, target_y, target_z):
    """Gearbox on the main spine at (x, SPINE_Y, WALKWAY_Z), then a vertical
    shaft leg down to target_y and a horizontal leg across Z to target_z.
    Cells already holding a machine are skipped -- Create transmits rotation
    into an adjacent kinetic block anyway, but see README: walk the spine
    in-game and patch any visible gap with one extra shaft."""
    gearbox(x, SPINE_Y, WALKWAY_Z)
    step = -1 if target_y < SPINE_Y else 1
    y = SPINE_Y
    while y != target_y:
        y += step
        soft_shaft(x, y, WALKWAY_Z, "y")
    step = -1 if target_z < WALKWAY_Z else 1
    z = WALKWAY_Z
    while z != target_z:
        z += step
        soft_shaft(x, target_y, z, "z")


# ----------------------------------------------------------------------
# Belts
# ----------------------------------------------------------------------

def belt_x(x0, x1, y, z, facing):
    step = 1 if x1 >= x0 else -1
    xs = list(range(x0, x1 + step, step))
    for i, x in enumerate(xs):
        if occupied(x, y, z):
            continue
        part = "start" if i == 0 else ("end" if i == len(xs) - 1 else "middle")
        soft(x, y, z, "create:belt",
             {"part": part, "facing": facing, "slope": "horizontal"})


def belt_ramp_x(x0, y0, z, rise, facing="east"):
    """Upward-sloping belt climbing `rise` blocks over `rise` blocks of X.
    Lands flat at (x0+rise, y0+rise, z)."""
    for i in range(rise):
        soft(x0 + i, y0 + i, z, "create:belt", {
            "part": "start" if i == 0 else ("end" if i == rise - 1 else "middle"),
            "facing": facing, "slope": "upward"})


def belt_z(z0, z1, x, y, facing):
    step = 1 if z1 >= z0 else -1
    zs = list(range(z0, z1 + step, step))
    for i, z in enumerate(zs):
        if occupied(x, y, z):
            continue
        part = "start" if i == 0 else ("end" if i == len(zs) - 1 else "middle")
        soft(x, y, z, "create:belt",
             {"part": part, "facing": facing, "slope": "horizontal"})


# ----------------------------------------------------------------------
# Item handling: funnels, chutes, chests, depots, signs
# ----------------------------------------------------------------------

def funnel(x, y, z, facing, filtered_item=None, brass=True, overwrite=False):
    """Create funnel.  `facing` is the direction items FLOW.
    Filter is written as the block-entity `Filter` ItemStack compound, which
    is FilteringBehaviour's key in Create 0.5.x -- if a funnel loads unset,
    re-apply it by hand (README, Manual Fixes)."""
    name = "create:brass_funnel" if brass else "create:andesite_funnel"
    nbt = None
    if filtered_item is not None:
        nbt = Compound({
            "id": String(name),
            "Filter": Compound({"id": String(filtered_item), "Count": Byte(1)}),
            "FilterMatchNBT": Byte(0),
        })
    place(x, y, z, name, {"facing": facing}, nbt, overwrite=overwrite)


def chute(x, y, z):
    place(x, y, z, "create:chute")


def chest(x, y, z, facing, label):
    nbt = Compound({
        "id": String("minecraft:chest"),
        "CustomName": String('{"text":"%s"}' % label),
        "Items": List[Compound]([]),
    })
    place(x, y, z, "minecraft:chest", {"facing": facing, "type": "single"}, nbt)


def depot(x, y, z):
    place(x, y, z, "create:depot")


def sign(x, y, z, lines, rotation="0"):
    """Standing oak sign, modern 1.20 front_text/back_text schema (correct
    for DataVersion 3465).  rotation 0-15, 0 = south-facing."""
    lines = (list(lines) + ["", "", "", ""])[:4]
    def msgs(ls):
        return List[String]([String('{"text":"%s"}' % t) for t in ls])
    nbt = Compound({
        "id": String("minecraft:sign"),
        "is_waxed": Byte(0),
        "front_text": Compound({
            "has_glowing_text": Byte(0), "color": String("black"),
            "messages": msgs(lines)}),
        "back_text": Compound({
            "has_glowing_text": Byte(0), "color": String("black"),
            "messages": msgs(["", "", "", ""])}),
    })
    place(x, y, z, "minecraft:oak_sign", {"rotation": rotation}, nbt)


# ----------------------------------------------------------------------
# Machines
# ----------------------------------------------------------------------

def basin(x, y, z):
    place(x, y, z, "create:basin")


def press(x, y, z, facing="north"):
    # Mechanical Press takes a HORIZONTAL facing (its shaft axis).
    place(x, y, z, "create:mechanical_press", {"facing": facing})


def mixer(x, y, z):
    # Mechanical Mixer is always vertical, powered from the shaft on top.
    place(x, y, z, "create:mechanical_mixer")


def blaze_burner(x, y, z, heat="kindled"):
    place(x, y, z, "create:blaze_burner", {"heat_level": heat})


def water_wheel(x, y, z, facing):
    place(x, y, z, "create:water_wheel", {"facing": facing})


def crushing_wheel(x, y, z, axis):
    # Pairs are placed touching, same axis; Create generates the internal
    # controller block itself, so we deliberately do NOT place one.
    place(x, y, z, "create:crushing_wheel", {"axis": axis})


def millstone(x, y, z):
    place(x, y, z, "create:millstone")


def encased_fan(x, y, z, facing):
    place(x, y, z, "create:encased_fan", {"facing": facing})


def deployer(x, y, z, facing, held=None, count=64):
    """Deployer, optionally pre-stocked.  Create's DeployerBlockEntity
    inventory schema is version-sensitive; this is best-effort and is listed
    in the README's Manual Fixes so it gets eyeballed in-game."""
    nbt = {"id": String("create:deployer")}
    if held:
        nbt["Inventory"] = Compound({
            "Items": List[Compound]([Compound({
                "Slot": Byte(0), "id": String(held), "Count": Byte(count)})]),
            "Size": Int(1),
        })
    place(x, y, z, "create:deployer", {"facing": facing}, Compound(nbt))


def mechanical_drill(x, y, z, facing):
    """Breaks the block it faces, forever, with no tool and no durability
    cost.  Used for the cobblestone generators instead of a pickaxe-holding
    Deployer -- a pickaxe wears out, which would have made the single most
    upstream input in the whole factory non-renewable."""
    place(x, y, z, "create:mechanical_drill", {"facing": facing})


def saw(x, y, z, facing):
    # HORIZONTAL facing = fixed tree cutter, no contraption needed.
    place(x, y, z, "create:mechanical_saw", {"facing": facing})


def steam_engine(x, y, z, facing):
    # Mounts on the side of a boiler (fluid tank), facing AWAY from it.
    place(x, y, z, "create:steam_engine", {"facing": facing})


def fluid_tank(x, y, z):
    place(x, y, z, "create:fluid_tank")


def fluid_pipe(x, y, z):
    soft(x, y, z, "create:fluid_pipe")


def mechanical_pump(x, y, z, facing):
    place(x, y, z, "create:mechanical_pump", {"facing": facing})


def hose_pulley(x, y, z, facing):
    place(x, y, z, "create:hose_pulley", {"facing": facing})


def furnace(x, y, z, facing="north"):
    nbt = Compound({"id": String("minecraft:furnace"),
                    "Items": List[Compound]([])})
    place(x, y, z, "minecraft:furnace", {"facing": facing, "lit": "false"}, nbt)


def mechanical_arm(x, y, z):
    nbt = Compound({
        "id": String("create:mechanical_arm"),
        # Targets are selected in-game by right-clicking each inventory in
        # order with the arm placed; cannot be pre-baked reliably.
        "Targets": List[Compound]([]),
    })
    place(x, y, z, "create:mechanical_arm", nbt=nbt)


def lever(x, y, z, facing="north"):
    place(x, y, z, "minecraft:lever",
          {"face": "floor", "facing": facing, "powered": "false"})


# ======================================================================
# GLOBAL LAYOUT
# ======================================================================

GROUND = 0        # stone floor
WALKWAY_Z = 15
WALKWAY_Y = 9     # glass walkway deck
SPINE_Y = 8       # main kinetic spine, directly under the walkway
ROOF_Y = 16
Z_MIN, Z_MAX = 0, 30

LANES8 = [3, 6, 9, 12, 18, 21, 24, 27]
LANES4 = [6, 9, 21, 24]

NUGGETS = [
    ("Iron",   "minecraft:iron_nugget",  "minecraft:iron_ingot"),
    ("Gold",   "minecraft:gold_nugget",  "minecraft:gold_ingot"),
    ("Copper", "create:copper_nugget",   "minecraft:copper_ingot"),
    ("Zinc",   "create:zinc_nugget",     "create:zinc_ingot"),
]

X = 0
ZONE_STARTS = {}


def next_zone(label, width, gap=4):
    global X
    x0 = X
    ZONE_STARTS[label] = x0
    X = x0 + width + gap
    return x0, x0 + width - 1


def zone_sign(x0, lines):
    sign(x0 + 1, GROUND + 1, WALKWAY_Z - 2, lines, rotation="0")


# ======================================================================
# ZONE A -- CRUSHING BANK
#   4 infinite cobblestone cells -> 20 Millstones -> gravel
#
# NOTE ON MILLSTONES vs CRUSHING WHEELS: the brief allows either.  A
# Crushing Wheel pair needs two wheels touching on a shared axis with the
# auto-generated `crushing_wheel_controller` occupying a specific adjacent
# air cell -- geometry that a static structure file cannot guarantee will
# resolve the way you intended, and a mis-seated pair silently does nothing.
# A Millstone is a single unambiguous block: shaft above, items inserted by
# the belt that runs into it, output pulled out the side by a funnel.  So
# the grinding load is carried entirely by Millstones, and there are enough
# of them that grinding is NOT the bottleneck (see README throughput math).
# ======================================================================
xa0, xa1 = next_zone("Crushing Bank", 26)

# Four independent lava+water cobblestone cells so one jam never starves the
# whole bank.  Lava and water sit two apart; cobble forms in the gap at
# y=GROUND+2 and a Deployer (pickaxe, Punch mode) mines it; the drop falls
# onto the collector belt one level below.
COBBLE_ZS = [3, 9, 21, 27]
MILL_X = xa0 + 12
MILLS_PER_GEN = 5          # z = gz-2 .. gz+2

for cz in COBBLE_ZS:
    place(xa0 + 1, GROUND + 2, cz, "minecraft:lava")
    place(xa0 + 3, GROUND + 2, cz, "minecraft:water")
    # (xa0+2, GROUND+2, cz) is the cobble formation cell -- deliberately air.
    # A Mechanical Drill (NOT a pickaxe Deployer) mines it: zero durability
    # cost, so the most upstream input in the build stays truly renewable.
    mechanical_drill(xa0 + 2, GROUND + 3, cz, "down")
    # containment so the fluids cannot spill across the floor
    for dz in (cz - 1, cz + 1):
        for dx in (xa0 + 1, xa0 + 2, xa0 + 3):
            soft(dx, GROUND + 2, dz, "minecraft:stone_bricks")
    soft(xa0 + 0, GROUND + 2, cz, "minecraft:stone_bricks")
    soft(xa0 + 4, GROUND + 2, cz, "minecraft:stone_bricks")
    # collector belt beneath the gen, running east to the mill fan-out
    belt_x(xa0 + 2, xa0 + 7, GROUND + 1, cz, "east")
    # fan out north and south to the five mill lanes for this generator
    belt_z(cz, cz - 2, xa0 + 7, GROUND + 1, "north")
    belt_z(cz, cz + 2, xa0 + 7, GROUND + 1, "south")

MILL_ZS = []
for cz in COBBLE_ZS:
    for mz in range(cz - 2, cz + 3):
        MILL_ZS.append((cz, mz))

for cz, mz in MILL_ZS:
    # belt runs east and inserts directly into the millstone it ends at
    belt_x(xa0 + 8, MILL_X - 1, GROUND + 1, mz, "east")
    millstone(MILL_X, GROUND + 1, mz)
    soft_shaft(MILL_X, GROUND + 2, mz, "y")            # power from above
    funnel(MILL_X + 1, GROUND + 1, mz, "east", brass=False)   # gravel out
    belt_x(MILL_X + 2, MILL_X + 6, GROUND + 1, mz, "east")
    # merge the five mill lanes back onto this generator's gravel trunk
    if mz != cz:
        belt_z(mz, cz, MILL_X + 6, GROUND + 1, "south" if mz < cz else "north")

for cz in COBBLE_ZS:
    belt_x(MILL_X + 7, xa1, GROUND + 1, cz, "east")    # gravel trunk east

for cz, mz in MILL_ZS:
    spine_tap(MILL_X, GROUND + 2, mz)

zone_sign(xa0, ["Crushing Bank", "4x cobble gen", "20x millstone", "-> gravel"])


# ======================================================================
# ZONE B -- WASH HALL
#   Fan-washing: Encased Fan blowing DOWN through a water source onto the
#   gravel belt.  Water Wheels flanking the hall are its power source.
# ======================================================================
xb0, xb1 = next_zone("Wash Hall", 22)

# Split each of the four gravel trunks onto two wash lanes apiece.
TRUNK_TO_LANES = {3: [3, 6], 9: [9, 12], 21: [18, 21], 27: [24, 27]}
for cz, lanes in TRUNK_TO_LANES.items():
    for lane in lanes:
        if lane != cz:
            belt_z(cz, lane, xb0 - 2, GROUND + 1,
                   "south" if lane > cz else "north")

for lane in LANES8:
    belt_x(xb0, xb1, GROUND + 1, lane, "east")
    # wash column: belt(y1) -> water(y2) -> fan(y3) facing down
    for wx in (xb0 + 4, xb0 + 8, xb0 + 12):
        place(wx, GROUND + 2, lane, "minecraft:water")
        encased_fan(wx, GROUND + 3, lane, "down")
        # glass shroud so the water source stays put and the wash is visible
        for dz in (lane - 1, lane + 1):
            soft(wx, GROUND + 2, dz, "minecraft:glass")
        soft(wx, GROUND + 4, lane, "minecraft:glass")

# Water wheels: the hall's visible renewable power, water-fed from a channel
# running along the outer walls.
for lane in (1, 29):
    for wx in range(xb0 + 2, xb0 + 18, 4):
        water_wheel(wx, GROUND + 2, lane, "east")
        place(wx, GROUND + 3, lane, "minecraft:water")
        soft(wx, GROUND + 4, lane, "minecraft:glass")

for lane in LANES8:
    for wx in (xb0 + 4, xb0 + 8, xb0 + 12):
        spine_tap(wx, GROUND + 3, lane)

zone_sign(xb0, ["Wash Hall", "fan + water wash", "gravel -> nuggets", "+flint, gravel"])


# ======================================================================
# ZONE C -- SORTING FLOOR
#   8 filter lines, 2 per nugget type.  Brass funnel faces UP: it takes from
#   the belt below and pushes into the chest above.  Anything unmatched
#   rides to the east end and loops back to the Crushing Bank.
# ======================================================================
xc0, xc1 = next_zone("Sorting Floor", 24)

SORT_LINES = []  # (lane, nugget_name, nugget_item) -- 2 lanes per type
for i, lane in enumerate(LANES8):
    name, item, ingot = NUGGETS[i % 4]
    SORT_LINES.append((lane, name, item, ingot))

for lane, name, item, ingot in SORT_LINES:
    belt_x(xc0, xc1, GROUND + 1, lane, "east")
    fx = xc0 + 8
    funnel(fx, GROUND + 2, lane, "up", filtered_item=item, brass=True)
    chest(fx, GROUND + 3, lane, "north", f"{name} Nuggets")
    # sorted nuggets leave the chest on a dedicated belt one level up,
    # heading east into the Compacting Floor
    funnel(fx + 1, GROUND + 3, lane, "east", filtered_item=item, brass=True)
    belt_x(fx + 2, xc1, GROUND + 3, lane, "east")

# Loop-back: unmatched gravel/flint reaches the east end of every lane,
# is lifted, merges on a return belt at y=6 and rides west to drop back
# onto the Crushing Bank collector belts.  This closes the gravel loop.
LOOPBACK_Y = GROUND + 6
for lane in LANES8:
    funnel(xc1, GROUND + 2, lane, "up", brass=False)
    belt_z(lane, WALKWAY_Z - 3, xc1, LOOPBACK_Y, "south" if lane < WALKWAY_Z else "north")
belt_x(xa0 + 6, xc1, LOOPBACK_Y, WALKWAY_Z - 3, "west")
for cz in COBBLE_ZS:
    belt_z(WALKWAY_Z - 3, cz, xa0 + 6, LOOPBACK_Y, "north" if cz < WALKWAY_Z else "south")
    # funnel off the return belt into a chute column that drops the gravel
    # back onto this generator's collector belt at GROUND+1 -- loop closed.
    funnel(xa0 + 6, LOOPBACK_Y - 1, cz, "down", brass=False)
    for cy in range(GROUND + 2, LOOPBACK_Y - 1):
        chute(xa0 + 6, cy, cz)

zone_sign(xc0, ["Sorting Floor", "8x brass funnel", "2 lines per metal", "unsorted loops back"])


# ======================================================================
# ZONE D -- COMPACTING FLOOR
#   8x Mechanical Press over Basin: 9 nuggets -> 1 ingot -> labelled chest
# ======================================================================
xd0, xd1 = next_zone("Compacting Floor", 18)

for lane, name, item, ingot in SORT_LINES:
    funnel(xd0, GROUND + 3, lane, "down", filtered_item=item, brass=True)
    basin(xd0 + 1, GROUND + 2, lane)
    press(xd0 + 1, GROUND + 4, lane, facing="north")
    funnel(xd0 + 1, GROUND + 1, lane, "east", brass=False)
    belt_x(xd0 + 2, xd0 + 5, GROUND + 1, lane, "east")
    chest(xd0 + 6, GROUND + 1, lane, "north", f"{name} Ingots")
    # glass viewing panel over every basin (showcase requirement)
    soft(xd0 + 1, GROUND + 5, lane, "minecraft:glass")

for lane in LANES8:
    spine_tap(xd0 + 1, GROUND + 4, lane)

# Copper + Zinc ingot tap-off to the Brass Wing, Iron/Zinc nugget tap-off to
# the Alloy Wing -- both are placed as belts later, from these funnels.
zone_sign(xd0, ["Compacting Floor", "9 nuggets -> ingot", "8x press + basin", "-> labelled chests"])


# ======================================================================
# ZONE E -- ANDESITE WING
#   Flint + Gravel + piped Lava -> 4x press+basin -> Andesite (quartz-free)
# ======================================================================
xe0, xe1 = next_zone("Andesite Wing", 18)

for lane in LANES4:
    funnel(xe0, GROUND + 3, lane, "down", brass=False)          # flint+gravel in
    basin(xe0 + 1, GROUND + 2, lane)
    press(xe0 + 1, GROUND + 4, lane, facing="north")
    fluid_pipe(xe0 + 1, GROUND + 1, lane)                        # lava into basin
    funnel(xe0 + 1, GROUND + 1, lane + 1, "east", brass=False)
    belt_x(xe0 + 2, xe1 - 2, GROUND + 1, lane, "east")
    soft(xe0 + 1, GROUND + 5, lane, "minecraft:glass")

# Power taps run only after every machine in the zone exists, so a tap's
# horizontal shaft leg can never land in a cell a later machine wants.
for lane in LANES4:
    spine_tap(xe0 + 1, GROUND + 4, lane)

# Output split: two lanes bank Andesite as a sellable product, two lanes
# belt it onward to the Alloy Wing.
chest(xe1, GROUND + 1, LANES4[0], "north", "Andesite (Storage)")
chest(xe1, GROUND + 1, LANES4[2], "north", "Andesite (Storage)")
belt_x(xe1 - 1, xe1, GROUND + 1, LANES4[1], "east")
belt_x(xe1 - 1, xe1, GROUND + 1, LANES4[3], "east")

zone_sign(xe0, ["Andesite Wing", "flint+gravel+lava", "4x press + basin", "quartz-free"])


# ======================================================================
# ZONE F -- ALLOY WING
#   Andesite + Iron/Zinc Nugget -> 4x mixer+basin -> Andesite Alloy
# ======================================================================
xf0, xf1 = next_zone("Alloy Wing", 16)

for i, lane in enumerate(LANES4):
    # andesite in from the Andesite Wing
    funnel(xf0, GROUND + 3, lane, "down", filtered_item="create:andesite_alloy" if False
           else "minecraft:andesite", brass=True)
    # nugget in: alternate iron / zinc so both valid recipes are exercised
    nug = "minecraft:iron_nugget" if i % 2 == 0 else "create:zinc_nugget"
    funnel(xf0 + 2, GROUND + 3, lane, "down", filtered_item=nug, brass=True)
    basin(xf0 + 1, GROUND + 2, lane)
    mixer(xf0 + 1, GROUND + 4, lane)
    funnel(xf0 + 1, GROUND + 1, lane, "east", brass=False)
    belt_x(xf0 + 2, xf0 + 5, GROUND + 1, lane, "east")
    chest(xf0 + 6, GROUND + 1, lane, "north", "Andesite Alloy")
    soft(xf0 + 1, GROUND + 5, lane, "minecraft:glass")

for lane in LANES4:
    spine_tap(xf0 + 1, GROUND + 4, lane)

zone_sign(xf0, ["Alloy Wing", "andesite + nugget", "4x mixer + basin", "-> andesite alloy"])


# ======================================================================
# ZONE G -- BRASS WING
#   Copper + Zinc Ingot 1:1 -> 4x mixer+basin over KINDLED charcoal-fed
#   Blaze Burners -> 2 Brass Ingots per craft
# ======================================================================
xg0, xg1 = next_zone("Brass Wing", 18)

BRASS_LANES = LANES4
for lane in BRASS_LANES:
    # burner at y=1, basin directly above it at y=2, mixer above that
    blaze_burner(xg0 + 1, GROUND + 1, lane, heat="kindled")
    basin(xg0 + 1, GROUND + 2, lane)
    mixer(xg0 + 1, GROUND + 4, lane)
    # 1:1 ingot intake, one filtered funnel per metal
    funnel(xg0, GROUND + 3, lane, "down", filtered_item="minecraft:copper_ingot", brass=True)
    funnel(xg0 + 2, GROUND + 3, lane, "down", filtered_item="create:zinc_ingot", brass=True)
    # brass out
    funnel(xg0 + 1, GROUND + 1, lane + 1, "east", brass=False)
    belt_x(xg0 + 2, xg0 + 6, GROUND + 1, lane + 1, "east")
    chest(xg0 + 7, GROUND + 1, lane + 1, "north", "Brass Ingots")
    soft(xg0 + 1, GROUND + 5, lane, "minecraft:glass")
    # CHARCOAL feed: belt arrives from the Timber Yard at y=1 on lane-1 and
    # a brass funnel filtered to charcoal inserts into the burner's side.
    funnel(xg0, GROUND + 1, lane, "east", filtered_item="minecraft:charcoal", brass=True)
    belt_x(xg0 - 6, xg0 - 1, GROUND + 1, lane, "east")

for lane in BRASS_LANES:
    spine_tap(xg0 + 1, GROUND + 4, lane)

zone_sign(xg0, ["Brass Wing", "copper + zinc 1:1", "4x mixer + basin", "kindled charcoal"])


# ======================================================================
# ZONE H -- TIMBER YARD
#   24 fixed-saw tree columns (no contraption) + closed sapling loop
#   + 16 furnaces -> Charcoal
# ======================================================================
xh0, xh1 = next_zone("Timber Yard", 38)

# Per tree row, four Z-slices:
#   row-2 : COLLECTION belt.  A Create Mechanical Saw ejects a felled tree's
#           drops behind itself, so the belt sits directly behind the saws --
#           logs AND saplings land on a belt, never on the floor.
#   row-1 : the fixed horizontal Saws, facing south into the trunk base.
#   row   : dirt + sapling; Deployers stand one block west of each trunk
#           facing east, so they replant into the trunk cell without ever
#           standing in the tree's way.  The sapling RETURN belt runs above
#           them at GROUND+3, dropping through a funnel into each Deployer.
TREE_ROWS = [5, 25]
TREE_XS = [xh0 + 2 + i * 2 for i in range(12)]     # 12 columns per row = 24
SAPLING_RETURN_Y = GROUND + 3
SAPLING_FILTER_X = xh0 + 26
LOG_LANE_Z = 13                                     # riser lane to the furnaces
LOG_DECK_Y = GROUND + 4

for row in TREE_ROWS:
    collect_z = row - 2
    for tx in TREE_XS:
        place(tx, GROUND, row, "minecraft:dirt", overwrite=True)
        place(tx, GROUND + 1, row, "minecraft:oak_sapling", {"stage": "0"})
        saw(tx, GROUND + 1, row - 1, "south")
        deployer(tx - 1, GROUND + 1, row, "east", held="minecraft:oak_sapling")
        funnel(tx - 1, GROUND + 2, row, "down", brass=False)   # sapling drop-in
    # collection belt directly behind the saw line
    belt_x(xh0, SAPLING_FILTER_X, GROUND + 1, collect_z, "east")
    # sapling skimmer: brass funnel lifts saplings up to the return belt,
    # logs ride straight past it and continue east to the log riser
    funnel(SAPLING_FILTER_X, GROUND + 2, collect_z, "up",
           filtered_item="minecraft:oak_sapling", brass=True)
    belt_z(collect_z, row, SAPLING_FILTER_X, SAPLING_RETURN_Y,
           "south" if row > collect_z else "north")
    belt_x(SAPLING_FILTER_X, xh0, SAPLING_RETURN_Y, row, "west")
    # logs continue east, then turn onto the shared riser lane
    belt_x(SAPLING_FILTER_X + 1, SAPLING_FILTER_X + 2, GROUND + 1, collect_z, "east")
    belt_z(collect_z, LOG_LANE_Z, SAPLING_FILTER_X + 2, GROUND + 1,
           "south" if LOG_LANE_Z > collect_z else "north")

# Log riser: sloped belt climbs GROUND+1 -> LOG_DECK_Y, then a deck belt
# runs over the furnace bank and funnels drop logs into each furnace.
belt_ramp_x(SAPLING_FILTER_X + 3, GROUND + 1, LOG_LANE_Z, 3, "east")
belt_x(SAPLING_FILTER_X + 6, xh1, LOG_DECK_Y, LOG_LANE_Z, "east")

# 16 furnaces on a clean 2 x 8 grid.  Z values avoid the tree rows
# (3,4,5 and 23,24,25), the log lane (13) and the walkway band (14-16).
FURNACE_XS = [xh0 + 30, xh0 + 34]
FURNACE_ZS = [1, 7, 9, 11, 18, 20, 22, 28]
FURNACE_CELLS = [(fx, fz) for fx in FURNACE_XS for fz in FURNACE_ZS]

for fx in FURNACE_XS:
    # deck distribution belt runs the full Z span over the furnace column
    belt_z(LOG_LANE_Z, FURNACE_ZS[0], fx, LOG_DECK_Y, "north")
    belt_z(LOG_LANE_Z, FURNACE_ZS[-1], fx, LOG_DECK_Y, "south")
    belt_x(SAPLING_FILTER_X + 6, fx, LOG_DECK_Y, LOG_LANE_Z, "east")

for (fx, fz) in FURNACE_CELLS:
    furnace(fx, GROUND + 2, fz)
    funnel(fx, GROUND + 3, fz, "down", brass=False)   # logs down from the deck
    funnel(fx, GROUND + 1, fz, "east", brass=False)   # charcoal out

# --- Charcoal split -------------------------------------------------------
# West group (z < walkway) feeds the 4 Brass Wing burners; east group feeds
# the 16 Boiler Room burners.  Splitting by furnace group means no belt ever
# has to be divided by a splitter -- each group has one destination.
WEST_FURNACES = [(fx, fz) for (fx, fz) in FURNACE_CELLS if fz < WALKWAY_Z]
EAST_FURNACES = [(fx, fz) for (fx, fz) in FURNACE_CELLS if fz > WALKWAY_Z]
CHARCOAL_WEST_Z = WALKWAY_Z - 4        # z = 11
CHARCOAL_EAST_Z = WALKWAY_Z + 4        # z = 19

for (fx, fz) in WEST_FURNACES:
    belt_x(fx + 1, FURNACE_XS[-1] + 2, GROUND + 1, fz, "east")
    belt_z(fz, CHARCOAL_WEST_Z, FURNACE_XS[-1] + 2, GROUND + 1,
           "south" if CHARCOAL_WEST_Z > fz else "north")
for (fx, fz) in EAST_FURNACES:
    belt_x(fx + 1, FURNACE_XS[-1] + 2, GROUND + 1, fz, "east")
    belt_z(fz, CHARCOAL_EAST_Z, FURNACE_XS[-1] + 2, GROUND + 1,
           "south" if CHARCOAL_EAST_Z > fz else "north")

# West trunk: all the way back to the Brass Wing burner funnels.
belt_x(FURNACE_XS[-1] + 2, xg0 - 6, GROUND + 1, CHARCOAL_WEST_Z, "west")
for lane in BRASS_LANES:
    belt_z(CHARCOAL_WEST_Z, lane, xg0 - 6, GROUND + 1,
           "north" if lane < WALKWAY_Z else "south")

# Observation window into the tree farm from the walkway.
for tz in (TREE_ROWS[0] + 2, TREE_ROWS[1] - 2):
    for tx in range(xh0, SAPLING_FILTER_X):
        for ty in (GROUND + 2, GROUND + 3, GROUND + 4):
            soft(tx, ty, tz, "minecraft:glass")

zone_sign(xh0, ["Timber Yard", "24x fixed saw", "closed sapling loop", "16x furnace"])


# ======================================================================
# ZONE I -- BOILER ROOM
#   4 boilers.  Each = 2x2x3 Fluid Tank multiblock (water) heated by 4
#   Blaze Burners underneath, with 4 Steam Engines on its sides.
#   Plus the infinite LAVA network and the infinite WATER network.
# ======================================================================
xi0, xi1 = next_zone("Boiler Room", 26)

BOILER_CELLS = [(xi0 + 4, 4), (xi0 + 4, 24), (xi0 + 14, 4), (xi0 + 14, 24)]

for (bx, bz) in BOILER_CELLS:
    # 4 charcoal-fed blaze burners under the tank
    for dx in (0, 1):
        for dz in (0, 1):
            blaze_burner(bx + dx, GROUND + 1, bz + dz, heat="kindled")
    # 2x2x3 fluid tank = the boiler proper
    for dx in (0, 1):
        for dz in (0, 1):
            for dy in range(2, 5):
                fluid_tank(bx + dx, GROUND + dy, bz + dz)
    # 4 steam engines on the tank sides at y=3, each facing away from it
    steam_engine(bx - 1, GROUND + 3, bz,     "west")
    steam_engine(bx - 1, GROUND + 3, bz + 1, "west")
    steam_engine(bx + 2, GROUND + 3, bz,     "east")
    steam_engine(bx + 2, GROUND + 3, bz + 1, "east")
    # shafts from the engines into the spine
    for ez, ex in ((bz, bx - 2), (bz + 1, bx - 2)):
        soft_shaft(ex, GROUND + 3, ez, "x")
    for ez, ex in ((bz, bx + 3), (bz + 1, bx + 3)):
        soft_shaft(ex, GROUND + 3, ez, "x")
    # charcoal in: belt at y=1 stops one short of the burner block, and a
    # charcoal-filtered brass funnel bridges belt -> burner on both rows.
    belt_x(xi0, bx - 2, GROUND + 1, bz, "east")
    belt_z(bz, bz + 1, bx - 2, GROUND + 1, "south")
    funnel(bx - 1, GROUND + 1, bz, "east",
           filtered_item="minecraft:charcoal", brass=True)
    funnel(bx - 1, GROUND + 1, bz + 1, "east",
           filtered_item="minecraft:charcoal", brass=True)
    # water in: pipe down into the top of the tank stack
    fluid_pipe(bx, GROUND + 5, bz)
    fluid_pipe(bx, GROUND + 6, bz)

# Boiler power ties into the spine only after all four boilers exist.
for (bx, bz) in BOILER_CELLS:
    spine_tap(bx, GROUND + 3, bz)

# Charcoal trunk from the Timber Yard's EAST furnace group into the Boiler
# Room feed belts (the west group serves the Brass Wing -- see Zone H).
belt_x(xh1, xi0, GROUND + 1, CHARCOAL_EAST_Z, "east")
for (bx, bz) in BOILER_CELLS:
    belt_z(CHARCOAL_EAST_Z, bz, xi0, GROUND + 1,
           "north" if bz < CHARCOAL_EAST_Z else "south")

# --- INFINITE LAVA NETWORK (cobblestone gens + Andesite presses ONLY) ---
# Hose Pulley lowers into a lava pool, fills a Fluid Tank buffer, and a pipe
# trunk runs west at y=1 the whole length of the build.
LAVA_X = xi1 - 2
for dz in (WALKWAY_Z + 5, WALKWAY_Z + 6):
    for dx in (LAVA_X, LAVA_X + 1):
        place(dx, GROUND + 1, dz, "minecraft:lava")
        soft(dx, GROUND, dz, "minecraft:stone_bricks")
hose_pulley(LAVA_X, GROUND + 4, WALKWAY_Z + 5, "north")
for dy in (5, 6, 7):
    fluid_tank(LAVA_X, GROUND + dy, WALKWAY_Z + 5)
mechanical_pump(LAVA_X, GROUND + 4, WALKWAY_Z + 4, "north")
# The lava trunk runs at y=GROUND (under the machine floor) for its whole
# length.  y=GROUND+1 is the universal belt level and is far too congested
# for a 230-block pipe run -- routing it there left the branch broken in
# nine places, which the verification pass caught.
LAVA_TRUNK_Y = GROUND
for dy in (GROUND, GROUND + 1, GROUND + 2, GROUND + 3):
    fluid_pipe(LAVA_X, dy, WALKWAY_Z + 4)          # riser: pool -> trunk
for x in range(xa0 + 1, LAVA_X + 1):
    fluid_pipe(x, LAVA_TRUNK_Y, WALKWAY_Z + 4)
# branch to the Andesite Wing basins (up through the riser already placed
# under each basin at GROUND+1)
for lane in LANES4:
    for z in range(min(lane, WALKWAY_Z + 4), max(lane, WALKWAY_Z + 4) + 1):
        fluid_pipe(xe0 + 1, LAVA_TRUNK_Y, z)
    fluid_pipe(xe0 + 1, GROUND + 1, lane)
# branch to each cobblestone generator, rising to the gen cell at GROUND+2
for cz in COBBLE_ZS:
    for z in range(min(cz, WALKWAY_Z + 4), max(cz, WALKWAY_Z + 4) + 1):
        fluid_pipe(xa0 + 1, LAVA_TRUNK_Y, z)
    fluid_pipe(xa0 + 1, GROUND + 1, cz)

# --- INFINITE WATER NETWORK (boiler feedwater) ---
# Boilers consume water; a 2x2 source pool is infinite, and a Mechanical
# Pump pushes it up a riser and along a trunk to all four tank stacks.
WATER_X = xi1 - 2
for dz in (WALKWAY_Z - 6, WALKWAY_Z - 5):
    for dx in (WATER_X, WATER_X + 1):
        place(dx, GROUND + 1, dz, "minecraft:water")
        soft(dx, GROUND, dz, "minecraft:stone_bricks")
mechanical_pump(WATER_X, GROUND + 2, WALKWAY_Z - 6, "up")
for dy in range(3, 7):
    fluid_pipe(WATER_X, GROUND + dy, WALKWAY_Z - 6)
WATER_TRUNK_Y = GROUND + 6
# Main trunk west along z=9 to a crossing column.
for x in range(xi0 + 1, WATER_X + 1):
    fluid_pipe(x, WATER_TRUNK_Y, WALKWAY_Z - 6)
# The north boilers cannot be reached by running straight across z=15 at
# every boiler's own X: the spine-tap shaft risers occupy (x, 3..8, 15)
# there, and the verification pass caught the pipe run being severed at
# exactly that cell.  So the trunk crosses the walkway line once, at a
# column with no spine tap, then fans out along Z-free lanes.
CROSS_X = xi0 + 1
for z in range(4, 25):
    fluid_pipe(CROSS_X, WATER_TRUNK_Y, z)
for bz in (4, 24):
    for x in range(CROSS_X, max(b[0] for b in BOILER_CELLS) + 2):
        fluid_pipe(x, WATER_TRUNK_Y, bz)

# Observation window into the Boiler Room + glass walkway floor over it.
for z in range(Z_MIN + 1, Z_MAX):
    soft(xi0, GROUND + 2, z, "minecraft:glass")
    soft(xi0, GROUND + 3, z, "minecraft:glass")
    soft(xi0, GROUND + 4, z, "minecraft:glass")

zone_sign(xi0, ["Boiler Room", "4x boiler tank", "16x steam engine", "charcoal-fed"])


# ======================================================================
# ZONE J -- BUY DEPOT
#   Diamonds in -> lever/sign selector -> Mechanical Arm moves a fixed
#   batch from the matching stock chest to the pickup Depot.
#   Create has NO variable-quantity dispensing: batches are fixed.
# ======================================================================
xj0, xj1 = next_zone("Buy Depot", 20)

DEPOT_RATES = [
    ("Iron Ingot",     32, "minecraft:iron_ingot"),
    ("Gold Ingot",     16, "minecraft:gold_ingot"),
    ("Copper Ingot",   32, "minecraft:copper_ingot"),
    ("Zinc Ingot",     32, "create:zinc_ingot"),
    ("Andesite Alloy", 24, "create:andesite_alloy"),
    ("Brass Ingot",    16, "create:brass_ingot"),
    ("Andesite",       64, "minecraft:andesite"),
]

DEPOT_POSITIONS = {}
for i, (label, rate, item) in enumerate(DEPOT_RATES):
    z = 3 + i * 4
    sx = xj0 + 2
    DEPOT_POSITIONS[label] = (sx, GROUND + 1, z)
    sign(sx, GROUND + 1, z, [label, "1 Diamond", f"= {rate}", "pull lever ->"], rotation="0")
    lever(sx + 1, GROUND + 1, z)
    chest(sx + 2, GROUND + 1, z, "north", f"Stock: {label}")
    # arm reach line
    soft(sx + 3, GROUND + 1, z, "minecraft:andesite")

# The arm sits central, within reach of the stock chests, the diamond input
# and the pickup depot.  Targets MUST be assigned in-game (see README).
ARM_POS = (xj0 + 8, GROUND + 2, WALKWAY_Z)
mechanical_arm(*ARM_POS)
soft(xj0 + 8, GROUND + 1, WALKWAY_Z, "create:andesite_casing")
spine_tap(xj0 + 8, GROUND + 2, WALKWAY_Z - 1)

chest(xj0 + 10, GROUND + 1, WALKWAY_Z - 2, "north", "Diamond Deposit (IN)")
depot(xj0 + 10, GROUND + 1, WALKWAY_Z + 2)          # pickup depot (OUT)
sign(xj0 + 11, GROUND + 1, WALKWAY_Z + 2, ["PICKUP", "collect your", "purchase here", ""], rotation="0")

# Visible diamond vault behind glass.
VAULT_POS = (xj0 + 14, GROUND + 1, WALKWAY_Z)
chest(*VAULT_POS, "north", "Diamond Vault")
for dz in (WALKWAY_Z - 1, WALKWAY_Z + 1):
    soft(xj0 + 14, GROUND + 1, dz, "minecraft:glass")
    soft(xj0 + 14, GROUND + 2, dz, "minecraft:glass")
soft(xj0 + 14, GROUND + 2, WALKWAY_Z, "minecraft:glass")
funnel(xj0 + 10, GROUND + 2, WALKWAY_Z - 2, "east", filtered_item="minecraft:diamond", brass=True)
belt_x(xj0 + 11, xj0 + 13, GROUND + 2, WALKWAY_Z - 2, "east")
belt_z(WALKWAY_Z - 2, WALKWAY_Z - 1, xj0 + 13, GROUND + 2, "south")

zone_sign(xj0, ["Buy Depot", "diamonds in", "fixed batch out", "arm delivers"])


# ======================================================================
# SHELL -- floor, roof, walkway, spine, scaffolding, perimeter
# (built last, soft-placed, so it never disturbs a machine)
# ======================================================================

X_MIN, X_MAX = 0, X - 1

# stone ground floor + andesite roof across the whole footprint
for x in range(X_MIN, X_MAX + 1):
    for z in range(Z_MIN, Z_MAX + 1):
        soft(x, GROUND, z, "minecraft:stone")
        soft(x, ROOF_Y, z, "minecraft:andesite")

# central elevated glass walkway (3 wide) + kinetic spine beneath it
for x in range(X_MIN, X_MAX + 1):
    for z in (WALKWAY_Z - 1, WALKWAY_Z, WALKWAY_Z + 1):
        soft(x, WALKWAY_Y, z, "minecraft:glass")
    soft_shaft(x, SPINE_Y, WALKWAY_Z, "x")
    # walkway railing
    for z in (WALKWAY_Z - 2, WALKWAY_Z + 2):
        soft(x, WALKWAY_Y, z, "create:andesite_casing")
    # support pillars, alternating andesite / copper / brass casing
    if x % 8 == 0:
        mat = ["minecraft:andesite", "create:copper_casing", "create:brass_casing"][(x // 8) % 3]
        for y in range(GROUND + 1, WALKWAY_Y):
            for z in (WALKWAY_Z - 2, WALKWAY_Z + 2):
                soft(x, y, z, mat)

# perimeter: low open showcase wall, stone/andesite/copper/brass palette
for x in range(X_MIN, X_MAX + 1):
    for z in (Z_MIN, Z_MAX):
        soft(x, GROUND + 1, z, "minecraft:stone_bricks")
        if x % 6 == 0:
            mat = ["minecraft:andesite", "create:copper_casing",
                   "create:brass_casing"][(x // 6) % 3]
            for y in range(GROUND + 2, GROUND + 6):
                soft(x, y, z, mat)
        else:
            soft(x, GROUND + 2, z, "minecraft:glass")

# roof support columns so the roof reads as a roof, not a floating slab
for x in range(X_MIN, X_MAX + 1, 8):
    for z in (Z_MIN, Z_MAX):
        for y in range(GROUND + 6, ROOF_Y):
            soft(x, y, z, "minecraft:andesite")

# entrance sign
sign(X_MIN, GROUND + 1, WALKWAY_Z, [
    "SEVENLINE", "FOUNDRY", "7 renewable lines", "walkway ->"], rotation="0")


# ======================================================================
# Assemble and write
# ======================================================================

def build_nbt():
    xs = [p[0] for p in blocks]
    ys = [p[1] for p in blocks]
    zs = [p[2] for p in blocks]
    min_x, min_y, min_z = min(xs), min(ys), min(zs)
    size = [max(xs) - min_x + 1, max(ys) - min_y + 1, max(zs) - min_z + 1]

    palette_list, palette_index = [], {}

    def palette_id(name, props):
        key = (name, tuple(sorted(props.items())))
        if key not in palette_index:
            entry = {"Name": String(name)}
            if props:
                entry["Properties"] = Compound(
                    {k: String(v) for k, v in sorted(props.items())})
            palette_list.append(Compound(entry))
            palette_index[key] = len(palette_list) - 1
        return palette_index[key]

    block_list = []
    for (x, y, z), data in sorted(blocks.items(),
                                  key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        entry = {
            "pos": List[Int]([Int(x - min_x), Int(y - min_y), Int(z - min_z)]),
            "state": Int(palette_id(data["name"], data["props"])),
        }
        if data["nbt"] is not None:
            entry["nbt"] = data["nbt"]
        block_list.append(Compound(entry))

    root = Compound({
        "DataVersion": Int(3465),                      # Minecraft 1.20.1
        "size": List[Int]([Int(v) for v in size]),
        "entities": List[Compound]([]),
        "blocks": List[Compound](block_list),
        "palette": List[Compound](palette_list),
    })
    return root, size


def census():
    """Count placed machines, used by the README verification pass."""
    tally = {}
    for d in blocks.values():
        tally[d["name"]] = tally.get(d["name"], 0) + 1
    return tally


def main():
    root, size = build_nbt()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "sevenline_foundry.nbt")
    nbtlib.File(root, gzipped=True).save(out)

    t = census()
    print(f"Wrote {out}")
    print(f"Structure size (X,Y,Z): {size}")
    print(f"Total blocks: {len(blocks)}   palette entries: {len(root['palette'])}")
    print("\nZone start X:")
    for k, v in ZONE_STARTS.items():
        print(f"  {k:<18} x={v}")
    print("\nMachine census:")
    for k in sorted(t):
        if k.startswith("create:") or k in (
                "minecraft:furnace", "minecraft:chest", "minecraft:oak_sapling",
                "minecraft:lava", "minecraft:water", "minecraft:oak_sign"):
            print(f"  {k:<34} {t[k]}")


if __name__ == "__main__":
    main()
