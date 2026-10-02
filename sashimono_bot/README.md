# SASHIMONO - samurai fight robot (Bambu A1 mini)

A samurai-themed bot:
- **Kabuto front**: visor ramp, flared *fukigaeshi* cheek wings and a crescent *maedate* crest.
- **Katana**: a servo swings the blade side to side above the armor (tsuba guard, wrapped handle, kissaki tip).
- **Sashimono**: a tall banner with a *mitsudomoe* emblem on the back. It's a **friction-fit breakaway** pole, so a hit knocks the flag off and nothing breaks.

Chassis, lid and wheels come from `../scorpion_bot` (the same drivetrain, servo bay and screw layout). `build_sashimono.py` imports from that folder.

| File | Qty | Print orientation | Material |
|---|---|---|---|
| chassis.stl | 1 | as-is | PETG |
| lid.stl | 1 | flip upside down | PETG |
| carapace.stl | 1 | as-is (has the banner socket) | PETG |
| kabuto.stl | 1 | as-is, flat bottom down | PETG, 5 walls |
| katana.stl | 1 | lay the blade flat (riser up) | PETG |
| banner.stl | 1 | lay it on its back (it's a flat sheet) | PLA/PETG, bright colour |
| wheel.stl | 2 | on its side | TPU 95A |

Note: the STLs for lid, carapace, kabuto and banner are in the assembled pose, so use "lay on face" in the slicer. Hardware and assembly are the same as the scorpion bot (see its README).
Pole fit is 5 x 3 mm in a 5.4 x 3.4 mm socket. Sand or add a layer of tape to tune the grip.
Overall height with the banner is about 128 mm, and weight stays low (about 75 g printed).
