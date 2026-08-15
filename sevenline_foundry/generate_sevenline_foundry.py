#!/usr/bin/env python3
"""
Build "Sevenline Foundry" -- a Create-mod (Minecraft Java, 1.20.1 / DataVersion
3465) Schematicannon-compatible structure NBT file, using Python + nbtlib.

This follows the same approach as the earlier `quad_wash_ingot_factory`
build in this repo: real vanilla-structure NBT schema (size/palette/blocks/
entities/DataVersion), real Create + vanilla block IDs and blockstate
properties, and block-entity NBT for funnels/chests/signs where Create's
schema needs it. It does NOT simulate Create's kinetic network, fluid
network, or contraption assembly -- those require in-game interaction (see
README.md "Manual In-Game Fixes Required").

======================================================================
LAYOUT (X = west->east process flow, Z = 0..16 width, Y = height)
======================================================================
Z=8 is a central elevated glass walkway (y=7) running the whole length,
with a shaft spine directly beneath it at y=6 that carries kinetic power
from the Boiler Room (steam engines) and the Wash Hall (water wheels)
out to every zone via gearbox taps.

Zones, west to east, each fronted by a Sign with its label:
  Crushing Bank   (cobblestone gen + 4x crushing wheel pair -> gravel)
  Wash Hall       (4x basin/water wheel -> nuggets/flint/gravel)
  Sorting Floor   (4x brass-funnel filter line, sorts nuggets by type)
  Compacting Floor(4x mechanical press+basin -> ingots -> chests)
  Andesite Wing   (2x press+basin, flint+gravel+lava -> andesite)
  Alloy Wing      (2x mixer+basin, andesite+nugget -> andesite alloy)
  Brass Wing      (2x mixer+basin over kindled blaze burners -> brass)
  Timber Yard     (saw+deployer replant loop, furnace bank -> charcoal)
  Boiler Room     (3x steam engine + 3x boiler, observation glass)
  Buy Depot       (lever/sign selector + mechanical arm + diamond vault)

See README.md for the renewability audit, throughput math, and the list
of things that still need a right-click / wrench / GUI pass in-game.
"""

import os
import nbtlib
from nbtlib import Compound, List, Int, String, Byte, Float

# ----------------------------------------------------------------------
# Block-placement bookkeeping
# ----------------------------------------------------------------------

blocks = {}  # (x, y, z) -> {"name": str, "props": dict, "nbt": Compound|None}


def place(x, y, z, name, props=None, nbt=None, overwrite=False):
    key = (x, y, z)
    if key in blocks and not overwrite:
        raise ValueError(
            f"Collision at {key}: '{blocks[key]['name']}' already placed, "
            f"tried to place '{name}'"
        )
    blocks[key] = {"name": name, "props": dict(props or {}), "nbt": nbt}


def clear(x, y, z):
    blocks.pop((x, y, z), None)


# ----------------------------------------------------------------------
# Kinetic helpers
# ----------------------------------------------------------------------

def shaft(x, y, z, axis):
    place(x, y, z, "create:shaft", {"axis": axis})


def cogwheel(x, y, z, axis):
    place(x, y, z, "create:cogwheel", {"axis": axis})


def gearbox(x, y, z):
    place(x, y, z, "create:gearbox")


def power_riser(x, z, y_from, y_to):
    """Vertical shaft column from y_from to y_to (inclusive) at (x,z),
    used to tap power from the main spine down/up into a zone."""
    lo, hi = (y_from, y_to) if y_from <= y_to else (y_to, y_from)
    for y in range(lo, hi + 1):
        shaft(x, y, z, "y")


def spine_tap(x, spine_y, spine_z, target_y, target_z):
    """Gearbox off the horizontal spine, shaft down/up + across to a
    zone's working level. Used throughout to visibly route power. Cells
    already occupied by a machine are left alone (adjacent kinetic blocks
    still transmit rotation to a block occupying the target cell in
    Create) -- final kinetic continuity should be verified in-game."""
    if (x, spine_y, spine_z) not in blocks:
        gearbox(x, spine_y, spine_z)
    # vertical leg
    step = -1 if target_y < spine_y else 1
    y = spine_y
    while y != target_y:
        y += step
        if (x, y, spine_z) not in blocks:
            shaft(x, y, spine_z, "y")
    # horizontal leg across Z toward the zone lane
    step = -1 if target_z < spine_z else 1
    z = spine_z
    while z != target_z:
        z += step
        if (x, target_y, z) not in blocks:
            shaft(x, target_y, z, "z")


