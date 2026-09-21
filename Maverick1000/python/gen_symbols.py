#!/usr/bin/env python3
"""
Generate kicad/libraries/symbols/SKYWARD_Custom.kicad_sym -- the custom
schematic symbols this design needs that don't exist in the stock KiCad
library: the two CM4 100-pin connectors, the Terra 22-pin payload
connector, and simplified representations of the LM74610 ideal-diode
controller and BQ25792 charger (parts too new/obscure for the KiCad 7.0.11
stock libraries shipped in this build environment).

Pin-number <-> function mapping matches python/design_data.py exactly.
"""

HEADER = """(kicad_symbol_lib (version 20211014) (generator kicad_symbol_editor)
"""
FOOTER = ")\n"


def pin(number, name, x, y, rotation, length=2.54, etype="passive", hide=False):
    hide_s = " hide" if hide else ""
    return f'''      (pin {etype} line (at {x:.2f} {y:.2f} {rotation}) (length {length}){hide_s}
        (name "{name}" (effects (font (size 1.016 1.016))))
        (number "{number}" (effects (font (size 1.016 1.016))))
      )
'''


def two_column_connector(sym_name, ref_prefix, footprint, description, datasheet,
                          pin_map, pitch=1.27, body_width=15.24):
    """pin_map: dict[int,str] pin_number -> pin_name, numbered 1..N, split into
    two equal columns (1..N/2 on the left pointing left, N/2+1..N on the right
    pointing right), top-to-bottom on each side."""
    n = len(pin_map)
    half = n // 2
    height = (half - 1) * pitch
    top_y = height / 2

    body = f'''    (symbol "{sym_name}_0_1"
      (rectangle (start -{body_width/2:.2f} {top_y + pitch:.2f}) (end {body_width/2:.2f} -{top_y + pitch:.2f})
        (stroke (width 0.254) (type default))
        (fill (type background))
      )
    )
'''
    pins_txt = ['    (symbol "%s_1_1"\n' % sym_name]
    for idx in range(1, n + 1):
        name = pin_map[idx]
        if idx <= half:
            y = top_y - (idx - 1) * pitch
            x = -body_width / 2
            rot = 0
        else:
            y = top_y - (idx - half - 1) * pitch
            x = body_width / 2
            rot = 180
        pins_txt.append(pin(idx, name, x, y, rot, length=5.08))
    pins_txt.append("    )\n")

    return f'''  (symbol "{sym_name}" (in_bom yes) (on_board yes)
    (property "Reference" "{ref_prefix}" (at 0 {top_y + pitch*3:.2f} 0)
      (effects (font (size 1.27 1.27)))
    )
    (property "Value" "{sym_name}" (at 0 {top_y + pitch*2:.2f} 0)
      (effects (font (size 1.27 1.27)))
    )
    (property "Footprint" "{footprint}" (at 0 0 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (property "Datasheet" "{datasheet}" (at 0 0 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (property "Description" "{description}" (at 0 0 0)
      (effects (font (size 1.27 1.27)) hide)
    )
{body}{"".join(pins_txt)}
  )
'''


def ic_symbol(sym_name, ref_prefix, footprint, description, datasheet, pin_map,
              pitch=2.54, body_width=17.78):
    """Small IC-style symbol, split N pins into two even columns."""
    return two_column_connector(sym_name, ref_prefix, footprint, description,
                                 datasheet, pin_map, pitch=pitch, body_width=body_width)


def main():
    parts = []

    # ---- CM4 100-pin connector (used for both J1 and J2 instances) ----
    from design_data import CM4_J1_PINS
    cm4_pins = {i: CM4_J1_PINS.get(i, "NC") for i in range(1, 101)}
    parts.append(two_column_connector(
        "CM4_Connector_100", "J", "SKYWARD_Custom:Hirose_DF40C-100DS-0.4V",
        "Raspberry Pi CM4 100-pin 0.4mm high-density connector (functional pin "
        "map -- verify pin numbers against official CM4 datasheet before fab, "
        "see docs/assumptions.md #1)",
        "~", cm4_pins, pitch=1.27, body_width=17.78))

    # ---- Terra 22-pin payload connector ----
    terra_pins = {
        1: "TERRA_PWR", 2: "GND", 3: "GND", 4: "TERRA_SDA", 5: "TERRA_SCL",
        6: "TERRA_SCLK", 7: "TERRA_MOSI", 8: "TERRA_MISO", 9: "TERRA_CS_N",
        10: "UART4_TXD", 11: "UART4_RXD", 12: "TERRA_USB_DP", 13: "TERRA_USB_DN",
        14: "TERRA_GPIO_A", 15: "TERRA_GPIO_B", 16: "TERRA_IRQ_N", 17: "TERRA_TRIG",
        18: "TERRA_PRESENCE_N", 19: "GND", 20: "TERRA_PWR", 21: "TERRA_BATT_RAW",
        22: "TERRA_BATT_RAW",
    }
    parts.append(two_column_connector(
        "Terra_Connector_22", "J", "SKYWARD_Custom:Hirose_DF13-22DP-1.25V",
        "Maverick 1000 standardized Terra payload bus, 22-pin, see docs/connector_pinouts.md",
        "~", terra_pins, pitch=2.54, body_width=20.32))

    # ---- LM74610 ideal-diode ORing controller (simplified 6-pin model) ----
    lm_pins = {1: "SNS", 2: "GND", 3: "VCAP", 4: "GATE", 5: "SUP", 6: "NC"}
    parts.append(ic_symbol(
        "LM74610", "U", "Package_TO_SOT_SMD:SOT-23-6",
        "TI LM74610-Q1 ideal-diode ORing controller (drives an external P-MOSFET)",
        "https://www.ti.com/lit/ds/symlink/lm74610-q1.pdf", lm_pins,
        pitch=2.54, body_width=15.24))

    # ---- BQ25792 charger, simplified to the 8 nets used in Rev A ----
    bq_pins = {1: "VAC1", 2: "GND", 3: "SW", 4: "VDD_LOGIC", 5: "SDA", 6: "SCL",
               7: "PROG", 8: "PGND"}
    parts.append(ic_symbol(
        "BQ25792", "U", "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm",
        "TI BQ25792 1-4S I2C buck charger -- SIMPLIFIED to the 8 nets used in "
        "Rev A. Full 24-pin QFN pinout must be reconciled against the datasheet "
        "before fabrication, see docs/assumptions.md #9",
        "https://www.ti.com/lit/ds/symlink/bq25792.pdf", bq_pins,
        pitch=2.54, body_width=15.24))

    out = HEADER + "".join(parts) + FOOTER
    path = "/home/user/Schematics/Maverick1000/kicad/libraries/symbols/SKYWARD_Custom.kicad_sym"
    with open(path, "w") as f:
        f.write(out)
    print(f"Wrote {path} ({len(parts)} symbols)")


if __name__ == "__main__":
    main()
