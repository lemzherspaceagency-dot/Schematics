# USB Boot-Mode Mux (U10) — Component Verification

## Why this part exists

See `docs/PROGRAMMING_DEBUG_GUIDE.md` §2 for the full story: before this
pass, the CM4's only USB2 OTG pair was wired directly and exclusively to
U7 (the USB2512B hub)'s upstream port, which made `rpiboot`-based eMMC
programming/recovery physically impossible — there was no path for an
external host to ever see the CM4 in USB device/boot mode. This is a real
hardware gap, fixed with a real component, not a documentation change.

## Selected part: FSUSB42MUX (ON Semiconductor FSUSB42)

**Reference designator**: U10. **Function**: USB 2.0 SPDT (single-pole,
double-throw) differential analog switch — routes one differential pair
(the CM4's OTG D+/D-) to one of two destinations, selected by a single
digital pin.

### Why this pinout is trusted

Unlike every custom-generated part in this project, **U10 uses KiCad's
own maintained stock library part directly** — `Interface_USB:FSUSB42MUX`
— the same highest-confidence verification tier already established for
U7 (USB2512B) and J12 (U.FL antenna connector) elsewhere in this project:
a real, community-maintained symbol from KiCad's own shipped libraries,
not hand-transcribed or fabricated. Pin data, parsed directly from the
installed `Interface_USB.kicad_sym`:

| Pin | Name | Function |
|---|---|---|
| 1 | VCC | Supply |
| 2 | SEL | Select: chooses which throw (HSD1 or HSD2) connects to D+/D- |
| 3 | D+ | Common port (this design: CM4 OTG D+) |
| 4 | D- | Common port (this design: CM4 OTG D-) |
| 5 | GND | Ground |
| 6 | HSD1- | Throw 1, D- (this design: to J13 external boot connector -- SEL low selects this throw) |
| 7 | HSD1+ | Throw 1, D+ |
| 8 | HSD2- | Throw 2, D- (this design: to U7 hub upstream -- SEL high selects this throw) |
| 9 | HSD2+ | Throw 2, D+ |
| 10 | ~OE | Active-low output enable |

### Footprint

The symbol's own embedded `Footprint` property declares
`Package_SO:MSOP-10_3x3mm_P0.5mm` — a real, maintained stock KiCad
footprint, standard JEDEC MSOP-10 geometry. Used as-is; no custom
footprint generation was needed (same reasoning as J12/U7's stock-library
footprints — the highest-confidence footprint verification tier in this
project, since the geometry is KiCad's own maintained data, not this
project's own approximation).

### Alternative considered: TS3USB221A

A parallel search (independent of finding FSUSB42MUX in the stock
library) confirmed **TS3USB221A** (Texas Instruments, 10-pin QFN "RSE"
package) as a real, viable alternative — cross-checked against 2
independent real sources: a KiCad symbol in `SPIRIT-org/SPIRIT` (the same
repository that supplied this project's verified EC25 symbol) citing the
TI datasheet directly, and a real, deployed CM4 handheld product
(`StonedEdge/Retro-Lite-CM4`) using this exact part for the exact same
application — muxing a CM4's single USB OTG pair between two downstream
destinations. Its real pinout (1D+/1D-/2D+/2D-/GND/OE#/D-/D+/S/VCC) was
independently verified but **not used**: FSUSB42MUX was preferred because
it is directly available as a real, maintained KiCad stock library
symbol+footprint pair in this environment, requiring no custom part
generation and matching this project's established "prefer a real stock
KiCad library part over a custom-generated one" verification hierarchy.
TS3USB221A remains a documented, real fallback option if FSUSB42
availability becomes a purchasing concern.

## SEL pin polarity — RESOLVED this pass

**SEL polarity is now verified against the real FSUSB42 datasheet truth
table**, cross-referenced via a real, independent hardware bring-up
document (`lazerduck/fuse-vault`, `docs/hardware-bringup-stage4.md`) that
cites onsemi's own FSUSB42 datasheet URL directly and states the truth
table explicitly: **"OE low is enabled, SEL low selects HSD1, and OE high
disconnects both routes."** A second independent real CM4-carrier design
doing the identical hub/rpiboot-mux pattern (`jrseti/RCM_DishControllerBoard`)
was checked for corroborating topology and found consistent, not
contradictory.

This board's original wiring (first draft this pass) had the assignment
backwards — it tied `SEL` directly to `nRPIBOOT` (high in normal
operation, low when SW1 forces boot mode) while wiring `HSD1` to U7 (the
hub) and `HSD2` to J13 (the boot connector). Per the real truth table,
that would have connected the **boot connector to the hub's path and the
hub to the boot connector's path** — exactly backwards, and not caught
until this verification. **Fixed** (not just documented): `HSD1` is now
wired to J13 (boot connector) and `HSD2` to U7 (hub) in
`python/design_data.py`, so the existing direct `nRPIBOOT`-to-`SEL`
connection is correct with no inverter needed: `nRPIBOOT` low (boot mode)
→ `SEL` low → `HSD1` (J13) selected; `nRPIBOOT` high (normal) → `SEL`
high → `HSD2` (U7) selected.

**Residual risk**: this rests on one directly-cited datasheet truth table
from a real, independent source, not on this project having directly
retrieved the onsemi PDF itself (onsemi.com is unreachable from this
sandboxed environment, the same constraint as every other part in this
project). Confirming with a continuity/logic-level check at first
hardware bring-up remains good practice, but this is no longer an
unresolved design-direction question — the wiring is now the correct
polarity as best determined from real, citable sources.

## What else is NOT independently verified
- **~OE polarity** (pin 10, tied to GND in this design) is assumed
  active-low (standard convention for a pin named with a tilde/overbar,
  matching every other active-low signal in this project's own netlist
  naming, e.g. `nRPIBOOT`) — consistent with the pin's own name in the
  verified symbol data, but not cross-checked against a datasheet timing/
  logic table beyond that naming convention.
- **VCC voltage** (wired to +3V3 in this design): 3.3 V is the standard
  supply rail for USB2.0 differential-signal-class analog switches in
  this IC family and matches U7 (the hub) and the CM4's own logic level
  on the same signals — a reasonable, low-risk assumption, not
  independently confirmed against a datasheet absolute-maximum/
  recommended-operating-conditions table.

## Physical routing status

See `docs/ROUTING_STATUS.md`. U10's control/power pins (SEL, ~OE, VCC,
GND) route through the same auto-router used for the rest of this board's
signal fan-out; the three USB2.0 differential pairs through it
(`CM4_USB_DP/DM`, `HUB_USB_DP/DM`, `BOOT_USB_DP/DM`) remain unrouted
ratsnest as of this pass, for the same reason most of this board's
fine-pitch/high-density signal routing remains incomplete — this
project's simple point-to-point router cannot navigate U7/U10's dense
footprint fan-out area. Completing these three connections (short,
low-risk hops given U10 sits immediately adjacent to both J2 and U7) is
recommended as the first interactive-KiCad routing task for this board,
ahead of the lower-priority remaining GPIO/UART gaps.
