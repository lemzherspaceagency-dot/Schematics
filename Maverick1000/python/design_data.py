"""
SKYWARD-COMPUTE-CARRIER (Maverick 1000) — single source of truth for the
electrical design: every component and every net. Both the schematic
generator (gen_schematic.py) and the PCB generator (gen_pcb.py) import this
module so the two outputs can never disagree with each other.
"""

from dataclasses import dataclass


@dataclass
class Component:
    ref: str
    lib_id: str             # "Library:Symbol" for the schematic
    footprint: str           # "Library:Footprint" for the PCB
    value: str                # value shown on schematic (e.g. "10uF", "TPS54331")
    mpn: str = ""
    manufacturer: str = ""
    description: str = ""
    datasheet: str = "~"
    dnp: bool = False
    group: str = "misc"      # for BOM / schematic layout grouping
    footprint_group: str = "0603"  # rough size class, used for PCB placement spacing


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------
COMPONENTS: list[Component] = [
    # ---- CM4 module connectors -------------------------------------------------
    Component("J1", "SKYWARD_Custom:CM4_Connector_100", "SKYWARD_Custom:Hirose_DF40C-100DS-0.4V",
               "CM4_J1", "DF40C-100DS-0.4V(51)", "Hirose Electric",
               "100-pos 0.4mm SMD receptacle, CM4 primary connector (low/med-speed IO + power)",
               group="cm4", footprint_group="cm4conn"),
    Component("J2", "SKYWARD_Custom:CM4_Connector_100", "SKYWARD_Custom:Hirose_DF40C-100DS-0.4V",
               "CM4_J2", "DF40C-100DS-0.4V(51)", "Hirose Electric",
               "100-pos 0.4mm SMD receptacle, CM4 secondary connector (high-speed IO + power)",
               group="cm4", footprint_group="cm4conn"),

    # ---- CM4 support ------------------------------------------------------------
    Component("SW1", "Switch:SW_Push", "Button_Switch_SMD:SW_SPST_B3U-1000P",
               "nRPIBOOT", "B3U-1000P", "Omron", "Tactile SW, hold to force CM4 USB boot mode",
               group="cm4", footprint_group="sw"),
    Component("SW2", "Switch:SW_Push", "Button_Switch_SMD:SW_SPST_B3U-1000P",
               "RUN", "B3U-1000P", "Omron", "Tactile SW, CM4 reset",
               group="cm4", footprint_group="sw"),
    Component("R7", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "10k", "RC0402FR-0710KL", "Yageo", "nRPIBOOT pull-up", group="cm4"),
    Component("R8", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "10k", "RC0402FR-0710KL", "Yageo", "RUN_PG_N pull-up", group="cm4"),
    Component("R9", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "10k", "RC0402FR-0710KL", "Yageo", "EEPROM_nWP pull-up (default: boot config write-protected)", group="cm4"),
    Component("C11", "Device:C", "Capacitor_SMD:C_0402_1005Metric",
               "100nF", "GRM155R71H104KE14D", "Murata", "CM4 +5V0 decoupling", group="cm4"),
    Component("C12", "Device:C", "Capacitor_SMD:C_0402_1005Metric",
               "100nF", "GRM155R71H104KE14D", "Murata", "CM4 +5V0 decoupling", group="cm4"),
    Component("C13", "Device:C", "Capacitor_SMD:C_0402_1005Metric",
               "100nF", "GRM155R71H104KE14D", "Murata", "CM4 +5V0 decoupling", group="cm4"),
    Component("C14", "Device:C", "Capacitor_SMD:C_0603_1608Metric",
               "10uF", "GRM188R61A106KE69D", "Murata", "CM4 +5V0 bulk decoupling", group="cm4"),
    Component("C15", "Device:C", "Capacitor_SMD:C_0603_1608Metric",
               "10uF", "GRM188R61A106KE69D", "Murata", "CM4 +5V0 bulk decoupling", group="cm4"),
    Component("J10", "Connector_Generic:Conn_01x06", "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
               "DEBUG", "PBC06SAAN", "Sullins", "CM4 UART console + boot/reset header", group="cm4", footprint_group="header"),

    # ---- Power: main battery input ----------------------------------------------
    Component("J3", "Connector_Generic:Conn_01x02", "Connector_JST:JST_GH_SM02B-GHS-TB_1x02-1MP_P1.25mm_Horizontal",
               "BATT_IN", "SM02B-GHS-TB", "JST", "4S LiHV main battery low-current tap", group="power", footprint_group="jst"),
    Component("F1", "Device:Fuse", "Fuse:Fuse_1206_3216Metric",
               "3A_PTC", "1206L300/16DR", "Bourns", "Main battery input resettable PTC fuse", group="power"),
    Component("D1", "Device:D_TVS", "Diode_SMD:D_SMB",
               "SMBJ24A", "SMBJ24A", "Littelfuse", "Main battery input TVS clamp, 24V standoff", group="power"),
    Component("U1", "SKYWARD_Custom:LM74610", "Package_TO_SOT_SMD:SOT-23-6",
               "LM74610QDBVRQ1", "LM74610QDBVRQ1", "Texas Instruments",
               "Ideal-diode ORing controller, main battery", group="power", footprint_group="sot23-6"),
    Component("Q1", "Device:Q_PMOS_GSD", "Package_TO_SOT_SMD:SOT-23",
               "SQJ438EP", "SQJ438EP-T1_GE3", "Vishay Siliconix", "P-MOSFET, main battery ORing pass element",
               group="power", footprint_group="sot23"),
    Component("C1", "Device:C", "Capacitor_SMD:C_1210_3225Metric",
               "22uF", "GRM32ER71V226KE15L", "Murata", "Main battery input bulk cap", group="power"),
    Component("C16", "Device:C", "Capacitor_SMD:C_0402_1005Metric",
               "100nF", "GRM155R71H104KE14D", "Murata", "U1 (LM74610) VCAP charge-pump cap", group="power"),

    # ---- Power: Terra P1 battery input -------------------------------------------
    Component("F2", "Device:Fuse", "Fuse:Fuse_1206_3216Metric",
               "3A_PTC", "1206L300/16DR", "Bourns", "Terra P1 input resettable PTC fuse", group="power"),
    Component("D2", "Device:D_TVS", "Diode_SMD:D_SMB",
               "SMBJ24A", "SMBJ24A", "Littelfuse", "Terra P1 input TVS clamp, 24V standoff", group="power"),
    Component("U2", "SKYWARD_Custom:LM74610", "Package_TO_SOT_SMD:SOT-23-6",
               "LM74610QDBVRQ1", "LM74610QDBVRQ1", "Texas Instruments",
               "Ideal-diode ORing controller, Terra P1", group="power", footprint_group="sot23-6"),
    Component("Q2", "Device:Q_PMOS_GSD", "Package_TO_SOT_SMD:SOT-23",
               "SQJ438EP", "SQJ438EP-T1_GE3", "Vishay Siliconix", "P-MOSFET, Terra P1 ORing pass element",
               group="power", footprint_group="sot23"),
    Component("C2", "Device:C", "Capacitor_SMD:C_1210_3225Metric",
               "22uF", "GRM32ER71V226KE15L", "Murata", "Terra P1 input bulk cap", group="power"),
    Component("C17", "Device:C", "Capacitor_SMD:C_0402_1005Metric",
               "100nF", "GRM155R71H104KE14D", "Murata", "U2 (LM74610) VCAP charge-pump cap", group="power"),

    # ---- Power: 5V buck (CM4 + Terra) --------------------------------------------
    Component("U4", "Regulator_Switching:TPS5430DDA", "Package_SO:TI_SO-PowerPAD-8_ThermalVias",
               "TPS5430DDA", "TPS5430DDA", "Texas Instruments", "3A sync buck, 5.5-36V in, adjustable -> set for +5V0",
               group="power", footprint_group="soic8"),
    Component("L1", "Device:L", "Inductor_SMD:L_Coilcraft_XAL4020-XXX",
               "10uH", "XAL4020-103MEB", "Coilcraft", "5V buck inductor", group="power", footprint_group="inductor"),
    Component("C3", "Device:C", "Capacitor_SMD:C_0805_2012Metric",
               "10uF", "GRM21BR61H106KE43L", "Murata", "5V buck input cap", group="power"),
    Component("C4", "Device:C", "Capacitor_SMD:C_0805_2012Metric",
               "22uF", "GRM21BR61A226ME44L", "Murata", "5V buck output cap", group="power"),
    Component("C18", "Device:C", "Capacitor_SMD:C_0402_1005Metric",
               "10nF", "GRM155R71H103KA88D", "Murata", "5V buck BOOT bootstrap cap", group="power"),
    Component("R1", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "10.0k", "RC0402FR-0710KL", "Yageo", "5V buck FB divider top", group="power"),
    Component("R2", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "3.09k", "RC0402FR-073K09L", "Yageo", "5V buck FB divider bottom", group="power"),

    # ---- Power: 3V3 LDO -----------------------------------------------------------
    Component("U5", "Regulator_Linear:AP2112K-3.3", "Package_TO_SOT_SMD:SOT-23-5",
               "AP2112K-3.3TRG1", "AP2112K-3.3TRG1", "Diodes Inc.", "600mA LDO, +5V0 -> +3V3 (low-noise, GNSS-friendly)",
               group="power", footprint_group="sot23-5"),
    Component("C5", "Device:C", "Capacitor_SMD:C_0603_1608Metric",
               "1uF", "GRM188R61A105KA61D", "Murata", "3V3 LDO input cap", group="power"),
    Component("C6", "Device:C", "Capacitor_SMD:C_0603_1608Metric",
               "1uF", "GRM188R61A105KA61D", "Murata", "3V3 LDO output cap", group="power"),

    # ---- Power: battery/bus telemetry ----------------------------------------------
    Component("U6", "Power_Management:INA3221", "Package_SO:TSSOP-16_4.4x5mm_P0.65mm",
               "INA3221AIPW", "INA3221AIPW", "Texas Instruments", "3-ch I2C V/I monitor: main batt, P1 batt, +5V0",
               group="power", footprint_group="tssop16"),
    Component("RSH1", "Device:R", "Resistor_SMD:R_1206_3216Metric",
               "10mOhm", "WSL1206R0100FEA", "Vishay", "Main battery current shunt", group="power"),
    Component("RSH2", "Device:R", "Resistor_SMD:R_1206_3216Metric",
               "10mOhm", "WSL1206R0100FEA", "Vishay", "Terra P1 current shunt", group="power"),
    Component("RSH3", "Device:R", "Resistor_SMD:R_1206_3216Metric",
               "10mOhm", "WSL1206R0100FEA", "Vishay", "+5V0 CM4 rail current shunt", group="power"),

    # ---- Power: dock charging -------------------------------------------------------
    Component("J4", "Connector_Generic:Conn_01x03", "Connector_JST:JST_GH_SM03B-GHS-TB_1x03-1MP_P1.25mm_Horizontal",
               "DOCK", "SM03B-GHS-TB", "JST", "Dock power + presence-detect, wired to skid contacts", group="power", footprint_group="jst"),
    Component("F3", "Device:Fuse", "Fuse:Fuse_1206_3216Metric",
               "1.5A_PTC", "1206L150/16DR", "Bourns", "Dock charge input PTC fuse", group="power"),
    Component("D3", "Device:D_Schottky", "Diode_SMD:D_SMA",
               "SS34", "SS34", "Onsemi", "Dock input reverse-polarity protection", group="power"),
    Component("D4", "Device:D_TVS", "Diode_SMD:D_SMB",
               "SMBJ24A", "SMBJ24A", "Littelfuse", "Dock input TVS clamp", group="power"),
    Component("U3", "SKYWARD_Custom:BQ25792", "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm",
               "BQ25792RQMR", "BQ25792RQMR", "Texas Instruments", "1-4S I2C buck charger, dock -> main battery",
               group="power", footprint_group="qfn24"),
    Component("L2", "Device:L", "Inductor_SMD:L_Coilcraft_XAL4020-XXX",
               "2.2uH", "XAL4020-222MEB", "Coilcraft", "BQ25792 charge inductor", group="power", footprint_group="inductor"),
    Component("C7", "Device:C", "Capacitor_SMD:C_0805_2012Metric",
               "10uF", "GRM21BR61H106KE43L", "Murata", "BQ25792 input cap", group="power"),
    Component("C8", "Device:C", "Capacitor_SMD:C_0805_2012Metric",
               "10uF", "GRM21BR61H106KE43L", "Murata", "BQ25792 SYS/output cap", group="power"),
    Component("C9", "Device:C", "Capacitor_SMD:C_0402_1005Metric",
               "100nF", "GRM155R71H104KE14D", "Murata", "BQ25792 decoupling", group="power"),
    Component("C10", "Device:C", "Capacitor_SMD:C_0402_1005Metric",
               "100nF", "GRM155R71H104KE14D", "Murata", "BQ25792 decoupling", group="power"),
    Component("R3", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "5.6k", "RC0402FR-075K6L", "Yageo", "BQ25792 ILIM/PROG set resistor", group="power"),
    Component("R5", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "10k", "RC0402FR-0710KL", "Yageo", "GPIO_DOCK_DET pull-up (dock presence detect)", group="power"),

    # ---- Terra payload fuse & pull-ups ------------------------------------------------
    Component("F4", "Device:Fuse", "Fuse:Fuse_1206_3216Metric",
               "2A_PTC", "1206L200/16DR", "Bourns", "Terra TERRA_PWR independent fuse", group="power"),
    Component("R10", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "4.7k", "RC0402FR-074K7L", "Yageo", "I2C0 SDA pull-up (VL53L5CX/INA3221/BQ25792 bus)", group="periph"),
    Component("R11", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "4.7k", "RC0402FR-074K7L", "Yageo", "I2C0 SCL pull-up", group="periph"),
    Component("R12", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "4.7k", "RC0402FR-074K7L", "Yageo", "I2C1 SDA pull-up (Terra bus)", group="periph"),
    Component("R13", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "4.7k", "RC0402FR-074K7L", "Yageo", "I2C1 SCL pull-up", group="periph"),
    Component("R14", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "10k", "RC0402FR-0710KL", "Yageo", "TERRA_PRESENCE_N pull-up", group="periph"),
    Component("R15", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "10k", "RC0402FR-0710KL", "Yageo", "VL53L5CX XSHUT default pull-up (solder-jumper option, see JP1)", group="periph"),
    Component("JP1", "Connector_Generic:Conn_01x03", "Jumper:SolderJumper-3_P1.3mm_Bridged12_Pad1.0x1.5mm",
               "XSHUT_SEL", "-", "-", "VL53L5CX XSHUT source select: free-run (default) vs CM4 GPIO", group="periph", footprint_group="jumper"),

    # ---- Peripheral connectors --------------------------------------------------------
    Component("J5", "Connector_Generic:Conn_01x06", "Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal",
               "FC", "SM06B-GHS-TB", "JST", "Flight controller UART/telemetry link", group="periph", footprint_group="jst"),
    Component("J6", "Connector_Generic:Conn_01x06", "Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal",
               "GNSS", "SM06B-GHS-TB", "JST", "BN-220 GNSS UART + PPS", group="periph", footprint_group="jst"),
    Component("J7", "Connector_Generic:Conn_01x04", "Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal",
               "ELRS", "SM04B-GHS-TB", "JST", "ELRS receiver UART", group="periph", footprint_group="jst"),
    Component("J8", "Connector_Generic:Conn_01x05", "Connector_JST:JST_SH_SM05B-SRSS-TB_1x05-1MP_P1.00mm_Horizontal",
               "TOF", "SM05B-SRSS-TB", "JST", "VL53L5CX-SATEL I2C + power", group="periph", footprint_group="jst"),
    Component("J9", "SKYWARD_Custom:Terra_Connector_22", "SKYWARD_Custom:Hirose_DF13-22DP-1.25V",
               "TERRA", "DF13-22DP-1.25V", "Hirose Electric", "Standardized Terra payload bus", group="periph", footprint_group="terra"),

    # ---- Test points --------------------------------------------------------------------
    Component("TP1", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm",
               "VBAT_BUS", "-", "-", "Test point, aircraft power bus", group="tp"),
    Component("TP2", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm",
               "+5V0", "-", "-", "Test point, +5V0 rail", group="tp"),
    Component("TP3", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm",
               "+3V3", "-", "-", "Test point, +3V3 rail", group="tp"),
    Component("TP4", "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.5mm",
               "GND", "-", "-", "Test point, ground reference", group="tp"),

    # ---- Status LED -----------------------------------------------------------------------
    Component("LED1", "Device:LED", "LED_SMD:LED_0603_1608Metric",
               "STATUS", "KP-1608SURCK", "Kingbright", "CM4-controlled status LED", group="periph"),
    Component("R6", "Device:R", "Resistor_SMD:R_0603_1608Metric",
               "330", "RC0603FR-07330RL", "Yageo", "Status LED current limit", group="periph"),

    # ---- Mounting holes ---------------------------------------------------------------------
    Component("MH1", "Mechanical:MountingHole", "MountingHole:MountingHole_2.7mm_M2.5",
               "M2.5", "-", "-", "Mounting hole", group="mech"),
    Component("MH2", "Mechanical:MountingHole", "MountingHole:MountingHole_2.7mm_M2.5",
               "M2.5", "-", "-", "Mounting hole", group="mech"),
    Component("MH3", "Mechanical:MountingHole", "MountingHole:MountingHole_2.7mm_M2.5",
               "M2.5", "-", "-", "Mounting hole", group="mech"),
    Component("MH4", "Mechanical:MountingHole", "MountingHole:MountingHole_2.7mm_M2.5",
               "M2.5", "-", "-", "Mounting hole", group="mech"),
]

