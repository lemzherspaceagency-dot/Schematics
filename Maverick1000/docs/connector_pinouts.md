# Connector Pinouts — SKYWARD-COMPUTE-CARRIER Rev A

All logic is 3.3 V. Pin 1 is marked on silkscreen with a square pad and a
silkscreen dot/arrow on every connector.

## J_FC — Flight Controller interface (6-pin JST-GH, 1.25 mm)

| Pin | Signal | Description |
|---|---|---|
| 1 | GND | Common ground with FC |
| 2 | +5V0 | 5 V power to FC telemetry side (FC is otherwise self-powered from main battery — this is a logic-supply reference/backup tap, <=100 mA) |
| 3 | FC_UART_TX | CM4 UART TX -> FC RX (command/telemetry link) |
| 4 | FC_UART_RX | FC TX -> CM4 UART RX |
| 5 | FC_RESET_N | Open-drain, CM4 GPIO -> FC reset (optional; FC may leave NC) |
| 6 | FC_AUX | Spare/auxiliary GPIO (e.g. arm status or buzzer trigger), CM4 GPIO |

## J_GNSS — GNSS (BN-220) interface (6-pin JST-GH, 1.25 mm)

| Pin | Signal | Description |
|---|---|---|
| 1 | GND | |
| 2 | +5V0 | BN-220 accepts 3.3-5 V; 5 V used for margin |
| 3 | GNSS_UART_TX | BN-220 TX -> CM4 UART RX |
| 4 | GNSS_UART_RX | CM4 UART TX -> BN-220 RX (rarely used, config only) |
| 5 | GNSS_PPS | 1PPS timing pulse -> CM4 GPIO (time sync for sensor fusion) |
| 6 | NC | Reserved |

## J_ELRS — ELRS receiver interface (4-pin JST-GH, 1.25 mm)

| Pin | Signal | Description |
|---|---|---|
| 1 | GND | |
| 2 | +3V3 | ELRS RX power (most ELRS RX modules are 3.3-5 V tolerant; 3.3 V chosen to match logic domain and save an LDO tap) |
| 3 | ELRS_UART_TX | ELRS RX TX -> CM4 UART RX (telemetry/CRSF) |
| 4 | ELRS_UART_RX | CM4 UART TX -> ELRS RX RX (rarely used) |

Note: the ELRS UART pair also connects to the FC in the airframe-level
harness (both FC and CM4 can see RC link telemetry) — that cross-connect is
made in the aircraft wiring harness, not on this board, since the FC's own
receiver input is on the FC board itself. This board's `J_ELRS` is the
CM4-side telemetry/companion tap only.

## J_TOF — VL53L5CX interface (5-pin JST-GH, 1.0 mm, SATEL-style)

| Pin | Signal | Description |
|---|---|---|
| 1 | GND | |
| 2 | +3V3 | |
| 3 | TOF_SDA | I2C data (address 0x29 default) |
| 4 | TOF_SCL | I2C clock |
| 5 | TOF_INT_N | Interrupt output -> CM4 GPIO |

Connector part: JST SM05B-SRSS-TB (1.0mm pitch SH-series SMD horizontal).

Assumption: VL53L5CX is implemented as the ST **VL53L5CX-SATEL** satellite
module (factory-calibrated optical stack) connected by a short FPC/wire
pigtail, not a bare optical die reflowed directly onto this board — this is
the standard, manufacturable way to deploy this sensor and avoids optical
stack handling/calibration risk on a general PCB assembly line. `XSHUT`
(reset) is tied to a CM4 GPIO via a solder-jumper-selectable option
(default: tied to +3V3 through a pull-up, sensor free-running) — see
schematic note.

## J_TERRA — Terra payload interface (22-pin Hirose DF13-22DP, 1.25 mm)

