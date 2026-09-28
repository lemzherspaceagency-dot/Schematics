# Programming, Debug, and Recovery Guide — SKYWARD-COMPUTE-CARRIER Rev A

This document exists because the brief for this pass was explicit: **"I
need to be able to connect the assembled board to my ThinkPad and
program/debug it. Treat this as a required design feature, not an
optional future improvement."** Every interface below is verified against
the actual schematic/PCB net list in `python/design_data.py`, not just
described in prose — pin numbers and net names here are the real ones on
the board, cross-checked the same way every other connection in this
project has been (see `verification/netlist_cross_check_output.txt`).

## 0. Summary table

| Interface | Connector | Status |
|---|---|---|
| CM4 serial console | J10 (pins 3/4, shared design with J5/FC — see below) | **Implemented, verified** |
| CM4 boot-mode control (nRPIBOOT) | SW1 tactile switch, also broken out on J10 pin 5 | **Implemented, verified** |
| CM4 reset (RUN_PG) | SW2 tactile switch, also broken out on J10 pin 6 | **Implemented, verified** |
| CM4 USB boot-mode DATA path (required for `rpiboot` eMMC programming) | — | **Was missing — a real, board-level gap found and fixed this pass. See §2.** |
| Board power-rail test points | TP1 (VBAT_BUS), TP2 (+5V0), TP3 (+3V3), TP4 (GND) | **Implemented** |
| RP2040 programming/debug | — | **N/A — this design contains no RP2040.** See §4. |

## 1. Serial console (UART debug)

- **Connector**: J10, a 6-pin 2.54 mm header, "DEBUG" silkscreen label,
  located in the CM4 support component group on the top side of the
  board (see `manufacturing/previews/top_composite.png`).
- **Pinout** (J10, pin 1 nearest the silkscreen dot):

  | Pin | Signal | Notes |
  |---|---|---|
  | 1 | GND | |
  | 2 | +3V3 | **Do not use to power a USB-serial adapter that also has its own supply** — this is CM4's own 3V3 rail, provided so a 3-wire (GND/TX/RX)-only adapter can sense logic level, not to be back-fed. |
  | 3 | UART0_TXD0 (CM4 TX, board perspective) | 3.3 V logic level |
  | 4 | UART0_RXD0 (CM4 RX, board perspective) | 3.3 V logic level |
  | 5 | nRPIBOOT | Same net as SW1 — see §2 |
  | 6 | RUN_PG | Same net as SW2 — see §2 |

- **Voltage levels**: strictly 3.3 V CMOS logic, direct from the CM4's
  own PL011 UART0 peripheral pins (J1 pins 51/55 — see
  `docs/CM4_PIN_VERIFICATION.md`). **Do not connect a 5 V-logic USB-serial
  adapter directly** — use a 3.3 V-only adapter (e.g. an FTDI-class
  adapter with a 3.3 V I/O jumper/variant, or any adapter explicitly
  rated for 3.3 V logic). This satisfies the brief's explicit "do not
  expose 5V UART signals to CM4 GPIO" requirement — no 5 V signal is
  present on this header at all (pin 2 is 3V3, not 5V0).
- **Required cable/adapter**: any 3.3 V USB-to-UART adapter (FTDI FT232R/
  232H, CP2102, CH340 3.3V-configured, etc.) with 3 flying leads to
  GND/TX/RX. Connect adapter TX -> J10 pin 4 (CM4 RX), adapter RX -> J10
  pin 3 (CM4 TX), adapter GND -> J10 pin 1. **Do not connect the
  adapter's own +5V or +3V3 output to J10 pin 2** unless the adapter is
  specifically a level-sense-only, unpowered-output type — the board
  already supplies 3V3 there.
- **Host-side tool**: any serial terminal (`screen /dev/ttyUSB0 115200`,
  `minicom`, PuTTY, etc.) at 115200 8N1, the standard Raspberry Pi OS
  console baud rate.
- **Verifying a successful connection**: power the board (or press SW2 to
  reset the CM4 with the adapter already connected) and watch for Linux
  kernel boot messages on the terminal. No output at all usually means a
  swapped TX/RX pair (try swapping) or wrong baud rate; garbled output
  means a baud-rate or voltage-level mismatch.