# ----------------------------------------------------------------------
# Belts
# ----------------------------------------------------------------------

def belt_run_x(x_start, x_end, y, z, facing):
    step = 1 if x_end >= x_start else -1
    xs = list(range(x_start, x_end + step, step))
    n = len(xs)
    for i, x in enumerate(xs):
        if (x, y, z) in blocks:
            continue
        part = "start" if i == 0 else ("end" if i == n - 1 else "middle")
        place(x, y, z, "create:belt", {"part": part, "facing": facing, "slope": "horizontal"})


def belt_run_z(z_start, z_end, x, y, facing):
    step = 1 if z_end >= z_start else -1
    zs = list(range(z_start, z_end + step, step))
    n = len(zs)
    for i, z in enumerate(zs):
        if (x, y, z) in blocks:
            continue
        part = "start" if i == 0 else ("end" if i == n - 1 else "middle")
        place(x, y, z, "create:belt", {"part": part, "facing": facing, "slope": "horizontal"})


def belt_slope(x, y, z, facing, slope, part="middle"):
    place(x, y, z, "create:belt", {"part": part, "facing": facing, "slope": slope})


# ----------------------------------------------------------------------
# Funnels (with optional filter NBT), chests, signs
# ----------------------------------------------------------------------

def funnel(x, y, z, facing, filtered_item=None, brass=True):
    name = "create:brass_funnel" if brass else "create:andesite_funnel"
    nbt = None
    if filtered_item is not None:
        nbt = Compound({
            "id": String(name),
            # Create's funnel filter slot. Exact tag name has shifted across
            # versions ("Filter" is correct for 1.20.1-era Create); if your
            # build uses a different key, re-set the filter by right-click
            # in-game instead -- see README "Manual In-Game Fixes Required".
            "Filter": Compound({"id": String(filtered_item), "Count": Byte(1)}),
            "FilterMatchNBT": Byte(0),
        })
    place(x, y, z, name, {"facing": facing}, nbt)


def chest(x, y, z, facing, label):
    nbt = Compound({
        "id": String("minecraft:chest"),
        "CustomName": String('{"text":"%s"}' % label),
        "Items": List[Compound]([]),
    })
    place(x, y, z, "minecraft:chest", {"facing": facing}, nbt)


def sign_text_component(text):
    return String('{"text":"%s"}' % text) if text else String('""')


def sign(x, y, z, lines, rotation="0", wall=False, facing="north"):
    """Standing sign (rotation 0-15, S=0) with modern 1.20 front_text/
    back_text schema. `lines` is a list of up to 4 strings.
    If `wall=True`, places a wall sign instead (facing cardinal direction)."""
    lines = (lines + ["", "", "", ""])[:4]
    front = Compound({
        "has_glowing_text": Byte(0),
        "color": String("black"),
        "messages": List[String]([sign_text_component(t) for t in lines]),
    })
    back = Compound({
        "has_glowing_text": Byte(0),
        "color": String("black"),
        "messages": List[String]([sign_text_component("") for _ in range(4)]),
    })
    nbt = Compound({
        "id": String("minecraft:sign"),
        "front_text": front,
        "back_text": back,
        "is_waxed": Byte(0),
    })
    if wall:
        place(x, y, z, "minecraft:oak_wall_sign", {"facing": facing}, nbt)
    else:
        place(x, y, z, "minecraft:oak_sign", {"rotation": rotation}, nbt)


def zone_label(x, z_center, text):
    """Post a sign on the walkway (Z=8, y=8) naming the zone starting at x."""
    sign(x, WALKWAY_Y + 1, WALKWAY_Z, [text, "", "", ""], rotation="4")


# ----------------------------------------------------------------------
# Machines
# ----------------------------------------------------------------------

def basin(x, y, z):
    place(x, y, z, "create:basin")


def press(x, y, z):
    place(x, y, z, "create:mechanical_press", {"facing": "down"})


def mixer(x, y, z):
    place(x, y, z, "create:mechanical_mixer")


def blaze_burner(x, y, z, heat="kindled"):
    place(x, y, z, "create:blaze_burner", {"heat_level": heat})


def water_wheel(x, y, z, facing):
    place(x, y, z, "create:water_wheel", {"facing": facing})


def crushing_wheel(x, y, z, axis):
    place(x, y, z, "create:crushing_wheel", {"axis": axis})


def crushing_wheel_controller(x, y, z, facing):
    place(x, y, z, "create:crushing_wheel_controller", {"facing": facing})


