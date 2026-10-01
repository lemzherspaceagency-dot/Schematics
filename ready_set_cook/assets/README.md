# Drop-in 3D models (optional)

Put `.glb` files here and the game uses them instead of its built-in primitive models. Nothing else to configure.
Use CC0 / properly licensed assets only (for example the Kenney, Quaternius or KayKit packs) and keep their licence files.

Rules: **1 unit = 1 tile**, the origin is the middle of the floor under the object, the front faces **+Z**.

| file name | replaces |
|---|---|
| `counter.glb`, `table.glb`, `chair.glb` | counters, dining tables, chairs |
| `crate_meat.glb` `crate_veg.glb` `crate_dough.glb` | ingredient crates |
| `chop_board.glb` `stove.glb` `oven.glb` `plate_station.glb` `bin.glb` | machines (a stove model is shown with its pot/flames only if the model has nodes named `pot` and `flames`) |
| `item_veg.glb` `item_meat.glb` `item_dough.glb` `item_veg_chop.glb` `item_meat_chop.glb` `item_veg_cook.glb` `item_meat_cooked.glb` `item_patty.glb` `item_bun.glb` `item_burnt.glb` | ingredients |
| `dish_salad.glb` `dish_steak.glb` `dish_soup.glb` `dish_burger.glb` `dish_stew.glb` | finished dishes |

Chefs and customers are rigged from code (named parts), so they are not replaceable this way.
