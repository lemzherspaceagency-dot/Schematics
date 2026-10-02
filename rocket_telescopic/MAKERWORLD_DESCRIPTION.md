# 🚀 Telescopic Rocket – Print-in-Place, No Supports, 3-Colour by Height

Print it as a tiny 83 mm rocket… then pull it out to **170 mm**! A fully print-in-place, three-stage telescopic rocket with a satisfying slide, a hard stop at each stage, and a pointed nose cone. No assembly. No supports. No AMS.

## Why you'll love it
- **Print-in-place** – 3 nested stages, 0.3 mm clearance, works straight off the bed
- **Zero supports** – every overhang ≤ 45° (nose, fins, bell, lips)
- **Single-colour printers welcome** – 4 filament swaps by layer height (table below)
- **Fidget + desk toy + display piece** – launch it, extend it, repeat
- **Fits 3×3 on an A1 mini plate** – print 9 for a launch squadron (`plate_nx/plate_ny`)
- **Fully parametric OpenSCAD file included**

## Colour swaps (0.2 mm layers) – pause at these heights
| Height | Colour | Part |
|---|---|---|
| 0 – 6 mm | Orange | Engine bell / flame |
| 6 – 28 mm | White | Body |
| 28 – 40 mm | Blue | Window band + portholes |
| 40 – 60 mm | White | Body |
| 60 – 83 mm | Red | Nose cone |

Bambu Studio: right-click the layer slider → *Add Color Change* at 6.0, 28.0, 40.0, 60.0.

## Print settings
- Printer: Bambu Lab A1 mini, 0.4 mm nozzle, 0.2 mm layer
- Walls: 4 · Infill: 10 % · Supports: **OFF** · Brim: outer only, 3–5 mm
- **Elephant-foot compensation: 0.1–0.15 mm** (keeps first-layer gaps open)
- Slow outer walls for the first 10 mm, PLA recommended
- If a stage sticks, raise `gap` to 0.35 in the .scad file and re-export

## After printing
1. Twist each stage gently to break the first-layer bond.
2. Pull the nose cone – three stages slide out and lock.
3. Push back down. Repeat forever.

Remix ideas: rename the stage colours, add stickers, change `stages`, `H`, or `R_o`.
Please post your make and a ⭐ – it helps a lot. Happy launching! 🚀
