# Address Plate Handwriting Capture

Record two people's cursive handwriting from an **XP-Pen Artist 15.6 (V2)** —
x, y, pen pressure, tilt and timing — into one JSON file, then hand that file
to Claude Code so it can fuse both hands into a single joined-up address plate.

Default text: **Alyvų g. 4**, written *rašytinėmis, ne spausdintinėmis*.

Everything is in one script: `capture_handwriting.py`.

## Install

```bash
pip install PySide6        # or PyQt6, or PyQt5 — the script takes whichever it finds
```

Qt is what gives us pressure. Plain tkinter/pygame only report mouse
coordinates, so pressure would be a constant and the plate would come out with
dead, uniform strokes.

### Make sure the tablet actually reports pressure

- **Windows** — in the XP-Pen driver, keep the pen mode on **Windows Ink**.
  Qt reads pressure through Windows Ink; if it is off you get mouse events with
  no pressure. (Some drawing apps prefer Wintab — that setting is per-app, so
  changing it for Photoshop does not change it here.)
- **Linux** — the tablet has to come up as an XInput2/libinput device. Check
  with `xinput list`; you should see the XP-Pen stylus as its own device, not
  just a generic mouse.
- **macOS** — works out of the box with the XP-Pen driver installed.

The header of the capture window tells you which one you got: `input: tablet`
or `input: mouse (no tablet seen yet)`. If it says mouse after you have touched
the pen to the screen, the driver is not feeding Qt.

## Use it

Move the window onto the pen display first, then press `F` for fullscreen (or
start with `--fullscreen`).

```bash
# you
python3 capture_handwriting.py --writer laurynas

# your brother, later, same file — it appends, it does not overwrite
python3 capture_handwriting.py --writer brolis
```

Both runs write to `alyvu_g4_handwriting.json`. Pass a different filename as
the last argument if you want.

Write the text on the **solid baseline**, with the small letters reaching the
**dashed x-height line**. Those guides are what let Claude line the two hands up
afterwards — if one of you writes tiny and the other huge it still works, but
only because the guides are recorded alongside the strokes.

Aim for **3 repetitions each**. More is better: it lets Claude pick the
cleanest one instead of being stuck with your one and only try.

### Keys

| Key | Does |
| --- | --- |
| `Enter` | commit this sample and start the next (also autosaves) |
| `Backspace` / `Ctrl+Z` | undo the last stroke |
| `C` | clear the current sample |
| `G` | toggle the faint ghost of your previous sample (helps keep size consistent) |
| `L` | toggle guide lines |
| `H` | toggle the key help |
| `F` | fullscreen |
| `S` | save now |
| `Esc` / `Q` | save and quit |

The eraser end of the pen is deliberately ignored — use `Backspace`.

### Check what you captured

```bash
python3 capture_handwriting.py --inspect
python3 capture_handwriting.py --svg preview.svg     # open preview.svg in a browser
```

`--inspect` prints per-sample stroke counts, point counts and pressure stats,
and warns about the things that would trip up the blend later (only one sample
for a writer, only one writer in the file, mouse-only samples).

Other flags: `--text` to write something else, `--samples N` for the target
count in the header, `--replace` to throw away one writer's earlier attempts,
`--pen-scale` to fatten the on-screen ink.

## Then: give the file to Claude Code

```
> read alyvu_g4_handwriting.json and do what the prompt inside says
```

The prompt is the first thing in the file (`claude_code_prompt`). It tells
Claude what the numbers mean, how to normalise both hands onto a shared
baseline, how to match stroke-to-stroke with DTW before blending, how to weld
the letters into continuous cursive, how to turn pressure into stroke width,
and what to output — an SVG in millimetres with a centreline layer and an
outlined (cuttable) layer, a side-by-side comparison SVG, and a script that
regenerates all of it deterministically.

## What is in the file

```jsonc
{
  "schema": "handwriting-capture/v2",
  "claude_code_prompt": [ "...", "..." ],   // the instructions, as lines
  "target_text": "Alyvų g. 4",
  "device": "XP-Pen Artist 15.6 (V2) ...",
  "canvas": { "width_px": …, "px_per_mm": …, "physical_dpi": … },
  "guides": { "baseline_y_px": …, "x_height_px": …, … },
  "point_format": ["x", "y", "p", "t", "tx", "ty"],
  "writers": { "laurynas": { "samples": 3, "strokes": 21, … }, … },
  "samples": [
    {
      "writer": "laurynas", "index": 0, "input": "tablet",
      "duration_ms": 4820, "stroke_count": 7, "point_count": 1943,
      "canvas": { … }, "guides": { … },        // as they were for THIS sample
      "strokes": [
        { "source": "pen",
          "points": [[412.55, 388.20, 0.4213, 16.7, 3.0, -11.0], …] }
      ]
    }
  ]
}
```

- `x`, `y` are canvas pixels and **y grows downward** (screen convention).
- `p` is pressure, 0.0–1.0. On the Artist 15.6 V2 that is 8192 levels
  underneath, normalised by the driver.
- `t` is milliseconds from the start of that sample, so stroke order,
  direction and writing speed all survive.
- `tx`, `ty` are pen tilt in degrees, `0` if your driver does not report it.
- Every sample carries its **own** `canvas` and `guides` — if you resize the
  window between samples, each one still normalises correctly.

`px_per_mm` comes from the display's reported DPI, so treat it as approximate;
drive the physical size of the plate from a target letter height in mm instead
of trusting it.

## Notes and gotchas

- **Use the same writer name every time.** `--writer laurynas` and
  `--writer Laurynas` are two different people as far as the file is concerned.
- If no tablet is detected you can still draw with the mouse — those samples
  get marked `"input": "mouse"` and their pressure is a constant 0.5, flagged
  so nothing downstream mistakes it for real pressure. Once a real tablet event
  arrives, mouse input is ignored for the rest of the session.
- Cursor offset on the pen display is a driver calibration issue, not a script
  one — run the XP-Pen driver's calibration.
- The file is rewritten atomically on every commit, so a crash mid-session
  costs you at most the sample you were in the middle of.