COMP_BY_REF = {c.ref: c for c in COMPONENTS}

# ---------------------------------------------------------------------------
# CM4 pin-number assignment (functional -> pin number).
# SEE docs/assumptions.md #1: verify against the official CM4 datasheet
# before fabrication. Unlisted pins (1-100 per connector) are NC.
# Power pins use the board-wide net name "+5V0" / "GND" directly so there is
# exactly one net object shared with the rest of the schematic.
# ---------------------------------------------------------------------------
CM4_J1_PINS = {
    1: "GND", 2: "GND",
    3: "+5V0", 4: "+5V0", 5: "+5V0",
    6: "GND",
    7: "RUN_PG_N", 8: "EEPROM_nWP", 9: "nRPIBOOT",
    10: "+3V3",  # GLOBAL_EN, tied high for normal always-enabled module operation
    11: "GND",
    12: "UART0_TXD0", 13: "UART0_RXD0",
    14: "UART1_TXD1", 15: "UART1_RXD1",
    16: "GND",
    17: "UART2_TXD", 18: "UART2_RXD",
    19: "UART3_TXD", 20: "UART3_RXD",
    21: "GND",
    22: "I2C0_SDA", 23: "I2C0_SCL",
    24: "I2C1_SDA", 25: "I2C1_SCL",
    26: "GND",
    27: "SPI0_SCLK", 28: "SPI0_MOSI", 29: "SPI0_MISO", 30: "SPI0_CE0_N",
    31: "GND",
    32: "USB2_0_DP", 33: "USB2_0_DN",
    34: "GND",
    35: "GPIO_DOCK_DET", 36: "GPIO_GNSS_PPS", 37: "GPIO_TOF_INT",
    38: "GPIO_TERRA_IRQ", 39: "GPIO_TERRA_TRIG", 40: "GPIO_TERRA_A",
    41: "GPIO_TERRA_B", 42: "GPIO_FC_RESET", 43: "GPIO_FC_AUX",
    44: "GPIO_STATUS_LED",
    45: "GND",
    46: "UART4_TXD", 47: "UART4_RXD",  # 5th PL011-capable UART instance, alt GPIO function, dedicated to Terra
}
CM4_J2_PINS = {
    1: "GND", 2: "+5V0", 3: "GND", 4: "+5V0", 5: "GND",
    6: "+5V0", 7: "GND", 8: "+5V0", 9: "GND", 10: "GND",
}

