#!/usr/bin/env python3
"""
Build "Quad-Wash Ingot Factory" as a Create-mod Schematicannon-compatible
structure NBT file (vanilla Java Edition structure-block schema), using nbtlib.

Layout summary (see README.md for the full explanation and caveats):

  X axis = the 4 parallel "lanes" (Iron, Gold, Copper, Zinc), each its own
           column running from the wash basin through to its ingot chest.
  Z axis = the process stages, low Z -> high Z:
           z=1  cobblestone->gravel distribution belt ("Spine A") + millstone
           z=2  unfiltered tap funnels (Spine A -> wash basin)
           z=3  wash basins (y=2) / water wheels (y=3) / water source (y=4)
                and the nugget merge belt "Spine B" directly below (y=1)
           z=4-5 filtered diversion belts rising off Spine B
           z=6  slope down to press level
           z=7  filtered tap funnel (side belt -> press basin)
           z=8  press basins (y=2) / mechanical presses (y=3), ingot chests
  y=0    open build floor (mostly unused / clear)
  y=3    shared kinetic "spine" (shaft/gearbox/cogwheel trunk), z=0, running
         the length of the build; the 4 water wheels are the only power
         source and drive everything else through this trunk.

This script does not simulate Create's actual physics -- it places real
Create/vanilla block IDs, blockstates, and block-entity NBT in the positions
this design calls for. See README.md for what to double-check in-game.
"""

import os
import nbtlib
from nbtlib import Compound, List, Int, String, Byte, Float

# --------------------------------------------------------------------------
# Block-placement bookkeeping
# --------------------------------------------------------------------------

blocks = {}  # (x, y, z) -> {"name": str, "props": dict, "nbt": Compound|None}


def place(x, y, z, name, props=None, nbt=None):
    key = (x, y, z)
    if key in blocks:
        raise ValueError(
            f"Collision at {key}: '{blocks[key]['name']}' already placed, "
            f"tried to place '{name}'"
        )
    blocks[key] = {"name": name, "props": dict(props or {}), "nbt": nbt}


def shaft(x, y, z, axis):
    place(x, y, z, "create:shaft", {"axis": axis})


def cogwheel(x, y, z, axis):
    place(x, y, z, "create:cogwheel", {"axis": axis})


def gearbox(x, y, z):
    # Gearbox performs a 90-degree kinetic redirect; no axis property assumed.
    place(x, y, z, "create:gearbox")


def belt_run_x(x_start, x_end, y, z, facing):
    """Place a straight horizontal belt run along X from x_start to x_end
    (inclusive, either direction), all at fixed y/z."""
    step = 1 if x_end >= x_start else -1
    xs = list(range(x_start, x_end + step, step))
    n = len(xs)
    for i, x in enumerate(xs):
        part = "start" if i == 0 else ("end" if i == n - 1 else "middle")
        place(x, y, z, "create:belt", {"part": part, "facing": facing, "slope": "horizontal"})


def belt_slope(x, y, z, facing, slope, part="middle"):
    place(x, y, z, "create:belt", {"part": part, "facing": facing, "slope": slope})


def funnel(x, y, z, facing, filtered_item=None, brass=True):
    name = "create:brass_funnel" if brass else "create:andesite_funnel"
    nbt = None
    if filtered_item is not None:
        block_entity_id = name
        nbt = Compound({
            "id": String(block_entity_id),
            "Filter": Compound({"id": String(filtered_item), "Count": Byte(1)}),
            "FilterMatchNBT": Byte(0),
        })
    place(x, y, z, name, {"facing": facing}, nbt)


def chest(x, y, z, facing, label):
    nbt = Compound({
        "id": String("minecraft:chest"),
        "CustomName": String('{"text":"%s"}' % label),
    })
    place(x, y, z, "minecraft:chest", {"facing": facing}, nbt)


# --------------------------------------------------------------------------
# Metal lanes
# --------------------------------------------------------------------------
# (name, wash-basin X, filter/press-lane X, nugget item id, ingot item name)
LANES = [
    ("Iron", 3, 4, "minecraft:iron_nugget", "Iron Ingots"),
    ("Gold", 6, 7, "minecraft:gold_nugget", "Gold Ingots"),
    ("Copper", 9, 10, "minecraft:copper_nugget", "Copper Ingots"),
    ("Zinc", 12, 13, "create:zinc_nugget", "Zinc Ingots"),
]

MILL_X = 18          # millstone / generator column
LEFTOVER_X = 15       # spine-B tap point for unmatched (leftover) items
SPINE_Z = 0            # z-row of the shared kinetic trunk
SPINE_Y = 3