- **Known limitation, not new to this pass, carried forward from the
  original design**: **J10 shares its UART0 pins with J5 (the flight
  controller connector) at the CM4 hardware level** — the BCM2711 SoC on
  this module only exposes 3 independent UART instances free of I2C0/SPI0
  pin conflicts (see `docs/CM4_PIN_VERIFICATION.md`), and this design
  uses all 3 for FC/GNSS/ELRS, leaving none free to dedicate solely to
  debug. **Do not connect a debug UART adapter to J10 while the flight
  controller is also connected to J5** — both are wired to the exact same
  CM4 pins, and driving both simultaneously will contend on the bus. This
  is a genuine, documented hardware constraint of this board revision,
  not an oversight; a future revision could add a UART mux (the same
  pattern used to fix the USB boot-mode gap in §2) if simultaneous FC +
  debug-console access is required.

## 2. CM4 USB boot mode / `rpiboot` (eMMC programming and OS recovery)

### The gap this pass found, and why it mattered

The CM4's SoC (BCM2711) has exactly **one** USB2.0 OTG-capable interface,
exposed on J2 pins 3/5 (`CM4_USB_DM`/`CM4_USB_DP`). Before this pass, the
comms-subsystem integration wired those two pins **directly and
exclusively** to U7 (the USB2512B hub)'s upstream port, so the hub could
fan the CM4's single USB port out to the EC25 modem and the Terra
high-bandwidth channel. That is correct for **normal Linux operation**
(CM4 boots, acts as USB host, the hub and its downstream devices enumerate
normally) — but it silently broke `rpiboot`-based programming: when the
CM4's SoC boot ROM is put into USB device/boot mode (by holding
`nRPIBOOT` low through power-on), it needs to present itself as a USB
**device** directly to an external host (a PC). With the OTG pins
permanently wired only to the hub's upstream (device-facing) port, and no
other physical path out to a connector, **there was no way for an
external host to ever see the CM4 in this mode** — the hub sits
electrically in the way in exactly the wrong direction, and neither of
the hub's downstream ports (wired to the onboard EC25 modem and the Terra
connector, not to any host-facing connector) provides an alternative
path either.

This is exactly the failure mode the brief warned about explicitly:
*"Verify actual CM4 USB device-mode path and the effect of the USB2512B
hub — do not assume the hub automatically supports CM4 programming."* It
did not, and this was a real, board-level, fabrication-relevant gap, not
a documentation gap — fixed by adding hardware, not by editing prose.

### The fix

A USB 2.0 SPDT (single-pole, double-throw) analog switch, **U10**, was
added between the CM4's OTG pins and two destinations:

- **Throw 1** (normal operation): U7's upstream port, exactly as before.
- **Throw 2** (boot/recovery mode): a new external-facing connector,
  **J15**, a USB Micro-B receptacle wired using KiCad's real, stock
  `Connector:USB_B_Micro` symbol and a real stock footprint (the same
  "use a maintained stock KiCad library part" verification tier already
  used for J12/U7 elsewhere in this project — see
  `docs/COMPONENT_FOOTPRINT_VERIFICATION_CHECKLIST.md`).

The switch's select line is tied to the **same `nRPIBOOT` net** SW1/J10
pin 5 already use — no new control signal, no new GPIO, no separate
jumper to remember to move. Holding `nRPIBOOT` low (SW1 pressed, or an
external controller driving J10 pin 5 low) simultaneously (a) tells the
CM4's boot ROM to enter USB device/boot mode, and (b) switches U10 to
connect CM4's OTG pins straight out to J15, so a host plugged into J15
sees the CM4 directly the moment its boot ROM starts advertising itself.
Releasing `nRPIBOOT` returns the mux to the hub path for normal operation.
This is a real, standard pattern used on other open-source CM4 carrier
designs that also need to share the CM4's single OTG port with onboard
USB peripherals — not a novel or unverified topology.