# ---------------------------------------------------------------------------
# Full net list: net_name -> [(ref, pin_number_or_name), ...]
# ---------------------------------------------------------------------------
NETS: dict[str, list[tuple[str, str]]] = {}


def _add(net, ref, pin):
    NETS.setdefault(net, []).append((ref, str(pin)))


# CM4 connector pins, from the tables above
for _pin, _sig in CM4_J1_PINS.items():
    _add(_sig, "J1", _pin)
for _pin, _sig in CM4_J2_PINS.items():
    _add(_sig, "J2", _pin)

# --- Power path: main battery -> ORing -> VBAT_BUS --------------------------
# LM74610 custom symbol pin map (see gen_symbols.py): 1 SNS, 2 GND, 3 VCAP,
# 4 GATE, 5 SUP, 6 NC. It senses/drives its OWN pass FET only (Q1) -- the
# instrumentation shunt (RSH1) sits downstream of Q1's drain, in series
# toward the merged VBAT_BUS node, so it reads main-battery branch current
# only, not the merged total.
_add("BATT_IN", "J3", 1)
_add("GND", "J3", 2)
_add("BATT_IN", "F1", 1)
_add("BATT_F", "F1", 2)
_add("BATT_F", "D1", 1)      # TVS
_add("GND", "D1", 2)
_add("BATT_F", "U1", 1)       # SNS (battery/source side)
_add("GND", "U1", 2)          # GND
_add("VCAP1", "U1", 3)        # VCAP
_add("Q1_GATE", "U1", 4)      # GATE drive to Q1
_add("VBAT_MAIN_OUT", "U1", 5)  # SUP (senses across Q1: drain side)
_add("VCAP1", "C16", 1); _add("GND", "C16", 2)
_add("BATT_F", "Q1", 2)       # Source
_add("Q1_GATE", "Q1", 1)      # Gate
_add("VBAT_MAIN_OUT", "Q1", 3)  # Drain
_add("BATT_F", "C1", 1)
_add("GND", "C1", 2)
_add("VBAT_MAIN_OUT", "RSH1", 1)
_add("VBAT_BUS", "RSH1", 2)