# --------------------------------------------------------------------------
# 1. Cobblestone generator (manual/assisted harvesting -- see README)
#    Placed east of the millstone (higher X) so it stays clear of Spine A,
#    which runs west of the millstone.
# --------------------------------------------------------------------------
GEN_X = MILL_X + 8
place(GEN_X - 1, 1, 1, "minecraft:water")
place(GEN_X + 1, 1, 1, "minecraft:lava")
# (GEN_X, 1, 1) is left empty/air -- that is the cell where cobblestone forms.

# Deployer placeholder: powered but with an empty inventory. Insert a
# pickaxe and set it to "Punch" mode with a wrench in-game (see README).
place(GEN_X, 2, 1, "create:deployer", {"facing": "down"})

# Collector belt catches the cobblestone item when it is broken and carries
# it west toward the millstone's lift funnels.
belt_run_x(GEN_X, MILL_X, 0, 1, facing="west")

# --------------------------------------------------------------------------
# 2. Millstone
# --------------------------------------------------------------------------
funnel(MILL_X, 1, 1, "up", brass=False)   # lift cobblestone belt(y0) -> y1
funnel(MILL_X, 2, 1, "up", brass=False)   # lift y1 -> millstone(y3)
place(MILL_X, 3, 1, "create:millstone")
gearbox(MILL_X, SPINE_Y, SPINE_Z)          # power tap directly off the spine

# Catch popped-up milled output above the millstone and send it toward
# Spine A (west, decreasing X).
funnel(MILL_X, 4, 1, "west", brass=False)

# Two-step slope down from the catch funnel's output height (y4) to Spine
# A's working height (y2), landing a few blocks west.
belt_slope(MILL_X - 1, 4, 1, facing="west", slope="horizontal", part="start")
belt_slope(MILL_X - 2, 3, 1, facing="west", slope="downward")
belt_slope(MILL_X - 3, 2, 1, facing="west", slope="downward", part="end")

# --------------------------------------------------------------------------
# 3. Spine A: gravel distribution belt (z=1, y=2), feeding all 4 wash basins
# --------------------------------------------------------------------------
spine_a_xs = list(range(2, MILL_X - 3))
spine_a_xs.reverse()  # travels west (already decreasing); explicit for clarity
for i, x in enumerate(spine_a_xs):
    if (x, 2, 1) in blocks:
        continue
    part = "start" if x == spine_a_xs[0] else ("end" if x == spine_a_xs[-1] else "middle")
    place(x, 2, 1, "create:belt", {"part": part, "facing": "west", "slope": "horizontal"})

# --------------------------------------------------------------------------
# 4. Four wash-basin units + water wheels (the kinetic power source)
# --------------------------------------------------------------------------
for name, bx, fx, nugget, ingot_label in LANES:
    # Unfiltered tap: Spine A -> basin (horizontal bridge, all at y=2)
    funnel(bx, 2, 2, "south", brass=False)
    place(bx, 2, 3, "create:basin")

    # Water wheel directly above the basin (one level higher than the
    # diverting belts at y=3, so the wheel row's kinetic line never crosses
    # the filtered belts); water source directly above the wheel.
    place(bx, 4, 3, "create:water_wheel", {"facing": "east"})
    place(bx, 5, 3, "minecraft:water")

    # Nugget output: basin auto-drops onto Spine B directly beneath it (y1).
    # (see README - verify basin auto-output in-game)

# Wheel row kinetic line: wheel-shaft/cogwheel-shaft/cogwheel-wheel..., axis=x
wheel_xs = [lane[1] for lane in LANES]
connector_xs = [x for x in range(wheel_xs[0], wheel_xs[-1] + 1) if x not in wheel_xs]
TAP_X = 7  # connector position between Gold(6) and Copper(9) wheels
for x in connector_xs:
    if x == TAP_X:
        continue  # replaced by a gearbox below
    cogwheel(x, 4, 3, "x")

# Tap from the wheel row down to the shared spine: turn off the wheel row's
# X-axis, run a Z-axis shaft south to the spine's row, then one more gearbox
# drops the remaining single Y level onto the spine itself.
gearbox(TAP_X, 4, 3)
shaft(TAP_X, 4, 2, "z")
shaft(TAP_X, 4, 1, "z")
gearbox(TAP_X, 4, SPINE_Z)  # drops onto the spine cell directly below it

# --------------------------------------------------------------------------
# 5. Spine B: nugget merge belt (z=3, y=1), running under all 4 basins
# --------------------------------------------------------------------------
spine_b_x_min = 2
spine_b_x_max = LEFTOVER_X
for x in range(spine_b_x_min, spine_b_x_max + 1):
    part = "start" if x == spine_b_x_min else ("end" if x == spine_b_x_max else "middle")
    place(x, 1, 3, "create:belt", {"part": part, "facing": "east", "slope": "horizontal"})

