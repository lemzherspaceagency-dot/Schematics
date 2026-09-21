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
        entry = pin_map[idx]
        name, etype = entry if isinstance(entry, tuple) else (entry, "passive")
        if idx <= half:
            y = top_y - (idx - 1) * pitch
            x = -body_width / 2
            rot = 0
        else:
            y = top_y - (idx - half - 1) * pitch
            x = body_width / 2
            rot = 180
        pins_txt.append(pin(idx, name, x, y, rot, length=5.08, etype=etype))
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

    # ---- CM4 100-pin connectors: J1 (physical pins 1-100) and J2 (101-200,
    # offset -100) are two DIFFERENT halves of the real 200-pin CM4 edge
    # connector pair and need two DIFFERENT symbol parts, each with its own
    # pin function names. An earlier revision generated only one symbol
    # (from CM4_J1_PINS) and reused it for both J1 and J2 -- net wiring was
    # still correct (design_data.py wires each instance's pins by NUMBER,
    # from the correct per-connector dict), but J2's schematic pin labels
    # were silently J1's, e.g. showing "I2C0_SCL" on a J2 pin that is
    # actually a plain GND/NC pin on the real connector. Found via an ERC-
    # equivalent netlist check (see docs/ERC_STATUS.md) cross-referencing
    # exported pinfunction names against design_data.py.
    from design_data import CM4_J1_PINS, CM4_J2_PINS
    cm4_j1_pins = {i: CM4_J1_PINS.get(i, "NC") for i in range(1, 101)}
    cm4_j2_pins = {i: CM4_J2_PINS.get(i, "NC") for i in range(1, 101)}
    parts.append(two_column_connector(
        "CM4_Connector_100_J1", "J", "SKYWARD_Custom:Hirose_DF40C-100DS-0.4V",
        "Raspberry Pi CM4 100-pin 0.4mm high-density connector, J1 half "
        "(physical pins 1-100) -- verify pin numbers against official CM4 "
        "datasheet before fab, see docs/assumptions.md #1",
        "~", cm4_j1_pins, pitch=1.27, body_width=17.78))
    parts.append(two_column_connector(
        "CM4_Connector_100_J2", "J", "SKYWARD_Custom:Hirose_DF40C-100DS-0.4V",
        "Raspberry Pi CM4 100-pin 0.4mm high-density connector, J2 half "
        "(physical pins 101-200, local numbering 1-100) -- verify pin "
        "numbers against official CM4 datasheet before fab, see "
        "docs/assumptions.md #1",
        "~", cm4_j2_pins, pitch=1.27, body_width=17.78))

    # ---- Terra 22-pin payload connector ----
    terra_pins = {
        1: "TERRA_PWR", 2: "GND", 3: "GND", 4: "TERRA_SDA", 5: "TERRA_SCL",
        6: "TERRA_SCLK", 7: "TERRA_MOSI", 8: "TERRA_MISO", 9: "TERRA_CS_N",
        10: "NC", 11: "NC", 12: "TERRA_USB_DP", 13: "TERRA_USB_DN",
        14: "TERRA_GPIO_A", 15: "TERRA_GPIO_B", 16: "TERRA_IRQ_N", 17: "TERRA_TRIG",
        18: "TERRA_PRESENCE_N", 19: "GND", 20: "TERRA_PWR", 21: "TERRA_BATT_RAW",
        22: "TERRA_BATT_RAW",
    }
    parts.append(two_column_connector(
        "Terra_Connector_22", "J", "SKYWARD_Custom:Hirose_DF13-22DP-1.25V",
        "Maverick 1000 standardized Terra payload bus, 22-pin, see docs/connector_pinouts.md",
        "~", terra_pins, pitch=2.54, body_width=20.32))

    # ---- LM74610-Q1 ideal-diode ORing controller: real 8-pin VSSOP-8 -----
    # Pin names/numbers verified against 2 independent open-source KiCad
    # libraries for LM74610QDGKRQ1 (VSSOP-8) which agree exactly -- the
    # pre-audit Rev A incorrectly modeled this as a 6-pin SOT-23-6 part
    # with invented pin names (SNS/GND/VCAP/GATE/SUP). The real part has
    # NO ground pin (it floats, parasitically powered between ANODE and
    # CATHODE) and needs a cap across VCAPL/VCAPH, not to ground. See
    # docs/LM74610_VERIFICATION.md.
    lm_pins = {
        1: ("VCAPL", "output"), 2: ("GATE_PULL_DOWN", "bidirectional"),
        3: ("NC", "no_connect"), 4: ("ANODE", "bidirectional"),
        5: ("NC", "no_connect"), 6: ("GATE_DRIVE", "output"),
        7: ("VCAPH", "output"), 8: ("CATHODE", "bidirectional"),
    }
    parts.append(ic_symbol(
        "LM74610QDGKRQ1", "U", "Package_SO:VSSOP-8_3.0x3.0mm_P0.65mm",
        "TI LM74610-Q1 ideal-diode ORing controller, VSSOP-8 (drives an "
        "external back-to-back-free single P-MOSFET; floats between ANODE "
        "and CATHODE, no GND pin) -- see docs/LM74610_VERIFICATION.md",
        "https://www.ti.com/lit/ds/symlink/lm74610-q1.pdf", lm_pins,
        pitch=2.54, body_width=20.32))

    # ---- BQ25792 charger: full real 29-pin WQFN pinout ----
    # Verified pin numbers/names/electrical types cross-referenced against
    # multiple independent real BQ25792RQMR KiCad libraries on GitHub
    # (M17-Project/LinHT-hw -- a shipped ham-radio product -- and a
    # tscircuit dataset import), which independently agree pin-for-pin.
    # Primary TI datasheet PDF access was blocked in this environment; see
    # docs/BQ25792_VERIFICATION.md for full methodology and residual risk.
    bq_pins = {
        1: ("STAT", "output"),
        2: ("VBUS", "power_in"), 3: ("VBUS", "power_in"),
        4: ("BTST1", "input"),
        5: ("REGN", "power_out"),
        6: ("D+", "bidirectional"), 7: ("D-", "bidirectional"),
        8: ("VAC2", "power_in"), 9: ("VAC1", "power_in"),
        10: ("ACDRV2", "power_in"), 11: ("ACDRV1", "power_in"),
        12: ("~{QON}", "input"), 13: ("~{CE}", "input"),
        14: ("SCL", "input"), 15: ("SDA", "bidirectional"),
        16: ("TS", "input"), 17: ("ILIM_HIZ", "input"),
        18: ("BATP", "input"), 19: ("BTST2", "input"),
        20: ("PROG", "input"), 21: ("~{INT}", "output"),
        22: ("BAT", "power_out"), 23: ("BAT", "power_out"),
        24: ("SDRV", "power_out"), 25: ("SYS", "power_out"),
        26: ("SW2", "input"), 27: ("GND", "power_in"),
        28: ("SW1", "input"), 29: ("PMID", "power_out"),
        30: ("EP", "power_in"),  # exposed thermal/ground pad, see docs/BQ25792_VERIFICATION.md
    }
    parts.append(two_column_connector(
        "BQ25792RQMR", "U",
        "SKYWARD_Custom:QFN-29_L4.0-W4.0-P0.40-BQ25792RQMR",
        "TI BQ25792 1-4S I2C-controlled buck-boost charger, dual-input "
        "selector, USB PD 3.0 OTG output. Full 29-pin WQFN pinout, "
        "verified against 2 independent open-source KiCad libraries -- "
        "see docs/BQ25792_VERIFICATION.md.",
        "https://www.ti.com/lit/ds/symlink/bq25792.pdf", bq_pins,
        pitch=2.54, body_width=20.32))

    out = HEADER + "".join(parts) + FOOTER
    path = "/home/user/Schematics/Maverick1000/kicad/libraries/symbols/SKYWARD_Custom.kicad_sym"
    with open(path, "w") as f:
        f.write(out)
    print(f"Wrote {path} ({len(parts)} symbols)")


if __name__ == "__main__":
    main()