# --- Power path: Terra P1 -> ORing -> VBAT_BUS -------------------------------
_add("TERRA_BATT_RAW", "J9", 21)
_add("TERRA_BATT_RAW", "J9", 22)
_add("TERRA_BATT_RAW", "F2", 1)
_add("P1_F", "F2", 2)
_add("P1_F", "D2", 1)
_add("GND", "D2", 2)
_add("P1_F", "U2", 1)          # SNS
_add("GND", "U2", 2)           # GND
_add("VCAP2", "U2", 3)         # VCAP
_add("Q2_GATE", "U2", 4)       # GATE
_add("VBAT_P1_OUT", "U2", 5)   # SUP (senses across Q2)
_add("VCAP2", "C17", 1); _add("GND", "C17", 2)
_add("P1_F", "Q2", 2)          # Source
_add("Q2_GATE", "Q2", 1)       # Gate
_add("VBAT_P1_OUT", "Q2", 3)   # Drain
_add("P1_F", "C2", 1)
_add("GND", "C2", 2)
_add("VBAT_P1_OUT", "RSH2", 1)
_add("VBAT_BUS", "RSH2", 2)

# --- 5V buck (U4, TPS5430DDA): VBAT_BUS -> +5V0 -------------------------------
# Real pinout (verified against installed KiCad symbol): 1 BOOT, 4 VSENSE,
# 5 EN, 6 GND, 7 VIN, 8 PH, 9 GNDPAD. Pins 2/3 are NC.
_add("VBAT_BUS", "C3", 1)
_add("GND", "C3", 2)
_add("VBAT_BUS", "U4", 7)     # VIN
_add("GND", "U4", 6)           # GND
_add("5V0_SW", "U4", 8)        # PH (switch node)
_add("BOOT_5V", "U4", 1)       # BOOT
_add("5V0_SW", "C18", 1)
_add("BOOT_5V", "C18", 2)
_add("FB5V", "U4", 4)          # VSENSE
_add("VBAT_BUS", "U4", 5)      # EN, tied to VIN (always enabled)
_add("GND", "U4", 9)           # GNDPAD (thermal)
_add("5V0_SW", "L1", 1)
_add("5V0_PRE", "L1", 2)
_add("5V0_PRE", "RSH3", 1)
_add("+5V0", "RSH3", 2)
_add("+5V0", "C4", 1)
_add("GND", "C4", 2)
_add("+5V0", "R1", 1)
_add("FB5V", "R1", 2)
_add("FB5V", "R2", 1)
_add("GND", "R2", 2)

