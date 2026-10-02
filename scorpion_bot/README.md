# SCORPION - Bambu A1 mini fight robot

Two-wheel-drive bot with a servo-driven **stinger tail** that whips side to side above the body, **pincer claws + ramp** on the front, and a segmented **armor carapace**. Every part fits the A1 mini bed. Regenerate or tweak with `python build_scorpion.py`.

| File | Qty | Print orientation | Material |
|---|---|---|---|
| chassis.stl | 1 | as-is | PETG |
| lid.stl | 1 | flip upside down | PETG |
| carapace.stl | 1 | as-is (ribs up) | PETG/PLA+ |
| claws.stl | 1 | as-is (flat bottom on bed) | PETG, 5 walls |
| tail.stl | 1 | lay the arm flat on the bed (riser pointing up) | PETG/PLA+ |
| wheel.stl | 2 | on its side | TPU 95A |

## Hardware
- 2x N20 gearmotors (3 mm D-shaft), 1x SG90-style 9 g micro servo (with its single-arm horn)
- 1S/2S LiPo, small 2-ch+servo brushed ESC/receiver, switch
- 4x M2x12 self-tapping (lid + carapace), 2x M2.5x10 (claws), 2x M2x6 (servo wings), 2x M2x8 (tail to horn)

## Assembly
1. Drop motors into the cradles; the servo stands in the centre slot with its shaft up. Screw its wings down.
2. Fit the lid (tabs clamp the motors), then the carapace over it with 4 screws. The servo shaft comes up through both.
3. Put the horn on the shaft pointing forward, centre the servo, and push/screw the tail onto the horn.
4. Screw the claws on the front. Press the wheels onto the motor shafts.

Fit is for typical N20 and SG90 dimensions. Test-fit the chassis first and adjust `MOTOR_*` / `SERVO_*` at the top of the script if needed.
Estimated printed weight about 70 g, so check it against your weight class once the electronics are in.