def deployer(x, y, z, facing):
    nbt = Compound({"id": String("create:deployer")})
    place(x, y, z, "create:deployer", {"facing": facing}, nbt)


def saw(x, y, z, facing):
    place(x, y, z, "create:mechanical_saw", {"facing": facing})


def steam_engine(x, y, z, facing):
    place(x, y, z, "create:steam_engine", {"facing": facing})


def boiler(x, y, z):
    place(x, y, z, "create:steam_engine_boiler" if False else "create:boiler")


def hose_pulley(x, y, z, facing):
    place(x, y, z, "create:hose_pulley", {"facing": facing})


def fluid_pipe(x, y, z):
    place(x, y, z, "create:fluid_pipe")


def fluid_tank(x, y, z):
    place(x, y, z, "create:fluid_tank")


def furnace(x, y, z, facing="north"):
    nbt = Compound({"id": String("minecraft:furnace"), "BurnTime": Int(0)})
    place(x, y, z, "minecraft:furnace", {"facing": facing, "lit": "false"}, nbt)


def mechanical_arm(x, y, z):
    nbt = Compound({
        "id": String("create:mechanical_arm"),
        # Targets must be selected in-game with the arm's target wrench
        # (right-click each input/output inventory in order). Left empty
        # here -- see README "Manual In-Game Fixes Required".
        "Targets": List[Compound]([]),
    })
    place(x, y, z, "create:mechanical_arm", nbt=nbt)


def lever(x, y, z, facing="floor", face="floor", powered="false"):
    place(x, y, z, "minecraft:lever", {"facing": facing, "face": face, "powered": powered})


# ----------------------------------------------------------------------
# Aesthetic helpers
# ----------------------------------------------------------------------

def floor_plane(x0, x1, z0, z1, y, material="minecraft:stone"):
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if (x, y, z) not in blocks:
                place(x, y, z, material)


def glass_floor(x0, x1, z0, z1, y):
    floor_plane(x0, x1, z0, z1, y, "minecraft:glass")


def scaffold_pillar(x, z, y0, y1, material="create:andesite_pillar" if False else "minecraft:andesite"):
    for y in range(y0, y1 + 1):
        if (x, y, z) not in blocks:
            place(x, y, z, material)


# ======================================================================
# GLOBAL LAYOUT CONSTANTS
# ======================================================================

WALKWAY_Z = 8
WALKWAY_Y = 7          # glass floor of the elevated central walkway
SPINE_Y = 6            # main kinetic spine, runs beneath the walkway
GROUND_Y = 0
ROOF_Y = 12

# lanes used by "4 parallel units" zones: two either side of the walkway
LANES4 = [2, 5, 11, 14]
# lanes used by "2 parallel units" zones
LANES2 = [5, 11]

X = 0  # running cursor for zone start; updated as we lay each zone out
ZONE_STARTS = {}  # label -> x0, for README + Buy Depot reference


def next_zone(label, width, gap=3):
    global X
    x0 = X
    ZONE_STARTS[label] = x0
    zone_label(x0 + 1, WALKWAY_Z, label)
    X = x0 + width + gap
    return x0, x0 + width - 1


# ======================================================================
# ZONE A: CRUSHING BANK
#   Infinite cobblestone (lava+water) -> 4x crushing-wheel pair -> gravel
# ======================================================================
xa0, xa1 = next_zone("Crushing Bank", 16)

# Infinite cobblestone generator: lava source west, water source east of a
# 1-block gap; they meet and continuously refresh a cobblestone block.
place(xa0 + 1, GROUND_Y + 1, 3, "minecraft:lava")
place(xa0 + 3, GROUND_Y + 1, 3, "minecraft:water")
# (xa0+2, GROUND_Y+1, 3) is the cobblestone-formation cell -- left as air;
# a deployer above (holding a pickaxe, "Punch" mode set in-game) mines it.
deployer(xa0 + 2, GROUND_Y + 2, 3, "down")
belt_run_x(xa0 + 2, xa0 + 8, GROUND_Y, 3, facing="east")

# 4x crushing wheel pairs (parallel, arranged along Z) fed by the same
# cobblestone belt via lift funnels; each pair crushes cobblestone->gravel.
for i, z in enumerate(LANES4):
    lift_x = xa0 + 8
    funnel(lift_x, GROUND_Y + 1, z, "north" if z < WALKWAY_Z else "south", brass=False)
    # bring item from collector belt (z=3) to this lane via a short belt
    belt_run_z(3, z, lift_x, GROUND_Y, "south" if z > 3 else "north")
    crushing_wheel(lift_x + 1, GROUND_Y + 2, z, "x")
    crushing_wheel(lift_x + 2, GROUND_Y + 2, z, "x")
    crushing_wheel_controller(lift_x + 1, GROUND_Y + 3, z, "down")
    # gravel output belt, all four merge onto the Zone A->B gravel spine
    belt_run_x(lift_x + 1, xa1, GROUND_Y + 1, z, facing="east")
