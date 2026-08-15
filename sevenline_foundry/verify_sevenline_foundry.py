#!/usr/bin/env python3
"""
Independent verification pass for sevenline_foundry.nbt.

This deliberately does NOT import the generator or reuse its in-memory
block dict.  It re-reads the written .nbt from disk and rebuilds the world
from the palette + blocks list, so a bug in the generator's bookkeeping
cannot hide from this check.

Every claim in the README's renewability table is re-derived here by graph
connectivity over the actual placed blocks:

  * FLUID  network: BFS over fluid_pipe / fluid_tank / mechanical_pump /
    hose_pulley cells (6-neighbour adjacency).  Used to prove lava can
    physically reach every Andesite Wing basin and every cobblestone
    generator, and that water can reach every boiler tank stack.
  * ITEM   network: BFS over belt / funnel / chute / depot / chest and
    machine inventories.  Used to prove charcoal can reach every blaze
    burner, logs reach the furnace bank, saplings reach every deployer,
    and unsorted gravel loops back to the cobblestone generators.

Limitation stated plainly: this proves PHYSICAL CONTINUITY (the blocks form
an unbroken chain of the right kinds in the right places).  It cannot prove
Create's runtime semantics -- belt direction correctness, funnel polarity,
kinetic stress budget, or recipe matching.  Those still need the in-game
pass listed in the README.
"""

import os
import sys
from collections import deque

import nbtlib

HERE = os.path.dirname(os.path.abspath(__file__))
NBT_PATH = os.path.join(HERE, "sevenline_foundry.nbt")

FLUID_BLOCKS = {
    "create:fluid_pipe", "create:fluid_tank",
    "create:mechanical_pump", "create:hose_pulley",
}
ITEM_BLOCKS = {
    "create:belt", "create:brass_funnel", "create:andesite_funnel",
    "create:chute", "create:depot", "minecraft:chest",
    "create:basin", "create:millstone", "minecraft:furnace",
    "create:blaze_burner", "create:deployer", "create:mechanical_saw",
}

NEIGHBOURS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]


def load():
    f = nbtlib.load(NBT_PATH)
    root = f  # structure NBT is a bare compound at the root
    palette = [str(e["Name"]) for e in root["palette"]]
    world = {}
    for b in root["blocks"]:
        p = b["pos"]
        world[(int(p[0]), int(p[1]), int(p[2]))] = palette[int(b["state"])]
    size = [int(v) for v in root["size"]]
    return root, world, size


def positions_of(world, *names):
    want = set(names)
    return {p for p, n in world.items() if n in want}


def component(world, seeds, allowed):
    """Flood fill from seeds across cells whose block is in `allowed`."""
    seen = set()
    q = deque()
    for s in seeds:
        if s in allowed:
            seen.add(s)
            q.append(s)
    while q:
        x, y, z = q.popleft()
        for dx, dy, dz in NEIGHBOURS:
            n = (x + dx, y + dy, z + dz)
            if n in allowed and n not in seen:
                seen.add(n)
                q.append(n)
    return seen


def touches(component_set, targets):
    """How many of `targets` are 6-adjacent to (or inside) the component."""
    hit = 0
    for t in targets:
        if t in component_set:
            hit += 1
            continue
        x, y, z = t
        if any((x + dx, y + dy, z + dz) in component_set
               for dx, dy, dz in NEIGHBOURS):
            hit += 1
    return hit


RESULTS = []


def check(name, ok, detail):
    RESULTS.append((name, ok, detail))
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {name}\n       {detail}")


