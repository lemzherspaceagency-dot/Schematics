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


def two_column_symbol_sparse(sym_name, ref_prefix, footprint, description, datasheet,
                              pin_list, pitch=1.27, body_width=17.78):
    """Like two_column_connector, but for real parts whose pin *numbers* are
    not a dense 1..N range (e.g. an LCC package that omits certain physical
    positions). pin_list: ordered list of (real_pin_number, name, etype)
    tuples, in the order they should be drawn -- first half down the left
    side (pointing left), second half down the right side (pointing right).
    The drawn pin carries its REAL number, not a sequential index, so a
    gap in the real numbering does not silently renumber/misassign a pin."""
    n = len(pin_list)
    half = n // 2 + (n % 2)
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
    for i, (real_num, name, etype) in enumerate(pin_list):
        if i < half:
            y = top_y - i * pitch
            x = -body_width / 2
            rot = 0
        else:
            y = top_y - (i - half) * pitch
            x = body_width / 2
            rot = 180
        pins_txt.append(pin(real_num, name, x, y, rot, length=5.08, etype=etype))
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

    # ---- U7: Microchip USB2512B, 2-port USB2.0 Hi-Speed hub --------------
    # Real, dense 1-37 pinout (36 signal pins + EP), extracted from a real,
    # working KiCad symbol published by EwoudVV/ducktop2 on GitHub (which
    # itself cites Microchip's real datasheet URL and models the real part
    # "USB2512B-AEZG-TR") -- see docs/COMMS_MODULE_DECISION.md. Footprint
    # is KiCad's own maintained stock QFN-36-1EP part (matches the source
    # symbol's own footprint reference exactly), not an approximation.
    usb2512b_pins = {
        1: ("USBDM_DN1", "bidirectional"), 2: ("USBDP_DN1", "bidirectional"),
        3: ("USBDM_DN2", "bidirectional"), 4: ("USBDP_DN2", "bidirectional"),
        5: ("VDDA33", "power_in"), 6: ("NC", "no_connect"), 7: ("NC", "no_connect"),
        8: ("NC", "no_connect"), 9: ("NC", "no_connect"), 10: ("VDDA33", "power_in"),
        11: ("TEST", "no_connect"), 12: ("PRTPWR1", "output"), 13: ("OCS_N1", "input"),
        14: ("CRFILT", "passive"), 15: ("VDD33", "power_in"), 16: ("PRTPWR2", "output"),
        17: ("OCS_N2", "input"), 18: ("NC", "no_connect"), 19: ("NC", "no_connect"),
        20: ("NC", "no_connect"), 21: ("NC", "no_connect"), 22: ("SDA", "bidirectional"),
        23: ("VDD33", "power_in"), 24: ("SCL", "bidirectional"), 25: ("HS_IND", "bidirectional"),
        26: ("RESET_N", "input"), 27: ("VBUS_DET", "input"), 28: ("SUSP_IND", "bidirectional"),
        29: ("VDDA33", "power_in"), 30: ("USBDM_UP", "bidirectional"), 31: ("USBDP_UP", "bidirectional"),
        32: ("XTALOUT", "output"), 33: ("XTALIN", "input"), 34: ("PLLFILT", "passive"),
        35: ("RBIAS", "input"), 36: ("VDDA33", "power_in"), 37: ("VSS_EP", "power_in"),
    }
    parts.append(ic_symbol(
        "USB2512B", "U",
        "Package_DFN_QFN:QFN-36-1EP_6x6mm_P0.5mm_EP3.7x3.7mm_ThermalVias",
        "Microchip USB2512B-AEZG-TR, 2-port USB2.0 Hi-Speed multi-TT hub. "
        "Real pinout + real stock-KiCad-footprint reference, see "
        "docs/COMMS_MODULE_DECISION.md.",
        "https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ProductDocuments/DataSheets/USB251xB-xBi-Data-Sheet-DS00001692.pdf",
        usb2512b_pins, pitch=2.54, body_width=22.86))

    # ---- U8: Quectel EC25 (EC25VFA-512-STD), LTE Cat 4 modem --------------
    # Real 132-pin pinout (gapped 1-144 numbering, pins 73-84 not
    # physically present), extracted programmatically from a real, working
    # KiCad symbol published by SPIRIT-org/SPIRIT on GitHub, whose own
    # embedded metadata states manufacturer=Quectel and describes the part
    # as "a series of 4G - LTE Cat 4 module" -- see
    # docs/COMMS_MODULE_DECISION.md for the full sourcing/verification
    # writeup, including a parsing bug (pins using a "clock" graphic style
    # were silently dropped by the first extraction attempt) that was
    # caught by a pin-count sanity check before being trusted.
    ec25_pins = {
        1: ("WAKEUP_IN", "input"), 2: ("AP_READY", "input"), 3: ("RSVD", "passive"),
        4: ("W_DISABLE#", "input"), 5: ("NET_MODE", "output"), 6: ("NET_STATUS", "output"),
        7: ("VDD_EXT", "power_in"), 8: ("GND", "power_in"), 9: ("GND", "power_in"),
        10: ("USIM_GND", "power_in"), 11: ("DBG_RXD", "input"), 12: ("DBG_TXD", "output"),
        13: ("USIM_PRESENCE", "input"), 14: ("USIM_VDD", "power_in"), 15: ("USIM_DATA", "bidirectional"),
        16: ("USIM_CLK", "output"), 17: ("USIM_RST", "output"), 18: ("RSVD", "passive"),
        19: ("GND", "power_in"), 20: ("RESET_N", "input"), 21: ("PWRKEY", "input"),
        22: ("GND", "power_in"), 23: ("SD_INS_DET", "input"), 24: ("PCM_IN", "input"),
        25: ("PCM_OUT", "output"), 26: ("PCM_SYNC", "bidirectional"), 27: ("PCM_CLK", "bidirectional"),
        28: ("SDC2_DATA3", "bidirectional"), 29: ("SDC2_DATA2", "bidirectional"), 30: ("SDC2_DATA1", "bidirectional"),
        31: ("SDC2_DATA0", "bidirectional"), 32: ("SDC2_CLK", "output"), 33: ("SDC2_CMD", "bidirectional"),
        34: ("VDD_SDIO", "power_in"), 35: ("ANT_DIV", "input"), 36: ("GND", "power_in"),
        37: ("BT_RTS", "input"), 38: ("BT_TXD", "output"), 39: ("BT_RXD", "input"),
        40: ("BT_CTS", "output"), 41: ("I2C_SCL", "output"), 42: ("I2C_SDA", "output"),
        43: ("RSVD", "passive"), 44: ("ADC1", "input"), 45: ("ADC0", "input"),
        46: ("GND", "power_in"), 47: ("ANT_GNSS", "input"), 48: ("GND", "power_in"),
        49: ("ANT_MAIN", "bidirectional"), 50: ("GND", "power_in"), 51: ("GND", "power_in"),
        52: ("GND", "power_in"), 53: ("GND", "power_in"), 54: ("GND", "power_in"),
        55: ("RSVD", "passive"), 56: ("GND", "power_in"), 57: ("VBAT_RF", "power_in"),
        58: ("VBAT_RF", "power_in"), 59: ("VBAT_BB", "power_in"), 60: ("VBAT_BB", "power_in"),
        61: ("STATUS", "output"), 62: ("RI", "output"), 63: ("DCD", "output"),
        64: ("CTS", "output"), 65: ("RTS", "input"), 66: ("DTR", "input"),
        67: ("TXD", "output"), 68: ("RXD", "input"), 69: ("USB_DP", "bidirectional"),
        70: ("USB_DM", "bidirectional"), 71: ("USB_VBUS", "input"), 72: ("GND", "power_in"),
        85: ("GND", "power_in"), 86: ("GND", "power_in"), 87: ("GND", "power_in"),
        88: ("GND", "power_in"), 89: ("GND", "power_in"), 90: ("GND", "power_in"),
        91: ("GND", "power_in"), 92: ("GND", "power_in"), 93: ("GND", "power_in"),
        94: ("GND", "power_in"), 95: ("GND", "power_in"), 96: ("GND", "power_in"),
        97: ("GND", "power_in"), 98: ("GND", "power_in"), 99: ("GND", "power_in"),
        100: ("GND", "power_in"), 101: ("GND", "power_in"), 102: ("GND", "power_in"),
        103: ("GND", "power_in"), 104: ("GND", "power_in"), 105: ("GND", "power_in"),
        106: ("GND", "power_in"), 107: ("GND", "power_in"), 108: ("GND", "power_in"),
        109: ("GND", "power_in"), 110: ("GND", "power_in"), 111: ("GND", "power_in"),
        112: ("GND", "power_in"), 113: ("RSVD", "passive"), 114: ("RSVD", "passive"),
        115: ("USB_BOOT", "input"), 116: ("RSVD", "passive"), 117: ("RSVD", "passive"),
        118: ("WLAN_SLP_CLK", "output"), 119: ("EPHY_RST_N", "output"), 120: ("EPHY_INT_N", "input"),
        121: ("SGMII_MDATA", "bidirectional"), 122: ("SGMII_MCLK", "output"), 123: ("SGMII_TX_M", "output"),
        124: ("SGMII_TX_P", "output"), 125: ("SGMII_RX_P", "input"), 126: ("SGMII_RX_M", "input"),
        127: ("PM_ENABLE", "output"), 128: ("USIM2_VDD", "power_in"), 129: ("SDC1_DATA3", "bidirectional"),
        130: ("SDC1_DATA2", "bidirectional"), 131: ("SDC1_DATA1", "bidirectional"), 132: ("SDC1_DATA0", "bidirectional"),
        133: ("SDC1_CLK", "output"), 134: ("SDC1_CMD", "output"), 135: ("WAKE_ON_WIRELESS", "input"),
        136: ("WLAN_EN", "output"), 137: ("COEX_UART_RX", "input"), 138: ("COEX_UART_TX", "output"),
        139: ("BT_EN", "output"), 140: ("RSVD", "passive"), 141: ("RSVD", "passive"),
        142: ("RSVD", "passive"), 143: ("RSVD", "passive"), 144: ("RSVD", "passive"),
    }
    ec25_pin_list = [(num, name, etype) for num, (name, etype) in sorted(ec25_pins.items())]
    parts.append(two_column_symbol_sparse(
        "EC25", "U", "SKYWARD_Custom:LCC-132_EC25_verified",
        "Quectel EC25VFA-512-STD, LTE Cat 4 modem, LCC-132 package. Real "
        "pinout verified against a real, working KiCad symbol; footprint "
        "verified against a real, open-hardware footprint for the "
        "footprint-compatible EG25-G sibling module -- see "
        "docs/EC25_FOOTPRINT_VERIFICATION.md.",
        "~", ec25_pin_list, pitch=1.27, body_width=25.4))

    out = HEADER + "".join(parts) + FOOTER
    path = "/home/user/Schematics/Maverick1000/kicad/libraries/symbols/SKYWARD_Custom.kicad_sym"
    with open(path, "w") as f:
        f.write(out)
    print(f"Wrote {path} ({len(parts)} symbols)")


if __name__ == "__main__":
    main()
