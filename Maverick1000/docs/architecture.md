# Maverick 1000 — SKYWARD-COMPUTE-CARRIER
## System Architecture — Rev A

**Company:** Frontier Robotics
**Product:** Maverick 1000 (internal codename: SKYWARD)
**Board:** SKYWARD-COMPUTE-CARRIER, Rev A
**Date:** 2026-09-21

---

## 1. Mission Context

Maverick 1000 is a <=250 g autonomous aerial robotics platform (not a racing
drone) built around a swappable sensing payload family ("Terra"), autonomous
navigation/mapping, obstacle avoidance, and autonomous dock-based recharging.

Mass budget:

| Item | Mass |
|---|---|
| Base aircraft (airframe, propulsion, avionics, FC, battery) | <= 185 g |
| Terra payload (any single module) | <= 65 g |
| **Total MTOW** | **<= 250 g** |

The Terra payload occupies the 65 g slot — it is never additive to 250 g.

Endurance requirement (hard): **>= 30 minutes** flight time with any normal
Terra payload installed. Engineering target: **> 30 minutes with margin**
(see `power_architecture.md` §6 for the energy budget that drives this).
Terra P1 (auxiliary energy payload) exists specifically to guarantee this
requirement is met even with a payload that has no energy-generation value
of its own (L1/V1/T1).

## 2. Compute / Control Split

Two independent compute domains, deliberately not merged:

- **Raspberry Pi CM4** (Linux, high-level autonomy): navigation, mapping,
  3D reconstruction, point-cloud processing, computer vision, path planning,
  Terra payload communications, telemetry, logging, docking logic.
- **Dedicated flight controller** (Toothpick-class F4 AIO, real-time):
  stabilization, IMU, motor control, failsafes.

The CM4 talks to the FC as a companion computer over UART (MSP/MAVLink-class
telemetry + command link), the same pattern used in every serious
Pi/Jetson-companion-computer autonomy stack. **If the CM4 hangs or reboots,
the FC continues stabilized flight independently** — this is a hard
requirement and is why the FC is not derived from, or dependent on, the CM4
in any way (separate power sequencing, separate reset domains, no shared
boot dependency).

## 3. Board Scope

SKYWARD-COMPUTE-CARRIER is the **central avionics/compute board** of the
airframe. It is not the flight controller and not the ESC — those functions
are provided by the existing Toothpick F4 AIO board, connected to this
board over a dedicated harness. This board provides:

1. CM4 socket + supporting circuitry (power, boot straps, debug)
2. Power architecture: main battery input, Terra P1 auxiliary battery input,
   power-path management, regulated rails, telemetry
3. FC interface (UART command/telemetry link)
4. GNSS interface (BN-220, UART + PPS)
5. VL53L5CX short-range spatial ToF sensor (permanently installed, I2C)
6. ELRS receiver interface (UART)
7. Standardized Terra payload interface (power, I2C, SPI, USB2 HS,
   GPIO, IRQ, trigger/sync, presence-detect -- no dedicated UART, see
   `CM4_PIN_VERIFICATION.md`: the CM4 only has 3 UART instances free of
   I2C0/SPI0 conflicts, all used by FC/GNSS/ELRS)
8. Dock/charging interface (3-contact skid interface -> onboard charger IC)
9. Debug/console header

## 4. Key Design Decisions & Rationale