See `docs/USB_MUX_VERIFICATION.md` for the exact part chosen, its real
pinout and source, and why.

### How to actually program the eMMC from a ThinkPad

1. Install `rpiboot` on the host (`apt install rpiboot` on Debian/Ubuntu-
   family Linux, or build from `raspberrypi/usbboot` — this is Raspberry
   Pi's own official tool, not a third-party or invented one).
2. With the board **unpowered**, connect a USB-A-to-Micro-B cable from
   the ThinkPad to **J15**.
3. Press and hold **SW1** (nRPIBOOT).
4. Apply power to the board (or, if already powered, press and hold SW1
   first, then press **SW2** to reset the CM4 while continuing to hold
   SW1).
5. Release SW1 after ~2 seconds.
6. On the host, run `sudo rpiboot`. The CM4 should enumerate as a USB
   device (`lsusb` will show a Broadcom/Raspberry Pi boot-mode VID:PID
   briefly, then the eMMC as a USB mass-storage device once `rpiboot`
   loads the second-stage bootcode).
7. Once enumerated as mass storage, the eMMC can be flashed with the
   normal Raspberry Pi OS imaging tools (`rpi-imager`, `dd`, etc.) exactly
   as with any USB-attached storage device.
8. Disconnect J15 and power-cycle the board (without holding SW1) to boot
   normally from the freshly-flashed eMMC.

### Verifying success

`lsusb` (or Windows Device Manager / macOS System Report) showing a
Raspberry Pi boot-mode or mass-storage device appear within a few seconds
of step 6 confirms the mux and wiring are working. No device appearing at
all most commonly means SW1 was not held through the power/reset event
(step 3-5 timing), a bad/charge-only USB cable at J15, or (if this
recurs after physical rework) a mux/connector solder-joint issue — since
this is new hardware added this pass, it is a candidate for `docs/`
follow-up bring-up testing on the first assembled unit, exactly as noted
in the fabrication-readiness section of this guide.

### Limitations / prerequisites

- Requires the `nRPIBOOT`-to-mux-select wiring to be intact — see
  `docs/USB_MUX_VERIFICATION.md` for the exact signal path.
- J15 provides data only in this design (VBUS/ID left unconnected — the
  board is self-powered, so no accidental back-feed risk from a host's
  5 V rail, and ID is correctly left floating for a device-side Micro-B
  receptacle per the USB spec).
- Only one of {hub path, J15 path} is active at a time by design (that is
  the entire point of the mux) — do not expect U7's downstream devices
  (EC25, Terra) to be reachable while nRPIBOOT is held low.

## 3. Board-level service access (test points, reset, boot)

| Test point | Net | Purpose |
|---|---|---|
| TP1 | VBAT_BUS | Merged main+secondary battery bus, post-ORing |
| TP2 | +5V0 | Main 5 V rail (post TPS5430 buck) |
| TP3 | +3V3 | Main 3.3 V logic rail (post AP2112K LDO) |
| TP4 | GND | Ground reference |

All 4 are bare `TestPoint_Pad_D1.5mm` pads (see
`manufacturing/stackup_and_fab_notes.md`), usable directly with a
multimeter probe or a pogo-pin bed-of-nails bring-up fixture — no
additional connector or adapter required. Boot/reset control (SW1/SW2)
and CM4 status/register access are already covered in §§1-2 above; no
separate header is needed for those since J10 already exposes both.

## 4. RP2040

**This design contains no RP2040.** A repository-wide search (`grep -ril
rp2040`, case-insensitive, across every file in this project) confirms
zero references, in schematic, PCB, `design_data.py`, or any
documentation file. The brief's "do not turn the RP2040 into the flight
controller" constraint refers to the separate, dedicated flight
controller board (the FC connector, J5, on this carrier — a distinct
physical board handling real-time stabilization, outside the scope of
SKYWARD-COMPUTE-CARRIER itself), not to any component on this PCB. Phase
4.C of the completion-pass brief ("if the RP2040 remains in the design,
provide/verify its programming/recovery path") is therefore not
applicable to this board — there is no RP2040-specific programming
interface to add, verify, or omit.