# power taps for the wheel pairs (placed after all machines so the spine
# taps' horizontal legs -- which sweep across every Z lane -- never try
# to overwrite a machine cell in a lane visited later in the loop above)
for z in LANES4:
    lift_x = xa0 + 8
    spine_tap(lift_x + 1, SPINE_Y, WALKWAY_Z, GROUND_Y + 2, z)

sign(xa0 + 1, GROUND_Y + 1, 1, ["Crushing Bank", "cobble -> gravel", "4x wheel pairs", ""], rotation="8")

# ======================================================================
# ZONE B: WASH HALL
#   Gravel -> 4x basin under water wheel -> nuggets/flint/leftover gravel
# ======================================================================
xb0, xb1 = next_zone("Wash Hall", 18)

# Gravel intake spine (continues each lane's belt from Zone A into a basin)
for z in LANES4:
    funnel(xb0, GROUND_Y + 1, z, "north" if z < WALKWAY_Z else "south", brass=False)
    basin(xb0 + 1, GROUND_Y + 1, z)
    water_wheel(xb0 + 1, GROUND_Y + 3, z, "east")
    place(xb0 + 1, GROUND_Y + 4, z, "minecraft:water")
    # Basin output (random nuggets/flint/leftover gravel) drops to a belt
    belt_run_x(xb0 + 1, xb1, GROUND_Y, z, facing="east")

# Wheel row kinetic tie + spine tap (water wheels are a real power source
# here, feeding *into* the main spine in addition to drawing from it, so
# the wash hall is self-sufficient even before the Boiler Room spins up).
for z in LANES4:
    spine_tap(xb0 + 2, SPINE_Y, WALKWAY_Z, GROUND_Y + 3, z)

sign(xb0 + 1, GROUND_Y + 1, 1, ["Wash Hall", "gravel -> nuggets", "+flint, gravel", ""], rotation="8")

# ======================================================================
# ZONE C: SORTING FLOOR
#   Central belt -> 4x brass-funnel filter line (iron/gold/copper/zinc)
#   Unsorted / leftover gravel+flint loops back to the Crushing Bank.
# ======================================================================
xc0, xc1 = next_zone("Sorting Floor", 18)

NUGGETS = [
    ("Iron", "minecraft:iron_nugget"),
    ("Gold", "minecraft:gold_nugget"),
    ("Copper", "minecraft:copper_nugget"),
    ("Zinc", "create:zinc_nugget"),
]

# Merge the 4 wash-hall lanes onto one central sorting spine at z=WALKWAY_Z-...
# we instead keep 4 independent filter lines, one per lane, each seeing the
# full mixed stream and skimming its own nugget type (classic Create sort).
for (name, item), z in zip(NUGGETS, LANES4):
    belt_run_x(xc0, xc0 + 10, GROUND_Y, z, facing="east")
    funnel(xc0 + 5, GROUND_Y + 1, z, "up", filtered_item=item, brass=True)
    place(xc0 + 5, GROUND_Y + 2, z, "create:belt", {"part": "middle", "facing": "east", "slope": "horizontal"})
    belt_run_x(xc0 + 11, xc1, GROUND_Y, z, facing="east")

sign(xc0 + 1, GROUND_Y + 1, 1, ["Sorting Floor", "brass funnels", "filter by nugget", "unsorted loops back"], rotation="8")

# Leftover loop-back: everything that isn't skimmed rides to the end of
# the sorting floor, is lifted, and rides an elevated return belt back to
# the Crushing Bank's collector belt (closing the gravel/flint loop).
LOOPBACK_Y = GROUND_Y + 5
funnel(xc1, GROUND_Y + 1, LANES4[0], "up", brass=False)
belt_run_x(xc1, xc1, LOOPBACK_Y, LANES4[0], facing="west")
belt_run_z(LANES4[0], 3, xc1, LOOPBACK_Y, facing="north")
belt_run_x(xa0 + 2, xc1, LOOPBACK_Y, 3, facing="west")
place(xa0 + 2, LOOPBACK_Y, 3, "create:andesite_funnel", {"facing": "down"}, overwrite=True)  # drops onto Crushing Bank collector belt