# --- 3V3 LDO (U5, AP2112K-3.3): +5V0 -> +3V3 -----------------------------------
# Real pinout (verified): 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT.
_add("+5V0", "C5", 1)
_add("GND", "C5", 2)
_add("+5V0", "U5", 1)     # VIN
_add("GND", "U5", 2)       # GND
_add("+5V0", "U5", 3)      # EN tied to VIN (always on)
_add("+3V3", "U5", 5)      # VOUT
_add("+3V3", "C6", 1)
_add("GND", "C6", 2)
# U5 pin 4 (NC) intentionally unconnected -- no-connect flagged by schematic generator.

# --- INA3221 (U6): 3-ch battery/bus telemetry ---------------------------------
# Real pinout (verified against installed KiCad symbol):
#   1 IN-3, 2 IN+3, 3 GND, 4 VS, 5 A0, 6 SCL, 7 SDA, 8 WARNING, 9 CRITICAL,
#   10 PV, 11 IN-1, 12 IN+1, 13 TC, 14 IN-2, 15 IN+2, 16 VPU, 17 EP.
# Each channel's shunt sits in that branch alone (see RSH1/RSH2/RSH3 above),
# so each channel reads only its own source's current, not the merged bus.
_add("+3V3", "U6", 4)         # VS
_add("GND", "U6", 3)           # GND
_add("I2C0_SDA", "U6", 7)
_add("I2C0_SCL", "U6", 6)
_add("GND", "U6", 5)           # A0 -> GND (I2C addr 0x40)
_add("VBAT_MAIN_OUT", "U6", 12)  # IN+1 ch1 (main battery, upstream of RSH1)
_add("VBAT_BUS", "U6", 11)       # IN-1 ch1 (downstream of RSH1, merged bus)
_add("VBAT_P1_OUT", "U6", 15)    # IN+2 ch2 (Terra P1, upstream of RSH2)
_add("VBAT_BUS", "U6", 14)       # IN-2 ch2 (downstream of RSH2, merged bus)
_add("5V0_PRE", "U6", 2)         # IN+3 ch3 (+5V0 CM4 rail, upstream of RSH3)
_add("+5V0", "U6", 1)            # IN-3 ch3 (downstream of RSH3)
_add("+3V3", "U6", 16)           # VPU (open-drain alarm pull-up supply)
# U6 pins 8 (WARNING), 9 (CRITICAL), 10 (PV), 13 (TC), 17 (EP) intentionally
# unconnected in Rev A (no consumer for hardware alarm flags yet) --
# no-connect flagged by the schematic generator.