# --------------------------------------------------------------------------
# 6. Four brass filter funnels + side belts + presses + chests
# --------------------------------------------------------------------------
for name, bx, fx, nugget, ingot_label in LANES:
    # Lift the matching nugget off Spine B into the diverting belt above.
    funnel(fx, 2, 3, "up", filtered_item=nugget, brass=True)

    # Diverting belt: travels north (+z here means away from Spine B) then
    # slopes down to press-basin height.
    place(fx, 3, 3, "create:belt", {"part": "start", "facing": "south", "slope": "horizontal"})
    place(fx, 3, 4, "create:belt", {"part": "middle", "facing": "south", "slope": "horizontal"})
    place(fx, 3, 5, "create:belt", {"part": "middle", "facing": "south", "slope": "horizontal"})
    place(fx, 2, 6, "create:belt", {"part": "end", "facing": "south", "slope": "downward"})

    # Horizontal bridge into the press basin.
    funnel(fx, 2, 7, "south", brass=False)
    place(fx, 2, 8, "create:basin")

    # Mechanical press directly above the basin.
    place(fx, 3, 8, "create:mechanical_press", {"facing": "down"})

    # Power riser: spine -> straight shaft column at fx+1 -> touches the press.
    px = fx + 1
    gearbox(px, SPINE_Y, SPINE_Z)
    for z in range(1, 8):
        shaft(px, SPINE_Y, z, "z")
    # (px, SPINE_Y, 8) intentionally omitted: the last shaft at z=7 already
    # sits adjacent to the press at (fx, SPINE_Y, 8).

    # Ingot output -> labeled chest.
    funnel(fx - 1, 2, 8, "west", brass=False)
    chest(fx - 2, 2, 8, "south", ingot_label)

# --------------------------------------------------------------------------
# 7. Leftover loop-back: unmatched items continue past all 4 filters, get
#    lifted, ride an elevated overpass belt east past the millstone, then
#    descend and drop (via a down-facing funnel) onto the same collector
#    belt that carries fresh cobblestone -- both feed the millstone.
# --------------------------------------------------------------------------
funnel(LEFTOVER_X, 2, 3, "up", brass=False)  # unfiltered lift off Spine B
place(LEFTOVER_X, 3, 3, "create:belt", {"part": "start", "facing": "north", "slope": "horizontal"})
place(LEFTOVER_X, 4, 2, "create:belt", {"part": "middle", "facing": "north", "slope": "upward"})
place(LEFTOVER_X, 5, 1, "create:belt", {"part": "middle", "facing": "east", "slope": "horizontal"})
for x in range(LEFTOVER_X + 1, MILL_X + 2):
    place(x, 5, 1, "create:belt", {"part": "middle", "facing": "east", "slope": "horizontal"})
DESCENT_X = MILL_X + 2
place(DESCENT_X, 4, 1, "create:belt", {"part": "middle", "facing": "east", "slope": "downward"})
place(DESCENT_X + 1, 3, 1, "create:belt", {"part": "middle", "facing": "east", "slope": "downward"})
place(DESCENT_X + 2, 2, 1, "create:belt", {"part": "end", "facing": "east", "slope": "downward"})
funnel(DESCENT_X + 2, 1, 1, "down", brass=False)
# Drops onto the collector belt from section 1, which already covers this cell.

# --------------------------------------------------------------------------
# 8. Spine trunk: straight shaft/cogwheel run tying every gearbox tap
#    together (z=0, y=3), alternating shaft/cogwheel for variety.
# --------------------------------------------------------------------------
spine_taps = sorted({TAP_X, MILL_X} | {fx + 1 for _, _, fx, _, _ in LANES})
x_min, x_max = min(spine_taps), max(spine_taps)
for x in range(x_min, x_max + 1):
    if (x, SPINE_Y, SPINE_Z) in blocks:
        continue  # gearbox already placed here
    if x % 2 == 0:
        cogwheel(x, SPINE_Y, SPINE_Z, "x")
    else:
        shaft(x, SPINE_Y, SPINE_Z, "x")

# --------------------------------------------------------------------------
# Assemble & write the structure NBT
# --------------------------------------------------------------------------

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
    for (x, y, z), data in sorted(blocks.items(), key=lambda kv: (kv[0][2], kv[0][1], kv[0][0])):
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
    out_path = os.path.join(os.path.dirname(__file__), "quad_wash_ingot_factory.nbt")
    nbtlib.File(root, gzipped=True).save(out_path)
    print(f"Wrote {out_path}")
    print(f"Structure size (X,Y,Z): {size}")
    print(f"Total blocks placed: {len(blocks)}")


if __name__ == "__main__":
    main()