# ======================================================================
# ZONE D: COMPACTING FLOOR
#   Sorted nugget lines -> 4x press+basin -> ingots -> labeled chests
# ======================================================================
xd0, xd1 = next_zone("Compacting Floor", 16)

for (name, item), z in zip(NUGGETS, LANES4):
    funnel(xd0, GROUND_Y + 1, z, "north" if z < WALKWAY_Z else "south", brass=False)
    basin(xd0 + 1, GROUND_Y + 1, z)
    press(xd0 + 1, GROUND_Y + 2, z)
    spine_tap(xd0 + 2, SPINE_Y, WALKWAY_Z, GROUND_Y + 2, z)
    funnel(xd0 + 2, GROUND_Y + 1, z, "east", brass=False)
    chest(xd0 + 3, GROUND_Y + 1, z, "south", f"{name} Ingots")

sign(xd0 + 1, GROUND_Y + 1, 1, ["Compacting Floor", "9 nuggets", "-> 1 ingot", "press over basin"], rotation="8")

# ======================================================================
# ZONE E: ANDESITE WING
#   Flint + Gravel + piped Lava -> 2x press+basin -> Andesite
#   (quartz-free recipe). Split output to storage chest + Alloy Wing belt.
# ======================================================================
xe0, xe1 = next_zone("Andesite Wing", 14)

# Piped lava from the infinite-lava network (see Boiler Room / hose pulley
# below) arrives along z=WALKWAY_Z at ground level and taps into each lane.
fluid_pipe_run_y = GROUND_Y + 1
for z in LANES2:
    funnel(xe0, GROUND_Y + 1, z, "north" if z < WALKWAY_Z else "south", brass=False)  # flint+gravel in
    basin(xe0 + 1, GROUND_Y + 1, z)
    fluid_pipe(xe0 + 1, GROUND_Y, z)  # lava tap into the basin from below
    press(xe0 + 1, GROUND_Y + 2, z)
    spine_tap(xe0 + 2, SPINE_Y, WALKWAY_Z, GROUND_Y + 2, z)
    funnel(xe0 + 2, GROUND_Y + 1, z, "east", brass=False)
    # split: belt continues east to storage chest AND a branch feeds the Alloy Wing
    belt_run_x(xe0 + 3, xe1, GROUND_Y, z, facing="east")

chest(xe1, GROUND_Y + 1, LANES2[0], "south", "Andesite (Storage)")
# Branch belt carrying andesite up and over to the Alloy Wing's intake lane
belt_run_x(xe1, xe1, GROUND_Y + 2, LANES2[1], facing="east")
funnel(xe1, GROUND_Y + 1, LANES2[1], "up", brass=False)

sign(xe0 + 1, GROUND_Y + 1, 1, ["Andesite Wing", "flint+gravel+lava", "press over basin", "quartz-free recipe"], rotation="8")

# fluid pipe trunk feeding the andesite wing's lava taps, connects to the
# infinite lava network described in the Boiler Room section below.
for z in LANES2:
    fluid_pipe(xe0, GROUND_Y, z)

# ======================================================================
# ZONE F: ALLOY WING
#   Andesite + Iron/Zinc Nugget -> 2x mixer+basin -> Andesite Alloy
# ======================================================================
xf0, xf1 = next_zone("Alloy Wing", 12)

for z in LANES2:
    funnel(xf0, GROUND_Y + 1, z, "north" if z < WALKWAY_Z else "south", brass=False)
    basin(xf0 + 1, GROUND_Y + 1, z)
    mixer(xf0 + 1, GROUND_Y + 2, z)
    spine_tap(xf0 + 2, SPINE_Y, WALKWAY_Z, GROUND_Y + 2, z)
    funnel(xf0 + 2, GROUND_Y + 1, z, "east", brass=False)
    chest(xf0 + 3, GROUND_Y + 1, z, "south", "Andesite Alloy")
    # nugget tap: a small side-funnel injects Iron/Zinc Nugget into the basin
    funnel(xf0 + 1, GROUND_Y + 2, z + (1 if z < WALKWAY_Z else -1), "south" if z < WALKWAY_Z else "north",
           filtered_item="minecraft:iron_nugget", brass=True)

sign(xf0 + 1, GROUND_Y + 1, 1, ["Alloy Wing", "andesite + nugget", "mixer over basin", "-> andesite alloy"], rotation="8")