# --- Dock + BQ25792 charger (U3): dock -> charges BATT_F (main pack) ----------
_add("DOCK_PWR_RAW", "J4", 1)
_add("GND", "J4", 2)
_add("GPIO_DOCK_DET", "J4", 3)     # shorted to GND by dock contact when seated
_add("+3V3", "R5", 1)
_add("GPIO_DOCK_DET", "R5", 2)
_add("DOCK_PWR_RAW", "F3", 1)
_add("DOCK_F", "F3", 2)
_add("DOCK_OK", "D3", 1)     # Schottky cathode (downstream, protected side)
_add("DOCK_F", "D3", 2)      # anode (upstream, raw dock input) -- forward-conducts DOCK_F -> DOCK_OK
_add("DOCK_OK", "D4", 1)
_add("GND", "D4", 2)
_add("DOCK_OK", "C7", 1)
_add("GND", "C7", 2)
_add("DOCK_OK", "U3", 1)     # VAC1 charger input
_add("GND", "U3", 2)
_add("CHG_SW", "U3", 3)
_add("CHG_SW", "L2", 1)
_add("BATT_F", "L2", 2)       # charges the main battery node, upstream of the Q1 ORing FET
_add("BATT_F", "C8", 1)
_add("GND", "C8", 2)
_add("+3V3", "C9", 1)
_add("GND", "C9", 2)
_add("+3V3", "C10", 1)
_add("GND", "C10", 2)
_add("+3V3", "U3", 4)         # I2C/logic supply
_add("I2C0_SDA", "U3", 5)
_add("I2C0_SCL", "U3", 6)
_add("PROG", "U3", 7)
_add("PROG", "R3", 1)
_add("GND", "R3", 2)
_add("GND", "U3", 8)          # thermal pad / PGND

