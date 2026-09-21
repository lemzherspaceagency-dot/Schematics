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
    Component("J1", "SKYWARD_Custom:CM4_Connector_100_J1", "SKYWARD_Custom:Hirose_DF40C-100DS-0.4V",
               "CM4_J1", "DF40C-100DS-0.4V(51)", "Hirose Electric",
               "100-pos 0.4mm SMD receptacle, CM4 primary connector (low/med-speed IO + power)",
               group="cm4", footprint_group="cm4conn"),
    Component("J2", "SKYWARD_Custom:CM4_Connector_100_J2", "SKYWARD_Custom:Hirose_DF40C-100DS-0.4V",
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
               "10k", "RC0402FR-0710KL", "Yageo", "RUN_PG pull-up", group="cm4"),
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
    Component("U1", "SKYWARD_Custom:LM74610QDGKRQ1", "Package_SO:VSSOP-8_3.0x3.0mm_P0.65mm",
               "LM74610QDGKRQ1", "LM74610QDGKRQ1", "Texas Instruments",
               "Ideal-diode ORing controller, main battery", group="power", footprint_group="vssop8"),
    Component("Q1", "Device:Q_PMOS_GSD", "Package_TO_SOT_SMD:SOT-23",
               "DMP2305U-7", "DMP2305U-7", "Diodes Incorporated", "P-MOSFET, main battery ORing pass element",
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
    Component("U2", "SKYWARD_Custom:LM74610QDGKRQ1", "Package_SO:VSSOP-8_3.0x3.0mm_P0.65mm",
               "LM74610QDGKRQ1", "LM74610QDGKRQ1", "Texas Instruments",
               "Ideal-diode ORing controller, Terra P1", group="power", footprint_group="vssop8"),
    Component("Q2", "Device:Q_PMOS_GSD", "Package_TO_SOT_SMD:SOT-23",
               "DMP2305U-7", "DMP2305U-7", "Diodes Incorporated", "P-MOSFET, Terra P1 ORing pass element",
               group="power", footprint_group="sot23"),
    Component("C2", "Device:C", "Capacitor_SMD:C_1210_3225Metric",
               "22uF", "GRM32ER71V226KE15L", "Murata", "Terra P1 input bulk cap", group="power"),
    Component("C17", "Device:C", "Capacitor_SMD:C_0402_1005Metric",
               "100nF", "GRM155R71H104KE14D", "Murata", "U2 (LM74610) VCAP charge-pump cap", group="power"),

    # ---- Power: 5V buck (CM4 + Terra) --------------------------------------------
    # TPS5430DDA is a NON-synchronous buck (integrated high-side switch
    # only) -- confirmed during this audit pass by cross-referencing 6+
    # independent open-source TPS5430 designs on GitHub, every one of
    # which places an external Schottky catch diode (cathode->PH,
    # anode->GND) at the switch node; one described it explicitly as
    # "not optional and not a snubber -- carries the inductor current for
    # ~79% of every cycle". The pre-audit design had NO catch diode on
    # this net at all -- a genuine missing-component defect that would
    # have made this converter non-functional (or destroyed the IC via
    # switch-node negative voltage transients) if fabricated as-is. Fixed
    # below with D5. See docs/OTHER_COMPONENTS_VERIFICATION.md.
    Component("U4", "Regulator_Switching:TPS5430DDA", "Package_SO:TI_SO-PowerPAD-8_ThermalVias",
               "TPS5430DDA", "TPS5430DDA", "Texas Instruments", "3A non-sync buck, 5.5-36V in, adjustable -> set for +5V0",
               group="power", footprint_group="soic8"),
    Component("L1", "Device:L", "Inductor_SMD:L_Coilcraft_XAL4020-XXX",
               "10uH", "XAL4020-103MEB", "Coilcraft", "5V buck inductor", group="power", footprint_group="inductor"),
    Component("D5", "Device:D_Schottky", "Diode_SMD:D_SMA",
               "SS34", "SS34", "Onsemi", "5V buck catch diode (PH->GND, non-synchronous TPS5430 topology)", group="power"),
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
    # U3 + support: BQ25792 is a 29-pin WQFN 4-switch buck-boost charger --
    # NOT the simple 8-pin part modeled in the pre-audit Rev A. See
    # docs/BQ25792_VERIFICATION.md for the verified real pinout and the
    # single-input (VAC1-only) application circuit implemented below.
    Component("U3", "SKYWARD_Custom:BQ25792RQMR",
               "SKYWARD_Custom:QFN-29_L4.0-W4.0-P0.40-BQ25792RQMR",
               "BQ25792RQMR", "BQ25792RQMR", "Texas Instruments", "1-4S I2C buck-boost charger, dock -> main battery",
               group="power", footprint_group="qfn29"),
    Component("Q5", "Device:Q_PMOS_GSD", "Package_TO_SOT_SMD:SOT-23",
               "DMP2305U-7", "DMP2305U-7", "Diodes Incorporated",
               "BQ25792 input blocking FET, ACFET1 (back-to-back pair with Q6)",
               group="power", footprint_group="sot23"),
    Component("Q6", "Device:Q_PMOS_GSD", "Package_TO_SOT_SMD:SOT-23",
               "DMP2305U-7", "DMP2305U-7", "Diodes Incorporated",
               "BQ25792 input blocking FET, RBFET1 (back-to-back pair with Q5)",
               group="power", footprint_group="sot23"),
    Component("L2", "Device:L", "Inductor_SMD:L_Coilcraft_XAL4020-XXX",
               "2.2uH", "XAL4020-222MEB", "Coilcraft", "BQ25792 buck-boost inductor, SW1-SW2", group="power", footprint_group="inductor"),
    Component("C7", "Device:C", "Capacitor_SMD:C_0805_2012Metric",
               "10uF", "GRM21BR61H106KE43L", "Murata", "BQ25792 VBUS input cap", group="power"),
    Component("C8", "Device:C", "Capacitor_SMD:C_0805_2012Metric",
               "10uF", "GRM21BR61H106KE43L", "Murata", "BQ25792 SYS output cap", group="power"),
    Component("C9", "Device:C", "Capacitor_SMD:C_0603_1608Metric",
               "1uF", "GRM188R61A105KA61D", "Murata", "BQ25792 REGN (internal LDO) decoupling", group="power"),
    Component("C10", "Device:C", "Capacitor_SMD:C_0805_2012Metric",
               "10uF", "GRM21BR61H106KE43L", "Murata", "BQ25792 PMID decoupling", group="power"),
    Component("C21", "Device:C", "Capacitor_SMD:C_0805_2012Metric",
               "10uF", "GRM21BR61H106KE43L", "Murata", "BQ25792 BAT decoupling (at the charger, in addition to C1 at the ORing input)", group="power"),
    Component("C22", "Device:C", "Capacitor_SMD:C_0402_1005Metric",
               "100nF", "GRM155R71H103KA88D", "Murata", "BQ25792 BTST1 bootstrap cap -- HIGHEST-UNCERTAINTY connection on this board, see docs/BQ25792_VERIFICATION.md", group="power"),
    Component("R3", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "5.6k", "RC0402FR-075K6L", "Yageo", "BQ25792 ILIM_HIZ set resistor -- value TBD, confirm against datasheet equation", group="power"),
    Component("R16", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "5.6k", "RC0402FR-075K6L", "Yageo", "BQ25792 PROG resistor -- value TBD, confirm against datasheet equation", group="power"),
    Component("R17", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "10k", "RC0402FR-0710KL", "Yageo", "BQ25792 TS bias divider (upper) -- approximates room temp; replace with real NTC divider if the battery pack provides a thermistor lead", group="power"),
    Component("R18", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "10k", "RC0402FR-0710KL", "Yageo", "BQ25792 TS bias divider (lower)", group="power"),
    Component("R19", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "10", "RC0402FR-0710RL", "Yageo", "BQ25792 ACDRV1 gate series resistor (Q5/Q6)", group="power"),
    Component("R20", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "10k", "RC0402FR-0710KL", "Yageo", "BQ25792 QON pull-up (inactive default, no manual power button in Rev A)", group="power"),
    Component("R21", "Device:R", "Resistor_SMD:R_0402_1005Metric",
               "10k", "RC0402FR-0710KL", "Yageo", "BQ25792 INT open-drain pull-up", group="power"),
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
# VERIFIED against the official raspberrypi/linux kernel device tree
# (bcm2711-rpi-ds.dtsi, GPIO ALT-function pin muxing) and cross-checked
# pin-for-pin against multiple independent open-source CM4 carrier board
# projects (including a shipped commercial product, NabuCasa/yellow).
# See docs/CM4_PIN_VERIFICATION.md for the full source list and mapping
# table -- this replaces the earlier unverified pin assignment.
#
# Only 3 of the BCM2711's 5 PL011 UART instances are usable simultaneously
# with I2C0 and SPI0 (UART2 shares GPIO0/1 with I2C0; UART4 shares GPIO8/9
# with SPI0) -- this is a real hardware constraint, not a choice, and it is
# why this design has 3 CM4-side UARTs (FC, GNSS, ELRS), not 5. The debug
# console shares the FC UART0 pins (fanned to both connectors; don't mate
# both at once). Terra's dedicated UART was removed for the same reason --
# it keeps SPI0 + I2C1 + USB2 HS, which was always the primary Terra bus
# plan. Unlisted pins are NC (present in the footprint, not connected).
CM4_J1_PINS = {
    1: "GND", 2: "GND", 7: "GND", 8: "GND", 13: "GND", 14: "GND",
    20: "EEPROM_nWP",
    22: "GND", 23: "GND",
    25: "GPIO_TERRA_B", 26: "GPIO_TERRA_TRIG", 27: "GPIO_TERRA_A",
    28: "UART5_RXD5", 29: "GPIO_GNSS_PPS", 30: "GPIO_DOCK_DET", 31: "UART5_TXD5",
    32: "GND", 33: "GND",
    34: "UART3_RXD3",
    35: "I2C0_SCL", 36: "I2C0_SDA",
    37: "SPI0_UNUSED_CE1",  # GPIO7, not used (only CE0 needed) -- left NC
    38: "SPI0_SCLK", 39: "SPI0_CE0_N", 40: "SPI0_MISO",
    41: "SPI0_UNUSED_GPIO25",  # GPIO25, not used -- left NC
    42: "GND", 43: "GND",
    44: "SPI0_MOSI", 45: "GPIO_STATUS_LED", 46: "GPIO_FC_RESET", 47: "GPIO_FC_AUX",
    49: "GPIO_TERRA_IRQ", 50: "GPIO_TOF_INT", 51: "UART0_RXD0",
    52: "GND", 53: "GND",
    54: "UART3_TXD3", 55: "UART0_TXD0",
    59: "GND", 60: "GND",
    65: "GND", 66: "GND",
    71: "GND", 74: "GND",
    77: "+5V0", 79: "+5V0", 81: "+5V0", 83: "+5V0", 85: "+5V0", 87: "+5V0",
    24: "GPIO_CHG_INT",  # GPIO26, BQ25792 charge-fault interrupt
    92: "RUN_PG", 93: "nRPIBOOT",
    98: "GND", 99: "+3V3",  # GLOBAL_EN, tied high for normal always-enabled operation
}
CM4_J2_PINS = {
    1: "GND",  # USB_OTG_ID, tied to GND to force USB host mode (CM4 is host to Terra)
    3: "USB2_0_DN", 5: "USB2_0_DP",
    7: "GND", 8: "GND", 13: "GND", 14: "GND", 19: "GND", 20: "GND",
    25: "GND", 26: "GND",
}
# GPIO7 (CE1) and GPIO25 are unused SPI0-adjacent pins with no net purpose
# in this design; they get a real no-connect flag, not a fake net -- see
# the cleanup pass right after NETS is populated below.
_CM4_PLACEHOLDER_NETS = ("SPI0_UNUSED_CE1", "SPI0_UNUSED_GPIO25")

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
for _placeholder in _CM4_PLACEHOLDER_NETS:
    NETS.pop(_placeholder, None)  # real no-connect, not a fake single-pin net

# --- Power path: main battery -> ORing -> VBAT_BUS --------------------------
# Real LM74610QDGKRQ1 pin map (see gen_symbols.py, verified against 2
# independent sources -- docs/LM74610_VERIFICATION.md): 1 VCAPL, 2
# GATE_PULL_DOWN, 3 NC, 4 ANODE, 5 NC, 6 GATE_DRIVE, 7 VCAPH, 8 CATHODE.
# The chip has NO ground pin -- it floats, powered parasitically between
# ANODE and CATHODE -- and its charge-pump cap goes BETWEEN VCAPL/VCAPH,
# not to ground. This replaced an earlier, incorrect 6-pin SOT-23-6 model
# with an invented GND pin. GATE_PULL_DOWN is tied to the same node as
# GATE_DRIVE (documented assumption -- both pins are involved in gate
# control per the part's naming; not independently confirmed from primary
# datasheet text, see the verification doc).
#
# The instrumentation shunt (RSH1) sits downstream of Q1's drain, in series
# toward the merged VBAT_BUS node, so it reads main-battery branch current
# only, not the merged total.
_add("BATT_IN", "J3", 1)
_add("GND", "J3", 2)
_add("BATT_IN", "F1", 1)
_add("BATT_F", "F1", 2)
_add("BATT_F", "D1", 1)      # TVS
_add("GND", "D1", 2)
_add("BATT_F", "U1", 4)         # ANODE (battery/source side)
_add("VBAT_MAIN_OUT", "U1", 8)  # CATHODE (bus/drain side)
_add("Q1_GATE", "U1", 6)        # GATE_DRIVE
_add("Q1_GATE", "U1", 2)        # GATE_PULL_DOWN (tied with GATE_DRIVE, see note above)
_add("VCAP1_L", "U1", 1); _add("VCAP1_H", "U1", 7)  # VCAPL/VCAPH -- cap goes between these two
_add("VCAP1_L", "C16", 1); _add("VCAP1_H", "C16", 2)
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
_add("P1_F", "U2", 4)           # ANODE
_add("VBAT_P1_OUT", "U2", 8)    # CATHODE
_add("Q2_GATE", "U2", 6)        # GATE_DRIVE
_add("Q2_GATE", "U2", 2)        # GATE_PULL_DOWN
_add("VCAP2_L", "U2", 1); _add("VCAP2_H", "U2", 7)
_add("VCAP2_L", "C17", 1); _add("VCAP2_H", "C17", 2)
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
_add("5V0_SW", "D5", 1)         # catch diode cathode -> PH switch node
_add("GND", "D5", 2)            # catch diode anode -> GND (non-sync buck, see comment above)
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
# Real 29-pin BQ25792 single-input (VAC1-only) application circuit. Pin
# numbers per docs/BQ25792_VERIFICATION.md. VAC2 (the unused second input)
# is tied to GND per TI's documented convention for an unpopulated input;
# CE is tied to GND (always enabled); QON gets an inactive-default pull-up
# (no manual power button in Rev A); BATP is tied directly to the BAT node
# as a conservative default (its exact function was not independently
# confirmed from primary datasheet text -- see the verification doc).
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

# VAC1 sense (high-impedance, taps the input directly) + input blocking FET
# pair Q5 (ACFET1) / Q6 (RBFET1), gate-driven by ACDRV1 through R19, boot-
# strapped by C22. This FET pair + bootstrap network is the single
# highest-uncertainty analog circuit on this board -- see
# docs/BQ25792_VERIFICATION.md and docs/FINAL_DESIGN_AUDIT.md.
_add("DOCK_OK", "U3", 9)      # VAC1 (sense)
_add("DOCK_OK", "Q5", 2)      # Q5 source (P-FET, S per Device:Q_PMOS_GSD pin2)
_add("Q5_Q6_MID", "Q5", 3)    # Q5 drain
_add("Q5_Q6_MID", "Q6", 3)    # Q6 drain (back-to-back: drains tied)
_add("VBUS_IN", "Q6", 2)      # Q6 source -> BQ25792 VBUS pins
_add("ACDRV1_GATE", "U3", 11)  # ACDRV1
_add("ACDRV1_GATE", "R19", 1)
_add("GATE_DRIVE", "R19", 2)
_add("GATE_DRIVE", "Q5", 1)   # Q5 gate
_add("GATE_DRIVE", "Q6", 1)   # Q6 gate
_add("BTST1", "U3", 4)
_add("BTST1", "C22", 1)
_add("DOCK_OK", "C22", 2)     # bootstrap cap referenced to the input rail (see audit note)
_add("VBUS_IN", "U3", 2); _add("VBUS_IN", "U3", 3)   # VBUS (both pins)
_add("VBUS_IN", "C7", 1); _add("GND", "C7", 2)  # input cap sits after the blocking FETs, on VBUS_IN

# unused second input (VAC2) tied to GND per TI convention for an
# unpopulated input; ACDRV2/BTST2 left NC (no second FET pair populated)
_add("GND", "U3", 8)          # VAC2

# always-enabled, no manual power button in Rev A
_add("GND", "U3", 13)         # ~CE, active low -> always enabled
_add("+3V3", "R20", 1); _add("QON_N", "R20", 2)
_add("QON_N", "U3", 12)       # ~QON, pulled inactive-high (no button populated)

# I2C control/telemetry (shared bus with VL53L5CX/INA3221)
_add("I2C0_SCL", "U3", 14)
_add("I2C0_SDA", "U3", 15)

# charge-fault interrupt -> CM4 GPIO26
_add("+3V3", "R21", 1); _add("GPIO_CHG_INT", "R21", 2)
_add("GPIO_CHG_INT", "U3", 21)  # ~INT

# TS: fixed bias divider approximating room temperature (documented
# placeholder -- replace with the pack's real NTC divider if available)
_add("REGN", "U3", 5)
_add("REGN", "C9", 1); _add("GND", "C9", 2)
_add("REGN", "R17", 1)
_add("TS_BIAS", "R17", 2)
_add("TS_BIAS", "U3", 16)     # TS
_add("TS_BIAS", "R18", 1); _add("GND", "R18", 2)

# ILIM_HIZ and PROG set resistors -- values marked TBD in the BOM, see
# docs/BQ25792_VERIFICATION.md
_add("ILIM_SET", "U3", 17)
_add("ILIM_SET", "R3", 1); _add("GND", "R3", 2)
_add("PROG_SET", "U3", 20)
_add("PROG_SET", "R16", 1); _add("GND", "R16", 2)

# BATP tied directly to the BAT node (conservative default, see above)
_add("BATT_F", "U3", 18)      # BATP

# PMID intermediate bus decoupling
_add("PMID", "U3", 29)
_add("PMID", "C10", 1); _add("GND", "C10", 2)

# 4-switch buck-boost inductor, SW1<->SW2
_add("SW1", "U3", 28)
_add("SW2", "U3", 26)
_add("SW1", "L2", 1)
_add("SW2", "L2", 2)

# SYS (system output) and BAT (battery charge/discharge) -- SYS not used
# by this design (the aircraft power bus is sourced from the battery
# ORing network, not from the charger's SYS pin) so it is decoupled but
# otherwise left as a charger-internal node; BAT charges the main battery
# node, upstream of the Q1 ORing FET.
_add("SYS_NODE", "U3", 25)
_add("SYS_NODE", "C8", 1); _add("GND", "C8", 2)
_add("BATT_F", "U3", 22); _add("BATT_F", "U3", 23)   # BAT (both pins)
_add("BATT_F", "C21", 1); _add("GND", "C21", 2)

_add("GND", "U3", 27)         # GND pin
_add("GND", "U3", 30)         # EP (exposed pad) -- documented assumption, see gen_footprints.py

# --- CM4 decoupling / boot straps ---------------------------------------------
for _c in ("C11", "C12", "C13", "C14", "C15"):
    _add("+5V0", _c, 1)
    _add("GND", _c, 2)

_add("nRPIBOOT", "SW1", 1); _add("GND", "SW1", 2)
_add("+3V3", "R7", 1); _add("nRPIBOOT", "R7", 2)
_add("RUN_PG", "SW2", 1); _add("GND", "SW2", 2)
_add("+3V3", "R8", 1); _add("RUN_PG", "R8", 2)
_add("+3V3", "R9", 1); _add("EEPROM_nWP", "R9", 2)

# Debug header shares the FC UART0 pins (see docs/CM4_PIN_VERIFICATION.md --
# only 3 independent UARTs are available; don't mate a debug adapter and
# the FC at the same time).
_add("GND", "J10", 1)
_add("+3V3", "J10", 2)
_add("UART0_TXD0", "J10", 3)
_add("UART0_RXD0", "J10", 4)
_add("nRPIBOOT", "J10", 5)
_add("RUN_PG", "J10", 6)

# --- FC / GNSS / ELRS / TOF connectors -----------------------------------------
_add("GND", "J5", 1); _add("+5V0", "J5", 2)
_add("UART0_TXD0", "J5", 3); _add("UART0_RXD0", "J5", 4)
_add("GPIO_FC_RESET", "J5", 5); _add("GPIO_FC_AUX", "J5", 6)

_add("GND", "J6", 1); _add("+5V0", "J6", 2)
_add("UART3_RXD3", "J6", 3)     # GNSS TX -> CM4 RX
_add("UART3_TXD3", "J6", 4)     # CM4 TX -> GNSS RX
_add("GPIO_GNSS_PPS", "J6", 5)
# J_GNSS pin 6: reserved, NC

_add("GND", "J7", 1); _add("+3V3", "J7", 2)
_add("UART5_RXD5", "J7", 3)      # ELRS TX -> CM4 RX
_add("UART5_TXD5", "J7", 4)      # CM4 TX -> ELRS RX

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
# J9 pins 10/11 (originally a dedicated Terra UART) are reserved/NC in this
# revision -- the CM4 only has 3 UARTs free of I2C0/SPI0 pin conflicts, all
# allocated to FC/GNSS/ELRS. See docs/CM4_PIN_VERIFICATION.md.
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

ALL_REFS = {c.ref for c in COMPONENTS}