# ======================================================================
# ZONE G: BRASS WING
#   Copper + Zinc Ingot (1:1) -> 2x mixer+basin over KINDLED blaze
#   burners (charcoal-fed) -> Brass Ingot -> chest
# ======================================================================
xg0, xg1 = next_zone("Brass Wing", 12)

for z in LANES2:
    funnel(xg0, GROUND_Y + 1, z, "north" if z < WALKWAY_Z else "south", brass=True,
           )  # copper ingot intake (filter set in-game / see README)
    funnel(xg0, GROUND_Y + 2, z, "north" if z < WALKWAY_Z else "south",
           filtered_item="create:zinc_ingot", brass=True)  # zinc ingot intake, second layer
    basin(xg0 + 1, GROUND_Y + 2, z)
    mixer(xg0 + 1, GROUND_Y + 3, z)
    blaze_burner(xg0 + 1, GROUND_Y + 1, z, heat="kindled")  # directly beneath the basin
    spine_tap(xg0 + 2, SPINE_Y, WALKWAY_Z, GROUND_Y + 3, z)
    funnel(xg0 + 2, GROUND_Y + 2, z, "east", brass=False)
    chest(xg0 + 3, GROUND_Y + 2, z, "south", "Brass Ingots")
    # charcoal feed belt into the burner from the Timber Yard (see below);
    # the belt terminates adjacent to the burner, which pulls fuel items
    # off the belt automatically in Create -- no funnel needed here.
    belt_run_x(xg0 - 2, xg0, GROUND_Y, z, facing="east")

sign(xg0 + 1, GROUND_Y + 1, 1, ["Brass Wing", "copper + zinc ingot", "mixer + kindled burner", "charcoal-fed"], rotation="8")

# ======================================================================
# ZONE H: TIMBER YARD
#   Mechanical Saw + Deployer replant loop (closed-loop tree farm) ->
#   logs on belts -> furnace bank -> Charcoal -> Boiler Room + Brass Wing
# ======================================================================
xh0, xh1 = next_zone("Timber Yard", 20)

TREE_XS = [xh0 + 2, xh0 + 6, xh0 + 10, xh0 + 14]
for tx in TREE_XS:
    # Sapling growth column (oak); a mechanical saw contraption on a
    # vertical shaft rides up past the trunk (assembled in-game with a
    # wrench -- see README) and fells the tree, dropping logs onto the
    # collector belt at ground level. Deployer replants the sapling from
    # its own inventory immediately after (closed loop: never buys
    # saplings, since ~50% of saplings drop from leaves on average and
    # the deployer only needs to replant 1 per felled tree -- surplus
    # saplings simply accumulate as a buffer inside the deployer).
    place(tx, GROUND_Y + 1, 4, "minecraft:oak_sapling")
    place(tx, GROUND_Y + 1, 4, "minecraft:oak_sapling", overwrite=True)
    saw(tx, GROUND_Y + 2, 3, "north")
    deployer(tx, GROUND_Y + 1, 3, "north")  # replants sapling after felling
    for ly in range(GROUND_Y + 2, GROUND_Y + 6):
        place(tx, ly, 4, "minecraft:oak_log", {"axis": "y"}, overwrite=True)
    shaft(tx, GROUND_Y + 6, 3, "y")  # saw contraption rides this column

belt_run_x(xh0, xh1, GROUND_Y, 3, facing="east")  # log collector belt

FURNACE_ZS = [1, 2, 5, 11, 14, 15]
for i, z in enumerate(FURNACE_ZS):
    fx = xh0 + 8 + i
    funnel(fx, GROUND_Y + 2, z, "down", brass=False)  # log input, drops into furnace below
    furnace(fx, GROUND_Y + 1, z)
    belt_run_x(fx, xh1, GROUND_Y, z, facing="east")  # charcoal output

# Charcoal output merges onto two trunks: one feeds the Boiler Room
# (west-adjacent... actually east, see zone order), one loops back west
# to feed the Brass Wing burners (belt placed in Zone G already reaches
# to xg0-2; here we extend a return line from the Timber Yard to it).
belt_run_x(xh1, xh1 + 1, GROUND_Y + 2, 1, facing="east")   # -> Boiler Room (continues east)
belt_run_z(1, LANES2[0], xh0 - 1, GROUND_Y + 3, facing="south")
belt_run_x(xg0 - 2, xh0 - 1, GROUND_Y + 3, LANES2[0], facing="west")
belt_slope(xh0 - 1, GROUND_Y + 2, LANES2[0], "west", "downward")
belt_run_x(xg0 - 2, xh0 - 2, GROUND_Y, LANES2[0], facing="west", )