# --- CM4 decoupling / boot straps ---------------------------------------------
for _c in ("C11", "C12", "C13", "C14", "C15"):
    _add("+5V0", _c, 1)
    _add("GND", _c, 2)

_add("nRPIBOOT", "SW1", 1); _add("GND", "SW1", 2)
_add("+3V3", "R7", 1); _add("nRPIBOOT", "R7", 2)
_add("RUN_PG_N", "SW2", 1); _add("GND", "SW2", 2)
_add("+3V3", "R8", 1); _add("RUN_PG_N", "R8", 2)
_add("+3V3", "R9", 1); _add("EEPROM_nWP", "R9", 2)

_add("GND", "J10", 1)
_add("+3V3", "J10", 2)
_add("UART3_TXD", "J10", 3)
_add("UART3_RXD", "J10", 4)
_add("nRPIBOOT", "J10", 5)
_add("RUN_PG_N", "J10", 6)

# --- FC / GNSS / ELRS / TOF connectors -----------------------------------------
_add("GND", "J5", 1); _add("+5V0", "J5", 2)
_add("UART0_TXD0", "J5", 3); _add("UART0_RXD0", "J5", 4)
_add("GPIO_FC_RESET", "J5", 5); _add("GPIO_FC_AUX", "J5", 6)

_add("GND", "J6", 1); _add("+5V0", "J6", 2)
_add("UART1_RXD1", "J6", 3)     # GNSS TX -> CM4 RX
_add("UART1_TXD1", "J6", 4)     # CM4 TX -> GNSS RX
_add("GPIO_GNSS_PPS", "J6", 5)
# J_GNSS pin 6: reserved, NC