| Decision | Rationale |
|---|---|
| CM4 (eMMC variant, not Lite) | No microSD holder/card mass or vibration-induced contact risk; higher reliability for a flying vehicle. Revisable: swap footprint-compatible Lite variant if cost/flexibility outweighs this. |
| Terra high-bandwidth channel = CM4 USB2 HS (480 Mb/s), not MIPI CSI-2 | CSI-2 would require exposing CM4 J2 MIPI diff pairs through a payload-bay connector with controlled-impedance flex routing across a mechanical mating interface — high risk, high routing cost, and CM4 J2 CSI lanes are not designed to be extended through a second board-to-board hop. USB2 480 Mb/s is ample for compressed LiDAR point-cloud streams, thermal frames, and compressed/raw stills from Terra V1/L1/T1, and is a mechanically simple 2-wire diff pair. PCIe/CSI is left as a documented future option (Rev B) if a Terra module needs more bandwidth than USB2 HS can provide. |
| Terra module identification over I2C (module-resident ID EEPROM, HAT-ID-EEPROM pattern) + a dedicated presence-detect pin | I2C ID EEPROM is the established, low-pin-count way to self-describe a plug-in module (same approach as Raspberry Pi HATs). The extra presence-detect pin lets the CM4 (or even just analog wake logic) know *something* is seated before I2C enumeration, without adding a second protocol. |
| No PCIe/NVMe in Rev A | Not required for any stated requirement; saves connector count, routing complexity and mass. All storage lives on the CM4 eMMC module. Documented as a Rev B option if local high-speed logging storage becomes necessary. |
| Logic domain: 3.3 V everywhere | CM4 GPIO, FC UART, ELRS RX UART, BN-220 UART and VL53L5CX I2C are all natively 3.3 V — no level shifting required anywhere in the signal chain, minimizing part count/mass/failure points. |
| Battery power-path: ideal-diode ORing (not raw parallel) | Main battery and Terra P1 battery are independently protected and ORed onto a common aircraft power bus so a fault or full discharge on one pack cannot back-feed or short into the other. See `power_architecture.md`. |
| Dock charges the main pack only; P1 is charged off-aircraft | Avoids a second, more complex bidirectional-charge power path through the same ORing junction (an ideal-diode ORing FET blocks reverse current by design — it cannot also serve as a charge path). Terra P1 is swappable exactly like L1/V1/T1 and is charged in a bench charger/bay between flights, consistent with normal multi-battery multirotor operating practice. |
| Only 3 CM4 UARTs used (FC, GNSS, ELRS); debug console shares the FC UART; Terra's UART dropped | The BCM2711 has 5 PL011 UART instances, but UART2 shares GPIO0/1 with I2C0 and UART4 shares GPIO8/9 with SPI0, both of which this design needs concurrently -- verified against the official `raspberrypi/linux` kernel device tree, see `CM4_PIN_VERIFICATION.md`. Only 3 UARTs are actually free of conflicts. This replaced an earlier draft that incorrectly assumed 5 independent UARTs were available. |
| 4-layer, 1.0 mm FR4 | 4 layers is sufficient for CM4 fan-out (single-ended, no true high-speed diff pairs routed in Rev A) plus solid GND/power planes; thinner-than-standard 1.0 mm core saves board mass vs. the 1.6 mm default at negligible mechanical cost for a board this size, mounted on 4 standoffs. |
| Motor power (main battery high current) does **not** route through this board | The FC/ESC AIO board takes battery power directly via its own XT30-class pads, as in the existing prototype. This board only taps a low-current (<=4 A) copy of the same battery rail for CM4/peripheral regulation. Keeps high-current, high-di/dt traces off the compute board entirely — good for both EMI (GNSS/RF nearby) and mass (no heavy copper needed for motor current). |

## 5. Interfaces Provided (by design, not "everything possible")

| Interface | Connector | Why it exists |
|---|---|---|
| CM4 | 2x Hirose DF40C-100DS-0.4V | Mandatory — module footprint |
| FC | 6-pin JST-GH 1.25 mm | UART telemetry/command link to Toothpick F4 |
| GNSS | 6-pin JST-GH 1.25 mm | BN-220 UART + PPS + power |
| ELRS RX | 4-pin JST-GH 1.25 mm | UART control/telemetry link |
| VL53L5CX | 5-pin JST-GH 1.0 mm (SATEL-style) | Permanently-installed short-range ToF, I2C |
| Terra payload | 22-pin Hirose DF13-22DP-1.25 mm | Standardized payload bus (see `connector_pinouts.md`) |
| Battery in | 2-pin JST-GH 1.25 mm (low-current tap) | 4S LiHV main pack tap for avionics power |
| Dock/charge | 3-pin JST-GH 1.25 mm (routed to skid pads) | Autonomous dock charging + presence detect |
| Debug | 6-pin 2.54 mm header | CM4 UART console, boot-mode strap, 3V3, GND |

Full pin-by-pin tables are in `connector_pinouts.md`.

## 6. Known Assumptions (see also `assumptions.md`)

The single highest-risk assumption in this design is flagged here and
repeated in the final report: **exact CM4 J1/J2 pin-number assignments in
the schematic are drawn from the engineer's working knowledge of the
published Raspberry Pi CM4 pinout and must be verified pin-by-pin against
the official Raspberry Pi CM4 Datasheet before this board is fabricated.**
Outbound network access to `datasheets.raspberrypi.com` was blocked in this
build environment, so the exact datasheet could not be re-verified live.
Every CM4 net in the schematic is labeled with the signal's functional name
so this check is a straightforward datasheet cross-reference, not a redesign.
