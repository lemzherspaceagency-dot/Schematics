# Liquid Experience Goggles

A client-side Forge addon for **Create: Enchantment Industry** on Minecraft 1.18.2.

Create's Engineer's Goggles already tell you a tank holds `1,395mB` of Liquid Experience.
They do not tell you that this is exactly a level-30 enchant. This adds that line.

```
Fluid Container:
     Liquid Experience
     1,395mB / 8,000mB
     30 levels                 <- added
     You: 12 → 31  (+19)       <- added, while sneaking
```

## What it hooks

One injection covers every fluid-holding machine in both mods, because they all delegate to
the same default method on Create's goggle interface, `containedFluidTooltip`:

| Mod | Blocks covered |
|---|---|
| Create | Fluid Tank, Spout, Item Drain |
| Enchantment Industry | Blaze Enchanter, Disenchanter, Printer |

No block entity class is named anywhere, so machines added later are picked up for free.

## Client-only

The mod registers no blocks, items, fluids, recipes or packets. It reads only block entity
data the server already sends so the client can render fluid inside a tank — `TankContent`
is written unconditionally in Create's `write`, not gated behind `!clientPacket`.

It declares `IGNORESERVERONLY`, so servers neither need it nor notice it, and it will not
stop you joining a server that lacks it. If the jar does end up in a server's mods folder,
the mixin plugin checks the physical side and applies nothing.

## Create version compatibility

Create moved `IHaveGoggleInformation` between releases, so the mod ships one hook per
package layout and picks whichever resolves at load time:

| Create | Package | Hook |
|---|---|---|
| 0.5.1 and later | `content.equipment.goggles` | `ModernGoggleMixin` |
| 0.5.0 and earlier | `content.contraptions.goggles` | `LegacyGoggleMixin` |

The method signature — `containedFluidTooltip(List<Component>, boolean, LazyOptional<IFluidHandler>)`
— is byte-for-byte identical across both, so only the owning class name varies. Selection
happens in `ExpGogglesMixinPlugin`, which probes for the classes through Mixin's bytecode
provider rather than `Class.forName`, so nothing is class-loaded prematurely.

Create 6 (1.21.1) changed the signature to take a bare `IFluidHandler` and moved to
NeoForge, so it is not reachable from a Forge 1.18.2 jar and would need its own build.

No mod source file imports a Create class. The hooks name their target as a string and the
tooltip is built from vanilla components rather than Create's `Lang` builders — that
utility package was reorganised more than once and moved out to Catnip in Create 6.

## The conversion

`1 mB of Liquid Experience = 1 experience point`, and Hyper Experience is 10 points per mB.
Both were read from CEI's source rather than a wiki: `ExperienceFluid` is constructed with
`xpRatio = 1` and `HyperExperienceFluid` calls `super(10, properties)`. Those ratios are
unchanged on every CEI release from 1.18.2 through 1.21.1; the Hyper fluid simply stops
existing in CEI 2.x.

Points are not levels. The vanilla curve costs `2L+7` per level below 15, `5L−38` to 29 and
`9L−158` from 30 up, so a bucket is worth level 26 rather than anything near 30. Inverting
it uses the closed-form root of the cumulative curve, corrected onto the exact integer
boundary — `Math.sqrt` lands a fraction below the true root on inputs sitting exactly on a
boundary, which would otherwise report a full tank of enchant fuel as level 29.

All totals are computed in `long`: a tank may hold up to `Integer.MAX_VALUE` mB, and the
cumulative cost of the resulting level (21,863) overflows a 32-bit int.

## Config

`config/expgoggles-client.toml`, client-side only:

| Key | Default | Meaning |
|---|---|---|
| `showLevels` | `true` | The level readout |
| `showProjection` | `true` | The "where this would leave you" line |
| `projectionRequiresSneak` | `true` | Only show that line while sneaking |
| `additionalExperienceFluids` | `[]` | Other mods' experience fluids |

The last accepts `modid:fluid=points` or `modid:fluid=points/millibuckets`, e.g.
`cofh_core:experience=1/25` for a fluid where 25 mB makes one point. CEI's own fluids are
built in and need no entry.

## Building

Requires a **Java 17** toolchain — ForgeGradle 5 does not run on newer JDKs.

```
./gradlew build
```

The jar lands in `build/libs/`. `./gradlew runClient` starts a dev client with Create.
