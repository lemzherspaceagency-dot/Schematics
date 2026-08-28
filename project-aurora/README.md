# Project Aurora: The Last Child

An original horror game — the FNaF-adjacent shape (an AI host, a facility,
tools an employee left behind) built into its own identity: nobody is
misunderstood, nothing is secretly on your side, and the thing chasing you
runs the whole building on purpose.

## This prototype

Per the project's own build rule — **one room, one mechanic, one
prototype, only then continue** — this is exactly that. A native
executable, C11 and OpenGL 3.3, no browser, no third-party engine.

- **Room**: the Orpheon lobby. Front desk, a locked inner door, the
  "Let Our Song Guide You Here" signage, family-entertainment dressing.
- **Mechanic**: D.I.V.A. — the employee tool found behind the desk —
  makes Orpheon's command conduits visible and lets you tap a travelling
  signal and re-aim it at a different endpoint. It's built to counter
  Aurora's defining trait (she coordinates every robot in the building)
  rather than to grapple, scan, or extract like the tools it's
  deliberately not.
- **Beat**: Aurora's canon first encounter — she walks in, scans Daniel,
  welcomes him with the project's actual slogan, and is gone the moment
  he looks away, with only a bracketed caption standing in for the
  mechanical shuffle since there's no audio pipeline yet.

## Running

Download the installer from `dist/` and run it, or just run
`ProjectAurora.exe` directly — it's self-contained, no runtime to
install. Needs 64-bit Windows and a graphics driver with OpenGL 3.3
(anything from about 2010 onward).

**Controls**: WASD move · mouse look · E interact · hold right-click to
trace with D.I.V.A. · Escape to pause.

Command line: `--width N --height N --selftest`.

## Building from source

```sh
make            # native build (X11/GLX) for development
make test       # headless self-test under Xvfb
make windows    # cross-compiled, statically linked ProjectAurora.exe
make installer  # the exe plus an NSIS installer, into dist/
```

Cross-compiling and packaging need `mingw-w64` and `nsis`. The headless
test needs `xvfb` and a Mesa software rasteriser.

### Layout

| File | What it does |
|---|---|
| `src/au_game.c` | The room's collision, Aurora's state machine, the D.I.V.A. mechanic, HUD |
| `src/au_render.c` | Shaders, primitive mesh builders (box/cylinder/sphere/ring), the bitmap-font overlay |
| `src/ff_gl.c` | Minimal OpenGL 3.3 loader — no GLEW, no GLAD |
| `src/plat_win32.c` | Win32 + WGL backend (the shipping build) |
| `src/plat_x11.c` | X11 + GLX backend (development and automated testing) |

The platform layer, GL loader and math library are carried over verbatim
from an earlier prototype in this repository (`antinode/`) — they're
fully generic (window/input/timing, a vector and matrix library) and were
already proven working, so this project reuses rather than re-derives
them. Everything game-specific is new.

Unlike a voxel world, the lobby is a small hand-authored set piece: one
static VBO built once at startup for the room and dressing, plus a
handful of small meshes (Aurora's body parts, the door, the signal pulse)
that just get a new model matrix each frame rather than being rebuilt.

A 23-check self-test drives the actual game loop headless: chamber
layout and collision, Aurora's full scripted sequence including the
look-away trigger, D.I.V.A. pickup, the conduit tap-and-redirect flow,
the door unlocking and animating open, walking through it to end the
slice, and restart. It caught two real bugs before anyone played this by
hand: the player spawned facing sideways at a wall instead of into the
room (meaning a real player could miss Aurora's entrance entirely), and
the lighting model was tuned so aggressively that the lobby rendered as
a black screen.

## What is in this prototype

Working: the room, the D.I.V.A. conduit-tap mechanic end to end, Aurora's
full scripted first encounter, the win condition (open the door and walk
through), save-free restart, a working exe and installer.

Deliberately not here yet, per the same one-room philosophy: **no audio
at all** — the "mechanical shuffling" is a bracketed caption, not a
sound, and this is the single biggest gap for a horror game specifically.
No second room. Aurora's behavior in this slice is fully scripted
(timers and lerps), not a real AI director — that's the next thing worth
building once this slice has earned it.

## Licence

MIT — see `LICENSE`.
