# CM4 J1/J2 Pin Verification — Rev A (post-audit correction)

## Why this document exists

Rev A's first draft assigned CM4 J1/J2 pin numbers from the engineer's
recollection of the published pinout, explicitly flagged as unverified
(`docs/assumptions.md` #1). This document records the actual verification
performed and the corrected pin table now used in `python/design_data.py`.

**Direct access to `datasheets.raspberrypi.com` remains blocked** in this
build environment (confirmed again this session). Verification was instead
performed by cross-referencing **multiple independent sources that are
each individually reliable**, and accepting a pin assignment only where
they agree:

1. **`raspberrypi/linux`** (github.com/raspberrypi/linux) — the official
   Raspberry Pi Foundation Linux kernel source tree. This is the
   authoritative source for GPIO ALT-function pin muxing
   (`arch/arm/boot/dts/broadcom/bcm2711-rpi-ds.dtsi`): which physical GPIO
   number each UART/I2C/SPI instance uses. This is not a third-party
   guess — it is the device tree the Raspberry Pi Foundation ships and
   the kernel actually uses to configure the SoC.
2. **NabuCasa/yellow** (github.com/NabuCasa/yellow) — the open-source
   KiCad hardware design for **Home Assistant Yellow**, a real shipped
   commercial CM4-based product. Its `CM4.kicad_sch` embeds a complete,
   internally-consistent 200-pin CM4 symbol (pins 1-100 = J1, 101-200 =
   J2, confirmed by cross-referencing against the known J1
   low/medium-speed-IO vs. J2 high-speed/multimedia split).
3. **Five further independent open-source CM4 carrier board projects**
   (different authors, different projects, spanning several years):
   `jkiv/cm4-carriers`, `Twisted-Fields/acorn-robot-electronics`,
   `ShawnHymel/rpi-cm4-carrier-template`, `murexrobotics/electrical`,
   `PionixPublic/reference-hardware`, `dridri/bcflight` (itself a CM4-based
   flight controller/drone project), `KaiPereira/CM5-SODIMM-Carrier`. All
   of these **independently agree** that `EEPROM_nWP` = pin 20, `RUN_PG` =
   pin 92, `GLOBAL_EN` = pin 99, `nRPIBOOT` = pin 93. Seven unrelated
   projects converging on the same four non-obvious pin numbers is strong
   evidence they all correctly transcribed the real datasheet, not a
   coincidence.

This is a legitimate verification methodology (triangulating multiple
independent real-world implementations against the official kernel source
that actually drives the hardware), but it is **not** the same as reading
the primary Raspberry Pi datasheet PDF directly. It is recorded here as
such. Confidence is very high for every pin listed below (cross-source
agreement, several from a shipped commercial product and the official
kernel), but a final diff against the primary PDF is still recommended
before high-volume production, and is listed as a non-blocking residual
risk in `docs/FINAL_DESIGN_AUDIT.md`.

## Critical correction: BCM2711 UART budget

The original Rev A design assumed **five independent, freely available
UART instances** on the CM4 (UART0 for FC, and three more for GNSS/ELRS/
debug console, plus a fifth invented for Terra). This was wrong and has
been corrected.

The BCM2711 SoC provides UART0, UART2, UART3, UART4, UART5 (PL011) plus a
mini-UART, but their GPIO pin assignments **overlap** with I2C0, I2C1 and
SPI0 (verified directly from `bcm2711-rpi-ds.dtsi`):

| UART | GPIOs | Conflicts with |
|---|---|---|
| UART0 | 14, 15 | (none) |
| UART2 | 0, 1 | **I2C0** (ID EEPROM bus) |
| UART3 | 4, 5 | (none) |
| UART4 | 8, 9 | **SPI0** (CE0, MISO) |
| UART5 | 12, 13 | (none) |

This design needs I2C0 (VL53L5CX/INA3221/BQ25792) and SPI0 (Terra) at the
same time as multiple UARTs, which rules out UART2 and UART4. **Only
three independent, conflict-free UART channels are actually available**
(UART0, UART3, UART5), not five. The architecture is corrected
accordingly:

- **FC** -> UART0 (GPIO14/15) — also fanned out to the debug header, since
  in practice only one of {FC, a debug UART adapter} is plugged in at a
  time. Do not connect both simultaneously.
- **GNSS** -> UART3 (GPIO4/5)
- **ELRS** -> UART5 (GPIO12/13)
- **Terra's dedicated UART pins are removed.** Terra retains SPI0, I2C1,
  USB2 HS and GPIO/IRQ/trigger — a UART was a "nice to have" documented as
  low-priority relative to those three real buses, and there is no GPIO
  budget left to give it one without taking a conflict on I2C0 or SPI0.
  Terra connector pins 10/11 (previously `UART4_TXD`/`UART4_RXD`) are now
  explicitly reserved/NC.

## Verified pin table (functions actually used in this design)

All GPIO-to-ALT-function assignments verified against
`raspberrypi/linux` `bcm2711-rpi-ds.dtsi`. All physical pin numbers
verified against the NabuCasa/yellow CM4 symbol, cross-checked against
the independent-project consensus above for the four config-strap pins.

| Signal | GPIO | J1/J2 pin | Source |
|---|---|---|---|
| +5V0 (CM4 power in) | — | J1: 77, 79, 81, 83, 85, 87 | NabuCasa |
| GND (J1) | — | J1: 1, 2, 7, 8, 13, 14, 22, 23, 32, 33, 42, 43, 52, 53, 59, 60, 65, 66, 71, 74, 98 | NabuCasa |
| GND (J2, partial, near USB2) | — | J2: 7, 8, 13, 14, 19, 20, 25, 26 | NabuCasa |
| RUN_PG | — | J1: 92 | 7-project consensus |
| EEPROM_nWP | — | J1: 20 | 7-project consensus |
| nRPIBOOT | — | J1: 93 | 7-project consensus |
| GLOBAL_EN | — | J1: 99 | 7-project consensus |
| UART0 TXD0 (-> FC, debug) | GPIO14 | J1: 55 | kernel dtsi + NabuCasa |
| UART0 RXD0 (-> FC, debug) | GPIO15 | J1: 51 | kernel dtsi + NabuCasa |
| UART3 TXD3 (-> GNSS) | GPIO4 | J1: 54 | kernel dtsi + NabuCasa |
| UART3 RXD3 (-> GNSS) | GPIO5 | J1: 34 | kernel dtsi + NabuCasa |
| UART5 TXD5 (-> ELRS) | GPIO12 | J1: 31 | kernel dtsi + NabuCasa |
| UART5 RXD5 (-> ELRS) | GPIO13 | J1: 28 | kernel dtsi + NabuCasa |
| I2C0 SDA (ID_SD) | GPIO0 | J1: 36 | kernel dtsi + NabuCasa |
| I2C0 SCL (ID_SC) | GPIO1 | J1: 35 | kernel dtsi + NabuCasa |
| I2C1 SDA | GPIO2 | J1: 58 | kernel dtsi + NabuCasa |
| I2C1 SCL | GPIO3 | J1: 56 | kernel dtsi + NabuCasa |
| SPI0 SCLK | GPIO11 | J1: 38 | kernel dtsi + NabuCasa |
| SPI0 MOSI | GPIO10 | J1: 44 | kernel dtsi + NabuCasa |
| SPI0 MISO | GPIO9 | J1: 40 | kernel dtsi + NabuCasa |
| SPI0 CE0_N | GPIO8 | J1: 39 | kernel dtsi + NabuCasa |
| USB2 OTG D+ | — | J2: 5 | NabuCasa |
| USB2 OTG D- | — | J2: 3 | NabuCasa |
| USB2 OTG ID (tied GND, forces host mode) | — | J2: 1 | NabuCasa |
| GPIO_DOCK_DET | GPIO6 | J1: 30 | NabuCasa |
| GPIO_GNSS_PPS | GPIO16 | J1: 29 | NabuCasa |
| GPIO_TOF_INT | GPIO17 | J1: 50 | NabuCasa |
| GPIO_TERRA_IRQ | GPIO18 | J1: 49 | NabuCasa |
| GPIO_TERRA_TRIG | GPIO19 | J1: 26 | NabuCasa |
| GPIO_TERRA_A | GPIO20 | J1: 27 | NabuCasa |
| GPIO_TERRA_B | GPIO21 | J1: 25 | NabuCasa |
| GPIO_FC_RESET | GPIO22 | J1: 46 | NabuCasa |
| GPIO_FC_AUX | GPIO23 | J1: 47 | NabuCasa |
| GPIO_STATUS_LED | GPIO24 | J1: 45 | NabuCasa |

Every other J1/J2 pin (Ethernet, PCIe, HDMI0/1, CSI0/1, DSI0/1, second SD
interface, CM4_3.3V/1.8V internal rail outputs, WL/BT disable, analog
inputs, camera GPIO, activity LED, nEXTRST) is present in the connector
footprint (all 200 physical pads are real copper) but is **not connected**
to anything on this board, per the original Rev A scope — none of those
interfaces are required by any stated Maverick 1000 requirement.

## Remaining, explicitly non-blocking risk

This table was not checked against the primary Raspberry Pi CM4 Datasheet
PDF directly (network access blocked in this environment). It should be
diffed against that PDF once before committing to a production run —
see `docs/FINAL_DESIGN_AUDIT.md` item 4 / "items requiring physical
prototype validation". Given the strength of the cross-source agreement
(kernel source + a shipped commercial product + 5 independent hobbyist/
professional projects), this is assessed as **low probability of error**,
not an open question about the architecture.
