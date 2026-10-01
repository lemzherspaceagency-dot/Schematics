# Ready, Set, Cook! v0.2 (Godot 4.2+)

1. Unzip, open Godot 4.2+, click Import, pick `project.godot`.
2. Press F5. Portrait 720x1280, mouse/touch only.

## How to play
Tap the floor to walk. Tap a station to walk there and use it.
- **Crates** (meat / veg / dough) give raw food. **Chop** board, **Pan** and **Oven** are timed: drop food in, do something else, come back.
  Pan and oven BURN food if you wait too long (watch the ring + "!"). Burnt food goes in the **Bin**.
- Put ingredients on the **Plate**. When they match a recipe it turns into a dish: tap the plate again to pick it up.
  (Tap the plate with empty hands on a wrong combo to take the last item back.)
- Tap a customer to serve. Faster = bigger tip. Back-to-back correct orders build a combo (+10% each, up to +50%).
- Wrong dish or an angry customer resets your combo.

Recipes: Salad (2 chopped veg), Steak (pan meat + chopped veg), Soup (2 pan-cooked chopped veg),
Burger (oven bun + chopped meat cooked in pan + chopped veg).

## What's new in v0.2
- 10 levels with star goals, unlock progression, brief screen with recipe cards
- 4 dishes, 3 timed machines with burn mechanic, assembly plate
- Customers with patience, moods, tips, combo streaks, rush hour in the last 20s
- Ready / Set / Cook intro, pause, result screen with animated stars
- 5 upgrades in a shop, coins + stars saved to disk (`user://save_v2.json`)
- Procedural sound effects (no audio files), particles, screen shake, tutorial hints on level 1

## Tweak
- `data.gd`: recipes, prices, machine times, levels, upgrades (everything balance-related)
- `main.gd`: `MAP` layout, chef speed, drawing

## Shipping to Messenger (Instant Games)
Project > Export > Web (needs the Web export template). Zip the exported files with a `fbapp-config.json`
and include the Facebook Instant Games SDK script in a custom HTML shell; call `FBInstant.initializeAsync()`/`startGameAsync()`
via `JavaScriptBridge`, and swap `user://` saves for `FBInstant.player.setDataAsync` when you're ready.

## Next ideas
Sprites (Kenney.nl, CC0), music, daily rewards, friend leaderboard, more machines per level, special customers.
