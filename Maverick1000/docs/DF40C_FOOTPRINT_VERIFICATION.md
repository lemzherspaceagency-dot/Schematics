# DF40C-100DS-0.4V Footprint Verification — Rev A (post-audit correction)

## The bug

The pre-audit footprint generator (`dual_row_connector` in
`python/gen_footprints.py`) laid out all 2-row connectors the same way:
pins 1..50 sequentially along the top row, pins 51..100 sequentially
along the bottom row. **This is the wrong pad numbering scheme for the
real Hirose DF40C-100DS-0.4V.**

## The proof (found via an independent third-party audit)

An unrelated open-source KiCad library project, `mszkowalik/KiCad-Lib`,
performed and published exactly this check as part of a footprint
correctness audit
(`docs/footprint-naming/06-connector-pin-numbering.md` in that repo). Its
finding, reproduced here because it applies directly to this board:

The real Hirose DF40C-100DS-0.4V numbers **odd contacts down one row,
even contacts down the other** (an "Odd_Even" scheme), not sequential
top-then-bottom. The proof is a parity check against the CM4's own
published pinout (the CM4 uses this exact connector): every one of the
CM4's 32 differential signal pairs lands on same-parity pins exactly 2
apart — e.g. `Ethernet_Pair3_P` = pin 3, `Ethernet_Pair3_N` = pin 5. A
differential pair can only be physically adjacent, as pair routing
requires, if same-parity contacts are consecutive within a row — i.e. the
connector *must* be odd/even, not sequential. Under a sequential
numbering, an unrelated signal (pin 4) would physically sit between pins
3 and 5 of a differential pair, which no real connector does.

That audit further notes it cross-checked its corrected symbol against
KiCad's own (newer-version) stock footprint,
`Hirose_DF40C-100DS-0.4V_2x50_P0.4mm` (shipped starting around KiCad
10.0.5 — not present in this project's KiCad 7.0.11 install, which is why
this project has a custom footprint at all), and confirmed pin 1 and pin
2 share an X coordinate on opposite rows, i.e. odd/even.

## The fix

`python/gen_footprints.py` now has a dedicated `dual_row_odd_even_
connector()` generator, used specifically for the CM4 footprint: pad
`2k+1` and pad `2k+2` (for `k = 0..49`) share an X position, one on each
row, matching the real part.

**No netlist changes were required.** This project's CM4 net assignments
(`python/design_data.py`, verified against `docs/CM4_PIN_VERIFICATION.md`)
already used real, community-verified pin *numbers* per signal — those
numbers were always correct. The bug was purely in the footprint
generator's physical pad *placement*: pad "3" existed and correctly
carried net `UART3_TXD3`, but was drawn in the wrong physical location on
the copper (sequential position 3, instead of the real connector's
"3rd-from-top on the odd row" position). If left unfixed, a real DF40C
connector soldered onto a board fabricated from the old footprint would
have every single signal landing on the wrong physical contact — this
would have been a **completely non-functional board**, not a subtle bug.

## What is still a documented approximation

The odd/even *scheme* is now confirmed correct. The exact pad *pitch,
row spacing, and pad size* remain a dimensional approximation from
published DF40C series family dimensions (0.4 mm pitch, 3.0 mm row
spacing assumed) — see `docs/assumptions.md` #2. Verify against Hirose's
mechanical drawing before ordering boards; this remains the top
fabrication-blocking risk on this project because it is the highest pin
count, finest pitch part on the board.