| Pin | Signal | Description |
|---|---|---|
| 1 | TERRA_PWR | Regulated +5V0 **out** (carrier -> module), fused independently to 2 A. Used by L1/V1/T1-class sensing payloads. |
| 2 | GND | |
| 3 | GND | |
| 4 | TERRA_SDA | I2C data — module ID EEPROM + control |
| 5 | TERRA_SCL | I2C clock |
| 6 | TERRA_SCLK | SPI clock |
| 7 | TERRA_MOSI | SPI CM4 -> module |
| 8 | TERRA_MISO | SPI module -> CM4 |
| 9 | TERRA_CS_N | SPI chip select |
| 10 | *(reserved, NC)* | Originally planned as a dedicated Terra UART; removed -- the CM4 only has 3 UART instances free of I2C0/SPI0 pin conflicts, all allocated to FC/GNSS/ELRS. See `CM4_PIN_VERIFICATION.md`. |
| 11 | *(reserved, NC)* | See pin 10 |
| 12 | TERRA_USB_DP | USB2 HS data+ (high-bandwidth sensor stream, e.g. L1 point cloud, V1/T1 imagery) |
| 13 | TERRA_USB_DN | USB2 HS data- |
| 14 | TERRA_GPIO_A | General-purpose, module-defined (e.g. payload power-good out) |
| 15 | TERRA_GPIO_B | General-purpose, module-defined |
| 16 | TERRA_IRQ_N | Module -> CM4 interrupt |
| 17 | TERRA_TRIG | CM4 -> module trigger/strobe (synchronized capture) |
| 18 | TERRA_PRESENCE_N | Grounded on the module side; lets the carrier detect *something* is seated before I2C enumeration |
| 19 | GND | Return / USB shield reference |
| 20 | TERRA_PWR | Second power pin, shares current with pin 1 |
| 21 | TERRA_BATT_RAW | Raw battery **input** (module -> carrier), Terra P1 **only**. Feeds the P1 ideal-diode ORing input (`power_architecture.md` §2) — completely separate from the regulated `TERRA_PWR` rail so a battery payload never backfeeds a regulator output. L1/V1/T1 modules leave this NC. |
| 22 | TERRA_BATT_RAW | Second raw-battery pin, current-shared with pin 21 |

Every Terra module (L1/V1/T1/P1, and future modules) must present an I2C ID
EEPROM at a fixed address (0x50, 24xx-class, HAT-ID-EEPROM pattern) so the
CM4 can identify which module is attached before enabling
module-specific drivers/power sequencing. This is what lets the carrier
tell a P1 (battery-source) module apart from a sensing (power-sink) module
before anything is electrically live on `TERRA_BATT_RAW`.

## J_BATT — Main battery tap (2-pin JST-GH, 1.25 mm)

| Pin | Signal |
|---|---|
| 1 | BATT_IN (4S LiHV, 12.0-17.4 V) |
| 2 | GND |

Low-current tap only (<=4 A) — motor power is **not** carried by this
board or connector; it goes directly from the main pack to the FC/ESC AIO
board on its own high-current pads, per `architecture.md` §4.

## J_DOCK — Dock/charge interface (3-pin JST-GH, 1.25 mm, wired to skid pads)

| Pin | Signal | Description |
|---|---|---|
| 1 | DOCK_PWR+ | Raw charge input from dock CC/CV supply |
| 2 | DOCK_GND | |
| 3 | DOCK_DET_N | Pulled to +3V3 on the aircraft side; shorted to DOCK_GND by the dock contact when properly seated (simple, robust mechanical presence detect — no protocol needed over the skid contacts) |

## J_DEBUG — Debug/console header (6-pin, 2.54 mm)

| Pin | Signal | Description |
|---|---|---|
| 1 | GND | |
| 2 | +3V3 | (reference only, do not source significant current from FTDI-style adapters) |
| 3 | UART0_TXD0 | Shares the FC UART0 net (J1 pin 55) -- do not mate a debug adapter here while the FC is also connected to J_FC |
| 4 | UART0_RXD0 | Shares the FC UART0 net (J1 pin 51) -- see pin 3 |
| 5 | nRPIBOOT | Pull low at power-up to force CM4 USB boot/rpiboot mode (via onboard tactile button, header pin brought out in parallel for automated test jigs) |
| 6 | RUN_PG | Pull low to reset CM4 (onboard button + header pin) |

