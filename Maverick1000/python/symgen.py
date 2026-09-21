"""
Uniform schematic-symbol renderer used by gen_schematic.py.

Rather than trying to re-embed (and correctly resolve `extends` on) the
original hand-drawn KiCad library artwork, every symbol used in this
schematic -- stock or custom -- is re-rendered here as a simple rectangle
body with pins in their REAL number/name/electrical-type (taken from the
actual KiCad library via libparse), laid out on a uniform grid. This keeps
the generator simple and correct where it matters (pin numbers, names,
electrical types -- i.e. netlist correctness) while not depending on
faithfully reproducing decorative artwork.
"""

from dataclasses import dataclass
from libparse import get_pins_for_lib_id, Pin


@dataclass
class RenderedSymbol:
    lib_nick: str
    sym_name: str
    embed_text: str          # the (symbol "lib:name" ...) block for lib_symbols
    pin_pos: dict            # pin number (str) -> (x, y, rotation) local coords
    width: float
    height: float


def _numeric_key(pin: Pin):
    try:
        return (0, int(pin.number))
    except ValueError:
        return (1, pin.number)


def render(lib_id: str) -> RenderedSymbol:
    lib_nick, sym_name = lib_id.split(":", 1)
    pins = sorted(get_pins_for_lib_id(lib_id), key=_numeric_key)
    n = len(pins)

    if n <= 2:
        pitch = 2.54
        cols = 1
    elif n <= 24:
        pitch = 2.54
        cols = 2
    else:
        pitch = 1.27
        cols = 2

    half = (n + 1) // 2 if cols == 2 else n
    body_width = 15.24 if n > 2 else 5.08

    # IMPORTANT: never derive a coordinate by dividing a pitch-multiple by 2.
    # pitch always has <=2 decimal digits, so any *integer* multiple of it is
    # exactly representable to 2 decimals -- but half of an ODD multiple of
    # 1.27 (e.g. 49*1.27/2 = 31.115) is NOT, and rounds inconsistently
    # depending on whether KiCad sums the (already-rounded) instance offset
    # + local pin offset, or whether this generator sums the unrounded
    # floats first and rounds once -- a real bug found and fixed here via
    # kicad-cli netlist cross-checks (see docs/assumptions.md). Keeping pin
    # 1 at y=0 and stepping by whole pitch multiples avoids the division
    # entirely, so both computations always round identically.
    pin_pos = {}
    pin_lines = []
    for idx, p in enumerate(pins, start=1):
        if cols == 1:
            if idx == 1:
                x, y, rot = 0.0, 2.54, 270
            else:
                x, y, rot = 0.0, -2.54, 90
        else:
            if idx <= half:
                x = -body_width / 2
                y = -(idx - 1) * pitch
                rot = 0
            else:
                x = body_width / 2
                y = -(idx - half - 1) * pitch
                rot = 180
        pin_pos[p.number] = (x, y, rot)
        length = 5.08 if n > 2 else 2.54
        pin_lines.append(
            f'      (pin {p.etype} line (at {x:.2f} {y:.2f} {rot}) (length {length})\n'
            f'        (name "{p.name}" (effects (font (size 1.016 1.016))))\n'
            f'        (number "{p.number}" (effects (font (size 1.016 1.016))))\n'
            f'      )\n'
        )

    col_len = max(half - 1, 0) * pitch  # distance from pin 1 (y=0) to the last pin in a column

    if n <= 2:
        # small passive body (Device:R / C / L style small box)
        bw, bh_top, bh_bot = 2.032, 1.27, 1.27
    else:
        bw, bh_top, bh_bot = body_width / 2, pitch, col_len + pitch

    label_y = bh_top + 2.5
    body = (
        f'    (symbol "{sym_name}_0_1"\n'
        f'      (rectangle (start -{bw:.3f} {bh_top:.3f}) (end {bw:.3f} -{bh_bot:.3f})\n'
        f'        (stroke (width 0.152) (type default))\n'
        f'        (fill (type background))\n'
        f'      )\n'
        f'    )\n'
    )
    pins_block = f'    (symbol "{sym_name}_1_1"\n' + "".join(pin_lines) + "    )\n"

    embed = (
        f'  (symbol "{lib_nick}:{sym_name}" (in_bom yes) (on_board yes)\n'
        f'    (property "Reference" "U" (at 0 {label_y + 1.5:.2f} 0)\n'
        f'      (effects (font (size 1.27 1.27)))\n'
        f'    )\n'
        f'    (property "Value" "{sym_name}" (at 0 {label_y:.2f} 0)\n'
        f'      (effects (font (size 1.27 1.27)))\n'
        f'    )\n'
        f'    (property "Footprint" "" (at 0 0 0)\n'
        f'      (effects (font (size 1.27 1.27)) hide)\n'
        f'    )\n'
        f'    (property "Datasheet" "~" (at 0 0 0)\n'
        f'      (effects (font (size 1.27 1.27)) hide)\n'
        f'    )\n'
        f'{body}{pins_block}'
        f'  )\n'
    )

    return RenderedSymbol(lib_nick, sym_name, embed, pin_pos, bw * 2, bh_top + bh_bot)
