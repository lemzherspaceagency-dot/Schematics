# ANTINODE

**Where the waves agree, the world becomes solid.**

Alpha 0.1 — a 3D game about building with wave interference.

You are alone in the Vault: a lightless cavern with a Core at its heart. You
never place a block and you never mine one. Instead you anchor **emitters**.
Each one floods the open space with a travelling wave that bends around rock
and dies out with distance. The waves sum. Where their crests reinforce past a
threshold, matter **condenses** into crystal. Where they cancel, matter
**sublimes** back into nothing.

So you build by tuning: wavelength, power, phase. Move an emitter half a
wavelength and a bridge you spent a minute growing evaporates and reappears
somewhere else.

Something else is down here. The **Bloom** is a crust that spreads across
anything solid — fast over the crystal you make, slow over bare stone. Every
structure you condense is a road you have built for it. It cannot cross empty
space, and it dies where the waves cancel, so the counterplay is to dissolve
your own work out from under it.

**A chamber is cleared** when all three Anchors are joined to the Core by a
continuous path of clean condensate, and you hold that lattice intact long
enough to stabilise it. **You lose** when the Bloom touches the Core.

## Controls

| Input | Action |
|---|---|
| Mouse | Look |
| `W` `A` `S` `D` | Fly |
| `Space` / `Ctrl` | Rise / descend |
| `Shift` | Boost |
| `1`–`5` | Select emitter |
| `F` | Anchor the selected emitter where you are aiming |
| `Q` / `E` | Wavelength down / up |
| `Z` / `X` | Power down / up |
| `C` / `V` | Phase back / forward |
| `R` | Switch the selected emitter on or off |
| `Tab` | Show or hide the live wave field |
| `Esc` | Pause |
| `F3` | Debug readout |
| `F5` | Store state |

Cyan motes mark where the field is reinforcing toward matter; magenta motes
mark where it is cancelling matter away. Power is a shared budget across all
emitters — reach or precision, not both.

## Playing it

Anchor two emitters on opposite sides of a gap with the *same* wavelength and
*matching* phase. The band of crystal that appears between them is the set of
points where both waves arrive in step. Widen the wavelength to make thicker,
sparser shells; shorten it for a fine lattice. To cut the Bloom off a bridge,
put a third emitter beside the infected span and turn its phase until the span
goes magenta in the overlay — then it dissolves, and the Bloom on it dies with
it.

## Running

Download the installer from `dist/`, run it, and launch ANTINODE from the
Start Menu. It needs 64-bit Windows and a graphics driver with OpenGL 3.3
(anything from about 2010 onward). The executable is self-contained — no
runtime to install, no data folder beside it. Saves go to
`%APPDATA%\Antinode`.

Command line: `--width N --height N --seed N --new --selftest`.

## Building from source

The game is C11 with no third-party dependencies. Every texture, the font and
the icon are generated procedurally at build or startup.

```sh
make                # native build (X11/GLX) for development
make test           # headless self-test under Xvfb
make windows        # cross-compiled, statically linked Antinode.exe
make installer      # the exe plus an NSIS installer, into dist/
```

Cross-compiling and packaging need `mingw-w64` and `nsis`. The headless test
needs `xvfb` and a Mesa software rasteriser.

### Layout

| File | What it does |
|---|---|
| `src/ff_vault.c` | The chamber, geodesic wave propagation, the interference field, the material rules, the Bloom automaton, connectivity |
| `src/ff_game.c` | Flight, emitter tuning, objective, HUD and screens |
| `src/ff_mesh.c` | Chunk meshing with per-vertex ambient occlusion |
| `src/ff_render.c` | Shaders, the procedural texture atlas, the renderer |
| `src/ff_ui.c` | Batched 2D overlay and the inline 5×7 bitmap font |
| `src/ff_gl.c` | Minimal OpenGL 3.3 loader — no GLEW, no GLAD |
| `src/plat_win32.c` | Win32 + WGL backend (the shipping build) |
| `src/plat_x11.c` | X11 + GLX backend (development and automated testing) |

### How the field is actually computed

Each emitter gets a geodesic distance field over the open volume, relaxed with
chamfer weights over a 26-neighbourhood, so wavefronts stay round and flow
around pillars instead of through them. Distances are only recomputed when an
emitter *moves*; retuning wavelength, power or phase just re-evaluates
`Σ Aᵢ·sin(2π·dᵢ/λᵢ + φᵢ)·falloff(dᵢ)` against the cached distances through a
sine lookup table. Cells that cross the threshold flip material and mark only
their own chunk dirty, so a knob turn remeshes a handful of chunks rather than
the whole vault.

A save file stores the seed and the emitter settings and nothing else — the
crystal is a function of the field, so it is reconstructed rather than stored.

## What is in this alpha

Working: chamber generation, wave propagation with occlusion, condensation and
sublimation, the Bloom and its counterplay, three chambers of escalating
pressure, the win and loss conditions, save and load, the full HUD, and a
26-check self-test that runs headless.

Not in yet: **audio** — there is no sound at all. Also missing: a tutorial
chamber, more than three chambers, emitter types beyond the basic radiator,
and any settings menu (resolution is a command-line flag for now). The Bloom
currently only spreads; it does not push back when you cut it.

## Licence

MIT — see `LICENSE`.