_add("GND", "J7", 1); _add("+3V3", "J7", 2)
_add("UART2_RXD", "J7", 3)      # ELRS TX -> CM4 RX
_add("UART2_TXD", "J7", 4)      # CM4 TX -> ELRS RX

_add("GND", "J8", 1); _add("+3V3", "J8", 2)
_add("I2C0_SDA", "J8", 3); _add("I2C0_SCL", "J8", 4)
_add("GPIO_TOF_INT", "J8", 5)

_add("+3V3", "R10", 1); _add("I2C0_SDA", "R10", 2)
_add("+3V3", "R11", 1); _add("I2C0_SCL", "R11", 2)
_add("+3V3", "R12", 1); _add("I2C1_SDA", "R12", 2)
_add("+3V3", "R13", 1); _add("I2C1_SCL", "R13", 2)

_add("+3V3", "JP1", 1)      # default bridge 1-2: XSHUT free-run, pulled high
_add("XSHUT", "JP1", 2)
# JP1 pin 3 (alternative: bridge 2-3 for future CM4 GPIO control of XSHUT) is
# intentionally reserved/unpopulated in Rev A -- no-connect flagged, not wired
# to a CM4 pin, per docs/assumptions.md #6.
_add("+3V3", "R15", 1); _add("XSHUT", "R15", 2)

# --- Terra connector -------------------------------------------------------------
_add("+5V0", "F4", 1)
_add("TERRA_PWR", "F4", 2)
_add("TERRA_PWR", "J9", 1)
_add("GND", "J9", 2)
_add("GND", "J9", 3)
_add("I2C1_SDA", "J9", 4)
_add("I2C1_SCL", "J9", 5)
_add("SPI0_SCLK", "J9", 6)
_add("SPI0_MOSI", "J9", 7)
_add("SPI0_MISO", "J9", 8)
_add("SPI0_CE0_N", "J9", 9)
_add("UART4_TXD", "J9", 10)
_add("UART4_RXD", "J9", 11)
_add("USB2_0_DP", "J9", 12)
_add("USB2_0_DN", "J9", 13)
_add("GPIO_TERRA_A", "J9", 14)
_add("GPIO_TERRA_B", "J9", 15)
_add("GPIO_TERRA_IRQ", "J9", 16)
_add("GPIO_TERRA_TRIG", "J9", 17)
_add("TERRA_PRESENCE_N", "J9", 18)
_add("GND", "J9", 19)
_add("TERRA_PWR", "J9", 20)
_add("+3V3", "R14", 1); _add("TERRA_PRESENCE_N", "R14", 2)

# --- Status LED --------------------------------------------------------------------
_add("GPIO_STATUS_LED", "R6", 1)
_add("LED_A", "R6", 2)
_add("LED_A", "LED1", 1)
_add("GND", "LED1", 2)

# --- Test points ---------------------------------------------------------------------
_add("VBAT_BUS", "TP1", 1)
_add("+5V0", "TP2", 1)
_add("+3V3", "TP3", 1)
_add("GND", "TP4", 1)

# ---------------------------------------------------------------------------
# UART2_TXD/UART2_RXD are shared between the CM4 (J1 pins 17/18) and both the
# ELRS connector: this is a single logical UART with one attachment point,
# no fan-out conflict (Device tree/init selects the ELRS UART peripheral).
#
# net UART cross-checks and single-consumer validation are performed by
# validate.py against this module before schematic/PCB generation runs.
# ---------------------------------------------------------------------------

ALL_REFS = {c.ref for c in COMPONENTS}