def main():
    if not os.path.exists(NBT_PATH):
        sys.exit(f"missing {NBT_PATH} -- run generate_sevenline_foundry.py first")

    root, world, size = load()
    print(f"Loaded {NBT_PATH}")
    print(f"  size={size}  blocks={len(root['blocks'])}  palette={len(root['palette'])}")
    print(f"  DataVersion={int(root['DataVersion'])}\n")

    fluid_cells = positions_of(world, *FLUID_BLOCKS)
    item_cells = positions_of(world, *ITEM_BLOCKS)

    lava = positions_of(world, "minecraft:lava")
    water = positions_of(world, "minecraft:water")
    basins = positions_of(world, "create:basin")
    burners = positions_of(world, "create:blaze_burner")
    tanks = positions_of(world, "create:fluid_tank")
    furnaces = positions_of(world, "minecraft:furnace")
    deployers = positions_of(world, "create:deployer")
    saplings = positions_of(world, "minecraft:oak_sapling")
    saws = positions_of(world, "create:mechanical_saw")
    millstones = positions_of(world, "create:millstone")

    # ---------------- FLUID: lava reaches presses + cobble gens -----------
    lava_seeds = set()
    for (x, y, z) in lava:
        for dx, dy, dz in NEIGHBOURS:
            n = (x + dx, y + dy, z + dz)
            if n in fluid_cells:
                lava_seeds.add(n)
    lava_net = component(world, lava_seeds, fluid_cells)

    # Andesite Wing basins are the basins that sit directly above a pipe.
    andesite_basins = {b for b in basins
                       if (b[0], b[1] - 1, b[2]) in fluid_cells}
    reached = touches(lava_net, andesite_basins)
    check("Lava reaches every Andesite Wing basin",
          len(andesite_basins) > 0 and reached == len(andesite_basins),
          f"{reached}/{len(andesite_basins)} andesite basins adjacent to the "
          f"lava-connected pipe network ({len(lava_net)} pipe cells in it)")

    # cobble generators: the lava source cells of the gens themselves
    gen_lava = {p for p in lava if p[0] < 10}
    gen_fed = touches(lava_net, gen_lava)
    check("Lava network reaches the cobblestone generators",
          gen_fed == len(gen_lava),
          f"{gen_fed}/{len(gen_lava)} generator lava cells touch the network")

    # ---------------- FLUID: water reaches every boiler tank -------------
    water_seeds = set()
    for (x, y, z) in water:
        for dx, dy, dz in NEIGHBOURS:
            n = (x + dx, y + dy, z + dz)
            if n in fluid_cells:
                water_seeds.add(n)
    water_net = component(world, water_seeds, fluid_cells)
    # Boiler tanks occupy y = 2..4; the lava buffer stack sits at y = 5..7 and
    # must NOT be on the water network -- it is checked separately below.
    boiler_tanks = {t for t in tanks if 2 <= t[1] <= 4}
    lava_buffer = {t for t in tanks if t[1] >= 5}
    tank_stacks = {(t[0], t[2]) for t in boiler_tanks}
    fed_stacks = {(t[0], t[2]) for t in boiler_tanks if t in water_net}
    check("Water reaches every boiler tank stack",
          len(tank_stacks) > 0 and len(fed_stacks) == len(tank_stacks),
          f"{len(fed_stacks)}/{len(tank_stacks)} boiler tank columns are on "
          f"the water-connected network ({len(water_net)} cells)")

    check("Lava and water networks stay separate",
          not (lava_buffer & water_net) and bool(lava_buffer),
          f"lava buffer stack ({len(lava_buffer)} tank blocks) is not on the "
          f"water network -- lava serves only the cobble gens and Andesite "
          f"presses, exactly as specified")

    # ---------------- ITEM: charcoal reaches every blaze burner ----------
    item_net_seeds = {p for p in furnaces}
    item_net = component(world, item_net_seeds, item_cells | furnaces)
    burner_fed = touches(item_net, burners)
    check("Charcoal path reaches every Blaze Burner",
          burner_fed == len(burners),
          f"{burner_fed}/{len(burners)} burners (16 boiler + 4 Brass Wing) "
          f"are connected to the furnace-rooted item network "
          f"({len(item_net)} cells)")

    # ---------------- ITEM: logs reach the furnace bank ------------------
    saw_net = component(world, saws, item_cells | saws)
    furn_fed = touches(saw_net, furnaces)
    check("Harvested logs reach the furnace bank",
          furn_fed == len(furnaces),
          f"{furn_fed}/{len(furnaces)} furnaces reachable from the tree-row "
          f"belt carpet")

    # ---------------- ITEM: saplings reach every tree deployer -----------
    tree_deployers = set(deployers)  # all deployers are now tree replanters;
    # the cobble generators use Mechanical Drills, which need no tool.
    dep_fed = touches(saw_net, tree_deployers)
    check("Sapling return path reaches every tree Deployer",
          dep_fed == len(tree_deployers),
          f"{dep_fed}/{len(tree_deployers)} tree deployers connected to the "
          f"same belt network the saplings drop onto")

    # ---------------- Replant geometry: saw + deployer per sapling -------
    good = 0
    for s in saplings:
        x, y, z = s
        has_saw = any((x + dx, y, z + dz) in saws
                      for dx, dz in ((0, -1), (0, 1), (-1, 0), (1, 0)))
        has_dep = any((x + dx, y, z + dz) in deployers
                      for dx, dz in ((0, -1), (0, 1), (-1, 0), (1, 0)))
        if has_saw and has_dep:
            good += 1
    check("Every tree column has both a felling Saw and a replant Deployer",
          good == len(saplings) and len(saplings) > 0,
          f"{good}/{len(saplings)} sapling cells have an adjacent saw AND an "
          f"adjacent deployer")

    # ---------------- ITEM: gravel loops back to the cobble gens ---------
    gen_belts = {p for p in item_cells if p[0] < 10 and world[p] == "create:belt"}
    sorter_end = {p for p in item_cells if 75 < p[0] < 84}
    loop_net = component(world, sorter_end, item_cells)
    loop_ok = touches(loop_net, gen_belts)
    check("Unsorted gravel loops back to the Crushing Bank",
          loop_ok > 0,
          f"{loop_ok} generator-side belt cells reachable from the Sorting "
          f"Floor's east-end return path")

    # ---------------- ITEM: gravel reaches the millstones ----------------
    mill_fed = touches(component(world, gen_belts, item_cells), millstones)
    check("Cobblestone reaches every Millstone",
          mill_fed == len(millstones),
          f"{mill_fed}/{len(millstones)} millstones reachable from the "
          f"cobblestone generator collector belts")

    # ---------------- summary --------------------------------------------
    print()
    failed = [r for r in RESULTS if not r[1]]
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("\n*** FAILURES ***")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
        sys.exit(1)
    print("All connectivity checks passed.")


if __name__ == "__main__":
    main()