sign(xh0 + 1, GROUND_Y + 1, 1, ["Timber Yard", "saw + deployer", "closed sapling loop", "-> charcoal (furnaces)"], rotation="8")

# ======================================================================
# ZONE I: BOILER ROOM
#   3x Steam Engine + 3x Boiler (parallel), charcoal-fed, observation
#   glass into the Timber Yard and down onto the machine floor.
# ======================================================================
xi0, xi1 = next_zone("Boiler Room", 16)

BOILER_ZS = [3, 8, 13]
for i, z in enumerate(BOILER_ZS):
    bx = xi0 + 2 + i * 4
    boiler(bx, GROUND_Y + 1, z)
    steam_engine(bx + 1, GROUND_Y + 1, z, "east")
    # charcoal feed from the Timber Yard trunk
    funnel(bx, GROUND_Y + 2, z, "down", brass=False)
    belt_run_x(xh1 + 1, bx, GROUND_Y + 2, z, facing="east")
    # power output ties straight into the main spine
    spine_tap(bx + 2, SPINE_Y, WALKWAY_Z, GROUND_Y + 1, z)

# Observation glass: a window wall looking back into the Timber Yard, and
# a glass panel in the walkway floor looking down on the boilers.
for z in range(1, 16):
    if (xi0, GROUND_Y + 3, z) not in blocks:
        place(xi0, GROUND_Y + 3, z, "minecraft:glass")
glass_floor(xi0, xi1, 6, 10, WALKWAY_Y)

# --- Infinite lava network: Hose Pulley + tank + pipe trunk, feeding the
# cobblestone generator and the Andesite Wing presses ONLY (per spec;
# every other zone that needs heat uses charcoal-fed blaze burners
# instead of piped lava). ---
hose_pulley(xi1, GROUND_Y + 4, WALKWAY_Z, "down")
fluid_tank(xi1, GROUND_Y + 3, WALKWAY_Z)
place(xi1, GROUND_Y + 4, WALKWAY_Z + 1, "minecraft:lava")  # infinite source pool the pulley drains
LAVA_PIPE_Y = GROUND_Y  # trunk runs at ground level the entire way back west
for x in range(xa0 + 1, xi1 + 1):
    if (x, LAVA_PIPE_Y, WALKWAY_Z) not in blocks:
        fluid_pipe(x, LAVA_PIPE_Y, WALKWAY_Z)
# branch down to the cobblestone gen (Zone A) and up into the Andesite Wing
# taps already placed in Zone E.
fluid_pipe(xa0 + 1, LAVA_PIPE_Y, 3)
belt_run_z(WALKWAY_Z, 3, xa0 + 1, LAVA_PIPE_Y, facing="south")

sign(xi0 + 1, GROUND_Y + 1, 1, ["Boiler Room", "3x steam engine", "3x boiler", "charcoal-fed"], rotation="8")

# ======================================================================
# ZONE J: BUY DEPOT
#   Lever/sign resource selector, mechanical arm pulls a fixed batch to
#   the pickup depot on Diamond deposit. Diamonds -> visible vault chest.
# ======================================================================
xj0, xj1 = next_zone("Buy Depot", 14)

DEPOT_RATES = [
    ("Iron Ingot", 32), ("Gold Ingot", 16), ("Copper Ingot", 32),
    ("Zinc Ingot", 32), ("Andesite Alloy", 24), ("Brass Ingot", 16),
    ("Andesite", 64),
]
for i, (label, rate) in enumerate(DEPOT_RATES):
    z = 1 + i * 2
    lever(xj0 + 1, GROUND_Y + 2, z)
    sign(xj0, GROUND_Y + 1, z, [label, f"1 Diamond =", f"{rate}x", ""], rotation="4")
    chest(xj0 + 2, GROUND_Y + 1, z, "south", f"Depot: {label}")

mechanical_arm(xj0 + 4, GROUND_Y + 2, 8)
chest(xj0 + 6, GROUND_Y + 1, 8, "south", "Diamond Deposit (input)")
chest(xj0 + 8, GROUND_Y + 1, 8, "south", "Pickup Depot (output)")
# Visible vault: diamonds paid in are stored here behind glass.
place(xj0 + 6, GROUND_Y + 2, 8, "minecraft:glass")
chest(xj1, GROUND_Y + 1, WALKWAY_Z, "south", "Diamond Vault")

sign(xj0 + 1, GROUND_Y + 1, 1, ["Buy Depot", "lever selects item", "arm delivers batch", "diamonds -> vault"], rotation="8")

