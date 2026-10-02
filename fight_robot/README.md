# Wedge fight robot (Bambu A1 mini)

Antweight-style wedge bot, 2-wheel drive. Every part fits the A1 mini 180 mm bed. Regenerate or tweak with `python build_robot.py` (needs `numpy trimesh manifold3d shapely`).

| File | Qty | Orientation | Material |
|---|---|---|---|
| chassis.stl | 1 | as-is (floor on bed) | PETG or PLA+ , 4 walls, 25% gyroid |
| lid.stl | 1 | **flip upside down** (flat plate on bed) | PETG |
| wedge.stl | 1 | as-is (flat bottom on bed) | PETG/PLA+, 5 walls, 40% infill |
| wheel.stl | 2 | axle pointing up (lay it on its face) | **TPU 95A** (best grip) |

## Hardware you need
- 2x N20 gearmotors, 3 mm D-shaft, 12x10 mm body (~300-600 rpm at 6V)
- 1S or 2S small LiPo (about 300-500 mAh) + 2-ch brushed ESC/receiver (e.g. a 2-in-1 antweight board) + switch
- 4x M2 x 8 self-tapping screws (lid), 2x M2.5 x 10 (wedge through the front wall)

## Notes
- Overall size ~118 x 90 x 33 mm. Check the weight class you plan to fight in (antweight limit is 150 g, usually plastic 3D-printed class is 150 g).
- Motors drop into the cradles, shaft out through the wheel-well wall, lid tabs clamp them down. Electronics go in the front cavity.
- Dimensions are my best fit for typical N20 motors. Print the chassis first and test-fit your motor, then adjust `MOTOR_W/MOTOR_H` if needed.
