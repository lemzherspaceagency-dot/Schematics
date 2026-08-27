# Address Plate Handwriting

You and your brother each write **Alyvų g. 4** a few times on the XP-Pen.
This records exactly how each of you moves the pen — every position and how
hard you press — into one file. Hand that file to Claude Code and it blends
the two hands into a single piece of joined-up cursive for the address plate.

There is nothing to type. The window walks you through it.

## Start it

- **Windows** — double-click `start_windows.bat`
- **Mac / Linux** — double-click `start_mac_linux.command`
- or, if you prefer: `python3 capture_handwriting.py`

First time only: if the pressure library isn't installed, the app asks and
installs it for you. One click, about a minute. (It needs Python itself —
[python.org](https://www.python.org/downloads/) if you don't have it.)

## How it goes

1. **Who's writing?** — type your name and hit *Start writing*. Use the same
   name every time; next time your name is already there as a button.
2. **Write it.** Cursive, sitting on the solid line, small letters reaching
   the dashed line above. *Save this one* keeps it and gives you fresh paper —
   with your last attempt showing faintly underneath so you can keep the size
   consistent. Three each is the sweet spot.
3. **Saved.** The app shows what's in the file, tells you the one line to say
   to Claude Code, and copies it to your clipboard on request. Hit *Someone
   else's turn* and hand the pen to your brother — his writing goes into the
   same file.

Nothing to remember: *Undo*, *Start over*, *Guides*, *Last one*, *Fullscreen*
and *Finish* are all buttons on screen. `Enter` saves and `Backspace` undoes
if you'd rather use the keyboard, but you never have to.

Everything is saved the moment you hit *Save this one*, and again if you close
the window mid-line — you can't lose work.

## Then: Claude Code

Open Claude Code in this folder and say:

```
read alyvu_g4_handwriting.json and do what the prompt inside says
```

That's it. The instructions are inside the file — how to line the two hands up
on a shared baseline, how to match stroke to stroke before blending, how to
weld the letters into continuous cursive, how to turn pen pressure into stroke
width, and what to produce: an SVG in millimetres with a centreline layer and
an outlined layer you can laser cut or CNC, a side-by-side comparison of both
hands against the blend, and a script that regenerates it all.

## Does the pen pressure actually work?

The capture screen tells you, top right: **pen connected ✓**, or *no pen yet*.
If it still says *no pen* after you've touched the pen to the screen:

- **Windows** — in the XP-Pen driver, turn **Windows Ink** on. That's the
  setting this reads. (It's per-app, so changing it for Photoshop doesn't
  change it here.)
- **Linux** — the stylus needs to show up in `xinput list` as its own device.
- **macOS** — just needs the XP-Pen driver installed.

You can still write with a mouse if you want — those samples get marked in the
file so nothing downstream mistakes their fake, flat pressure for the real
thing. The blend will be much better with a real pen.

Cursor landing in the wrong place on the pen display is a driver calibration
thing, not this app — run the XP-Pen driver's calibration.

## What ends up in the file

`alyvu_g4_handwriting.json`, next to the script:

```jsonc
{
  "claude_code_prompt": [ "..." ],          // the instructions, first thing in the file
  "target_text": "Alyvų g. 4",
  "device": "XP-Pen Artist 15.6 (V2) ...",
  "point_format": ["x", "y", "p", "t", "tx", "ty"],
  "writers": { "laurynas": { "samples": 3, ... }, "brolis": { ... } },
  "samples": [
    { "writer": "laurynas", "index": 0, "input": "tablet",
      "canvas": { ... }, "guides": { ... },       // as they were for THIS sample
      "strokes": [ { "points": [[412.55, 388.20, 0.4213, 16.7, 3.0, -11.0], ...] } ] }
  ]
}
```

- `x`, `y` — canvas pixels, y grows **downward**
- `p` — pressure 0–1 (8192 levels underneath, on the Artist 15.6 V2)
- `t` — milliseconds from the start of that sample, so speed and stroke
  direction survive
- `tx`, `ty` — pen tilt in degrees, `0` if the driver doesn't report it

Each sample carries its own `canvas` and `guides`, so resizing the window
between attempts doesn't spoil anything.

## Optional, if you like a terminal

```bash
python3 capture_handwriting.py --inspect          # stroke/pressure stats per sample
python3 capture_handwriting.py --svg preview.svg  # draw the raw captures
python3 capture_handwriting.py somefile.json      # use a different file
```

The *See what I wrote* button on the last screen does the same as `--svg`.