# ======================================================================
# WALKWAY, SPINE, FLOOR/ROOF/SCAFFOLDING (built last, over the finished
# footprint, so it never collides with machine placements)
# ======================================================================

X_MIN, X_MAX = 0, X - 1  # X was advanced past the last gap by next_zone()
Z_MIN, Z_MAX = 0, 16

# Ground floor (stone) and roof (andesite), full footprint.
floor_plane(X_MIN, X_MAX, Z_MIN, Z_MAX, GROUND_Y, "minecraft:stone")
floor_plane(X_MIN, X_MAX, Z_MIN, Z_MAX, ROOF_Y, "minecraft:andesite")

# Central elevated walkway: glass floor at WALKWAY_Y, running the full
# length at Z=WALKWAY_Z-1..WALKWAY_Z+1 (3 wide), with andesite/brass/copper
# scaffolding posts every 6 blocks holding it up, and the main kinetic
# spine directly beneath it.
for x in range(X_MIN, X_MAX + 1):
    for z in (WALKWAY_Z - 1, WALKWAY_Z, WALKWAY_Z + 1):
        if (x, WALKWAY_Y, z) not in blocks:
            place(x, WALKWAY_Y, z, "minecraft:glass")
    if (x, SPINE_Y, WALKWAY_Z) not in blocks:
        shaft(x, SPINE_Y, WALKWAY_Z, "x")
    if x % 6 == 0:
        for y in (GROUND_Y + 1, GROUND_Y + 2, GROUND_Y + 3, GROUND_Y + 4, GROUND_Y + 5):
            for z in (WALKWAY_Z - 1, WALKWAY_Z + 1):
                if (x, y, z) not in blocks:
                    place(x, y, z, "minecraft:andesite" if x % 12 == 0 else "create:copper_block" if False else "minecraft:andesite")

# Scaffolding: brass/andesite/copper trim posts at every zone boundary,
# and a stone/andesite/copper palette perimeter wall (low, open showcase
# style, not fully enclosing) along the north and south edges.
for x in range(X_MIN, X_MAX + 1, 4):
    for z in (Z_MIN, Z_MAX):
        for y in range(GROUND_Y + 1, GROUND_Y + 4):
            if (x, y, z) not in blocks:
                place(x, y, z, "minecraft:andesite")

# Entry sign at the west end introducing the whole build.
sign(X_MIN, GROUND_Y + 1, WALKWAY_Z, ["Sevenline Foundry", "7 outputs, fully", "renewable & parallel", "-> see chests"], rotation="4")


# ======================================================================
# Assemble & write the structure NBT
# ======================================================================

def build_nbt():
    xs = [p[0] for p in blocks]
    ys = [p[1] for p in blocks]
    zs = [p[2] for p in blocks]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)

    size = [max_x - min_x + 1, max_y - min_y + 1, max_z - min_z + 1]

    palette_list = []
    palette_index = {}

    def palette_id(name, props):
        key = (name, tuple(sorted(props.items())))
        if key in palette_index:
            return palette_index[key]
        entry = {"Name": String(name)}
        if props:
            entry["Properties"] = Compound({k: String(v) for k, v in sorted(props.items())})
        palette_list.append(Compound(entry))
        idx = len(palette_list) - 1
        palette_index[key] = idx
        return idx

    block_list = []
    for (x, y, z), data in sorted(blocks.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        state = palette_id(data["name"], data["props"])
        entry = {
            "pos": List[Int]([Int(x - min_x), Int(y - min_y), Int(z - min_z)]),
            "state": Int(state),
        }
        if data["nbt"] is not None:
            entry["nbt"] = data["nbt"]
        block_list.append(Compound(entry))

    root = Compound({
        "DataVersion": Int(3465),  # Minecraft 1.20.1
        "size": List[Int]([Int(size[0]), Int(size[1]), Int(size[2])]),
        "entities": List[Compound]([]),
        "blocks": List[Compound](block_list),
        "palette": List[Compound](palette_list),
    })
    return root, size


def main():
    root, size = build_nbt()
    out_path = os.path.join(os.path.dirname(__file__), "sevenline_foundry.nbt")
    nbtlib.File(root, gzipped=True).save(out_path)
    print(f"Wrote {out_path}")
    print(f"Structure size (X,Y,Z): {size}")
    print(f"Total blocks placed: {len(blocks)}")
    print(f"Zone starts: {ZONE_STARTS}")


if __name__ == "__main__":
    main()