## CM4 module connectors (J1, J2 — Hirose DF40C-100DS-0.4V, 100-pin each)

**All 200 physical pads are present in the footprint** (required — this is
a fixed-pinout module connector). Only the subset of signals this board
actually uses are wired to nets in the schematic; the remainder are placed
as `NC` (no-connect flagged) pins in the symbol, which is standard practice
for a large fixed-pinout connector where a carrier board doesn't use every
signal (e.g., this board does not use HDMI, CSI/DSI, Ethernet RGMII, PCIe,
or the second SD interface — none of those are required by any stated
Maverick 1000 requirement).

**Pin numbers below are verified** — see `CM4_PIN_VERIFICATION.md` for the
full methodology and source list (the official `raspberrypi/linux` kernel
device tree for GPIO ALT-function assignments, cross-checked against a
shipped commercial CM4 product's open-source schematic and five further
independent open-source CM4 carrier board projects). This replaced an
earlier unverified pin assignment; **only 3 UART instances are actually
available** given the I2C0/SPI0 pin-sharing constraint (see that doc) —
FC, GNSS and ELRS each get one; the debug console shares the FC UART; a
previously-planned dedicated Terra UART was removed.

| Function | Net name(s) | J1/J2 pin(s) |
|---|---|---|
| Power (+5V0 in) | +5V0 | J1: 77, 79, 81, 83, 85, 87 |
| Ground | GND | J1: 1,2,7,8,13,14,22,23,32,33,42,43,52,53,59,60,65,66,71,74,98; J2: 1,7,8,13,14,19,20,25,26 |
| Module control | RUN_PG (J1:92), EEPROM_nWP (J1:20), nRPIBOOT (J1:93), GLOBAL_EN (J1:99, tied to +3V3) | see left |
| UART0 (-> FC + debug header) | UART0_TXD0 (J1:55), UART0_RXD0 (J1:51) | GPIO14/15 |
| UART3 (-> GNSS) | UART3_TXD3 (J1:54), UART3_RXD3 (J1:34) | GPIO4/5 |
| UART5 (-> ELRS) | UART5_TXD5 (J1:31), UART5_RXD5 (J1:28) | GPIO12/13 |
| I2C bus 0 (-> VL53L5CX, INA3221, BQ25792) | I2C0_SDA (J1:36), I2C0_SCL (J1:35) | GPIO0/1 |
| I2C bus 1 (-> Terra) | I2C1_SDA (J1:58), I2C1_SCL (J1:56) | GPIO2/3 |
| SPI0 (-> Terra) | SPI0_SCLK (J1:38), SPI0_MOSI (J1:44), SPI0_MISO (J1:40), SPI0_CE0_N (J1:39) | GPIO11/10/9/8 |
| USB2 OTG (-> Terra high-bandwidth) | USB2_0_DP (J2:5), USB2_0_DN (J2:3), ID (J2:1, tied GND for host mode) | — |
| GPIO (dock detect, PPS, IRQs, triggers, status LED, FC reset/aux) | GPIO_DOCK_DET (J1:30/GPIO6), GPIO_GNSS_PPS (J1:29/GPIO16), GPIO_TOF_INT (J1:50/GPIO17), GPIO_TERRA_IRQ (J1:49/GPIO18), GPIO_TERRA_TRIG (J1:26/GPIO19), GPIO_TERRA_A (J1:27/GPIO20), GPIO_TERRA_B (J1:25/GPIO21), GPIO_FC_RESET (J1:46/GPIO22), GPIO_FC_AUX (J1:47/GPIO23), GPIO_STATUS_LED (J1:45/GPIO24) | see left |

PCIe, USB3, HDMI0/1, CSI0/1, DSI0/1, Ethernet RGMII, and the second SD
interface are present on the physical connector (mostly on J2) but are
**not connected to anything on this board** in Rev A — left as documented
NC pins, easy to bring out in a Rev B if a future Terra module needs PCIe-
class bandwidth.
