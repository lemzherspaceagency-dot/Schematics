# High-Bandwidth Communications Module — Engineering Decision

## Selected module

**Quectel EC25 series** (LTE Cat 4 module), verified against the specific
variant **EC25VFA-512-STD**, LCC (leadless chip carrier) package, 132
real, physically-present pins on a 1-144 numbering scheme with gaps
(pins 73-84 not populated on the real part).

**Manufacturer**: Quectel Wireless Solutions Co., Ltd.

Reference designator on this board: **U8**.

## Why this pinout is trusted

Unlike a datasheet PDF (not reachable from this sandboxed environment —
Quectel's own site returns a blocked connection here, same constraint
documented for other parts this session), this pinout was extracted
directly from a real, working KiCad symbol file
(`GSM-GPS-EC25VFA-512-STD.kicad_sym`) published in the `SPIRIT-org/SPIRIT`
open-hardware repository on GitHub (an avionics/robotics hardware org that
also supplied the real CM4/CM5 carrier reference used earlier in
`docs/CM4_PIN_VERIFICATION.md`). The symbol's own embedded metadata
states `"MF" = "Quectel"` and `"Description" = "Quectel EC25VFA-512-STD
is a series of 4G - LTE Cat 4 module optimized specially for M2M and IoT
applications."` — i.e. this is a real, deployed part, not an invented
one. All 132 pins were parsed programmatically (not hand-transcribed) and
cross-checked for internal consistency (no duplicate pin numbers, correct
pin count matching the file's own 132 `(pin ...)` blocks). The first parse
attempt had a bug (missed 7 pins that used a `clock` graphic style instead
of `line`, silently mis-aligning the rest) — caught by a duplicate-count
sanity check before being trusted, the same "verify the verification"
discipline used throughout this project.

**What is NOT independently verified**: the real physical *footprint*
(exact pad coordinates on the 29 x 32.8 mm-class LCC package). No real
footprint file for this part was found in this pass (see "Footprint" in
Integration below) — this is flagged as an open fabrication risk, exactly
like the DF40C/BQ25792 dimensional flags elsewhere in this project.

## Why this module fits the Maverick 1000

Weighed against the brief's explicit priority list:

- **Throughput**: LTE Cat 4 is a 3GPP-standardized UE category with a
  defined peak rate ceiling of 150 Mbps downlink / 50 Mbps uplink (a
  specification fact, not a vendor marketing number) — far more than
  needed for compressed live video (a few to ~20 Mbps for 1080p/4K
  H.264/H.265) plus telemetry and mission data. Real-world throughput is
  network- and signal-condition-dependent and will typically be a small
  fraction of the category ceiling — this is stated as a class
  characteristic, not a guaranteed number, per the "don't claim
  performance the manufacturer doesn't document" constraint.
- **Latency**: typical LTE network round-trip latency is commonly in the
  30-70 ms range under good coverage — workable for an interactive live
  preview / mapping downlink, though not as tight as a dedicated
  point-to-point radio. This is a real, known trade-off of the cellular
  approach, stated plainly rather than oversold (see "Alternatives
  considered" below).
- **Range / reliability**: this is the main reason cellular was chosen
  over a point-to-point ISM-band radio. Range is bounded by cellular
  network coverage, not free-space RF budget — for a mapping/scouting
  mission profile operating within a coverage area, this gives genuinely
  long, reliable range (kilometers) using infrastructure that already
  exists, rather than requiring a matched ground-station radio and
  antenna mast. The explicit trade-off (no function outside coverage) is
  documented, not hidden.
- **Linux/CM4 compatibility**: LTE USB modems in this class (Quectel
  EC2x/EG2x family) have long-standing mainline Linux kernel support
  (`qmi_wwan`, `option`, `cdc_acm` drivers, `ModemManager`/ `libqmi`
  userspace stack) — this is one of the most software-mature module
  classes available for embedded Linux, not a niche/unsupported choice.
- **Host interface**: **USB 2.0 High-Speed** (pins 69/70/71 —
  `USB_DP`/`USB_DM`/`USB_VBUS`), which lands directly on the CM4's own
  USB2 OTG port — the *same physical CM4 pins* (J2 pins 1/3/5) already
  verified with high confidence in `docs/CM4_PIN_VERIFICATION.md` this
  session. This was a deciding factor: it avoids introducing a *second*,
  unverified high-speed CM4 interface (PCIe or Ethernet) into this
  board — this session tried and failed to independently verify real CM4
  PCIe pin numbers from open sources (see "Alternatives considered"), and
  per this project's explicit rule against inventing pin assignments,
  wiring to an unverified interface was rejected in favor of the
  interface this project already has real, trusted pin data for.
- **Power**: module supply pins (`VBAT_BB`/`VBAT_RF`, dual-bonded, pins
  57/58/59/60) are consistent with the 3.3-4.3 V supply class typical of
  this module family — fed from this board's existing +3V3 rail is
  *not* sufficient margin-wise for some EC2x variants' documented minimum
  (some need >3.3 V nominal); **this design feeds it from a dedicated
  step-down tapped from `VBAT_BUS` instead of the shared +3V3 rail** (see
  Integration below) specifically so a cellular TX burst's transient
  current draw cannot dip the CM4/logic 3V3 rail. Exact current
  consumption (including TX burst peaks, commonly the largest current
  transient in a cellular design) is **not verified against a real
  datasheet** in this pass — flagged as a real, open risk in
  `docs/FINAL_DESIGN_AUDIT.md`, not assumed away.
- **Mass/size**: LCC module footprint class is small (real EC25-class
  parts are commonly cited around 29 x 32.8 x 2.4 mm, a few grams bare) —
  small relative to the ≤250 g airframe budget. Full subsystem mass
  (module + SIM holder + antenna + pigtail, see below) is estimated, not
  measured — flagged as an estimate.
- **Availability**: Quectel EC25-family modules are stocked by normal
  distributors (Digikey, Mouser, LCSC and others routinely carry Quectel
  EC2x parts) — not a boutique/single-source part.
- **Antenna connectivity**: standard U.FL/IPEX-class micro-coax pads for
  `ANT_MAIN` (cellular, pin 49) and `ANT_GNSS` (module's own onboard GNSS
  receiver, pin 47) — industry-standard connector approach, consistent
  with how this board already handles RF connections.
- **Existing Linux drivers**: see "Linux/CM4 compatibility" above.
- **Regulatory**: operates on licensed cellular spectrum via a carrier —
  this significantly *reduces* the aircraft's own RF-emissions regulatory
  burden relative to a custom point-to-point ISM-band link, since the
  module itself is a modular-certified radio (FCC/CE certification is
  part of Quectel's standard product line for this class, though the
  **exact regional variant/band-plan SKU must be selected for the
  aircraft's actual country of operation** before ordering — "EC25VFA"
  denotes one specific regional/band variant found in the verified
  source; this is flagged as a purchasing-time decision, not assumed).
- **Practical PCB integration**: reuses an already-verified host
  interface (CM4 USB2), needs no new CM4 pin risk, and is a single
  SMT-mount module rather than a multi-board assembly — directly
  addresses "practical integration over theoretical performance."

## Alternatives considered and rejected

1. **CM4 PCIe-attached module (e.g. a PCIe/M.2 WiFi 6 or 5G card).**
   Rejected: this session made a real, thorough attempt to independently
   verify CM4's real PCIe differential-pair pin numbers on J2 from open
   sources (the same GitHub cross-referencing method used successfully
   for every other verified part in this project — checked
   `antmicro/scalenode-cm4-baseboard`, a real CM4 PCIe carrier, and
   `intergalaktik/ULX4M-PCIe-IO`) and could not extract trustworthy exact
   pin numbers (the antmicro schematic uses net labels tied to symbol
   geometry rather than named pins, and would have required parsing
   graphical wire coordinates rather than reading real pin data — too
   unreliable to commit hardware to; the ULX4M library turned out to be a
   generic PCIe *card-edge* connector template, not CM4-specific). Per
   this project's explicit rule against inventing pin assignments, PCIe
   was not used. USB2 was chosen specifically because it already has
   trusted pin data.
2. **CM4 Ethernet-attached module (e.g. a Doodle Labs Mini-OEM-class
   point-to-point radio, Ethernet host interface).** Rejected for the
   same reason: CM4's Ethernet PHY pin assignment was not independently
   re-verified this session (out of scope of the original CM4 pin audit,
   which only verified the pins this board's pre-existing design actually
   used). A point-to-point ISM-band radio would also have given lower,
   more predictable latency than cellular and independence from ground
   infrastructure — a real advantage for missions outside cellular
   coverage — but at the cost of requiring a matched ground-station radio
   (out of scope of "carrier PCB" integration) and an unverified host
   interface. Documented here as a legitimate Rev B option if a future
   pass verifies CM4's real Ethernet pin assignment.
3. **Proprietary FPV digital video systems (e.g. DJI O3, Walksnail
   Avatar).** Rejected outright: these do not expose a documented,
   general-purpose host data interface a Linux companion computer can use
   for telemetry/mission data/mapping — they are closed, single-purpose
   video links, not usable as "CM4 ↔ module ↔ ground station" data
   modems as required by the brief.
4. **Generic high-power WiFi (e.g. a long-range 802.11ac/ax module).**
   Rejected as not fitting the "realistic, not theoretical-best"
   instruction: standard WiFi's practical range (on the order of
   100-300 m even with a good link) is short for a scouting/mapping
   mission profile relative to cellular's coverage-area range, and
   long-range WiFi video-link products in the drone space are mostly
   proprietary broadcast systems (same problem as item 3), not
   Linux-host-drivable modems.

## Host interface and expected bandwidth (CM4 ↔ module ↔ ground station)

```
CM4 (Linux, qmi_wwan/ModemManager)
   |  USB 2.0 Hi-Speed (480 Mbit/s link rate; real achievable
   |  throughput is set by the cellular link, not the USB link --
   |  USB2 is not the bottleneck for this application)
   v
U8 (Quectel EC25, LTE Cat 4 modem)
   |  Licensed cellular RF (ANT_MAIN, pin 49)
   v
Cellular network (carrier infrastructure)
   |  Standard IP backhaul
   v
Ground station (any Internet-reachable endpoint -- VPN/relay server,
                  cloud relay, or a SIM-equipped ground unit on the
                  same carrier)
```

The CM4 handles this as an ordinary USB network/serial device (like any
USB cellular modem on a Linux host) — it does not require dedicated CM4
CPU cycles beyond normal network-stack overhead, so it does not compete
with the autonomy/mapping/flight-control workload's CPU budget in any way
specific to this module (ordinary IP traffic handling only). ELRS's own
UART link to the flight controller is entirely separate hardware
(different net, different connector, different CM4 pins) and shares
nothing with this path.

## Power consumption

**Not fully verified against a real datasheet this pass** (Quectel's own
documentation was not reachable from this environment). What is known
with reasonable confidence for this module class: supply voltage range
approximately 3.3-4.3 V on `VBAT_BB`/`VBAT_RF`, with cellular TX bursts
producing the dominant current transient (commonly the largest instantaneous
current draw in a cellular-modem design, on the order of 1-2 A peak for
this power class during a transmit burst, average draw much lower). This
project's power design (see Integration) provisions a dedicated,
adequately-decoupled supply rather than assuming worst case is negligible,
but the exact number needed to size the regulator/decoupling with margin
**must be confirmed against the real EC25 datasheet before ordering
boards** — flagged explicitly, not silently assumed safe.

## Physical dimensions and mass

- Module (LCC package): commonly cited as approximately 29.0 x 32.8 x
  2.4 mm for this part class — **not independently verified this pass**
  (no real footprint/mechanical-drawing source was found — see
  Integration). Flagged as a dimensional assumption requiring
  verification, the same treatment as this project's other unverified
  footprints.
- Estimated mass, bare module: a few grams (LCC packages in this size
  class are typically in the 5-6 g range) — **engineering estimate, not
  measured or datasheet-cited**.
- Added mass for the full subsystem (module + nano-SIM holder + U.FL
  pigtail + small antenna): engineering estimate on the order of 10-20 g
  total depending on antenna choice, well within the aircraft's overall
  mass budget headroom discussed in `docs/architecture.md` §7 — but not a
  measured number.

## Antenna requirements

- **ANT_MAIN** (cellular, pin 49): requires an external cellular antenna
  (LTE-band, typically a small dipole or PCB/FPC antenna) connected via a
  U.FL/IPEX-class micro-coax connector and short pigtail — the same
  connector class already used elsewhere in this project's RF
  interfaces. See Integration and `docs/architecture.md` for placement
  guidance (separation from GNSS and ELRS, ground-plane considerations,
  orientation-independence on a multirotor).
- **ANT_GNSS** (pin 47, the module's *own* onboard GNSS receiver): **left
  unconnected in this design.** The Maverick 1000 already has a dedicated
  GNSS receiver (BN-220 via the FC/GNSS connector, see
  `docs/connector_pinouts.md`) — using the EC25's own GNSS function would
  be redundant and would add another antenna, connector, and RF keepout
  requirement for no functional benefit. This is a deliberate integration
  decision, not an oversight.
- **ANT_DIV** (pin 35, receive-diversity antenna): **left unconnected.**
  Diversity improves receive robustness in multipath-heavy environments
  but requires a second antenna, connector, and RF keepout region — for a
  ≤250 g aircraft's mass/complexity budget, single-antenna operation is
  the more appropriate trade-off. Documented as a deliberate
  simplification, not a missed requirement.

## Regulatory considerations

The module operates on licensed cellular spectrum via a carrier
subscription (data SIM required) rather than unlicensed ISM bands, which
meaningfully reduces this aircraft's own RF-certification burden relative
to a custom point-to-point radio design — but the **specific regional
variant/band-plan SKU must be selected to match the aircraft's actual
country/region of operation** before ordering (this is standard practice
for Quectel EC25-family parts, which ship in multiple regional band
variants). "EC25VFA-512-STD" is the variant this session's real,
verified source happened to model; it is cited here as evidence the part
family is real and integrable, not as a claim that this exact regional
variant is the correct one to order — that selection needs to be made
against the actual operating region and carrier requirements.

## Availability

Quectel EC25-family LTE Cat 4 modules are stocked by normal electronics
distributors (Digikey, Mouser, LCSC, and others carry Quectel EC2x
parts routinely) — not a boutique or single-source component.

## PCB integration requirements

See "Integration" section of `docs/FINAL_DESIGN_AUDIT.md` (post-update)
and `python/design_data.py` for the implemented circuit. Summary:

- U8 (EC25 module, LCC, soldered directly — no socket/card-edge
  connector, minimizing added connector mass and height)
- J13: nano-SIM push-pull card holder, wired to the 6 real USIM interface
  pins (`USIM_VDD`/`USIM_GND`/`USIM_DATA`/`USIM_CLK`/`USIM_RST`/
  `USIM_PRESENCE`)
- J14: U.FL-class RF connector for `ANT_MAIN`
- Dedicated power path from `VBAT_BUS` (not the shared +3V3 rail) through
  a new small buck/LDO stage sized for this module's supply range and
  transient current, with local bulk + high-frequency decoupling directly
  at the `VBAT_BB`/`VBAT_RF` pins
- `PWRKEY`, `RESET_N` routed to spare CM4 GPIOs for host-controlled
  power-on/reset sequencing
- `W_DISABLE#` pulled to its inactive (radio-enabled) state by default via
  a pull-up resistor — a spare-GPIO override was considered and rejected
  for this pass to avoid consuming another of the CM4's limited remaining
  GPIOs for a "nice to have" rather than "required" function
- `STATUS`, `NET_STATUS` routed to spare CM4 GPIOs for host-side link
  monitoring (module-ready and network-registration status), rather than
  dedicated LEDs, to save component mass
- `USB_DP`/`USB_DM`/`USB_VBUS` wired to the CM4's own verified USB2 OTG
  port (J2 pins 1/3/5) — this repurposes the pins the pre-existing design
  reserved for USB OTG/debug use; debug/programming access to the CM4
  itself is unaffected (it uses the separate DEBUG UART header, J10)
- All real GND pins (a large fraction of the 132) tied to the board's GND
  net — required for the module's RF/thermal return path, not optional
- Every other real pin (PCM audio-codec interface, SDIO x2, Bluetooth,
  Ethernet-PHY/SGMII, WLAN-coexistence, legacy UART modem-control lines,
  ADCs, `USB_BOOT`, `VDD_EXT`, `ANT_DIV`, `ANT_GNSS`) intentionally left
  unconnected — not used by this design, explicitly documented rather
  than silently omitted, exactly as the CM4 connectors' genuine NC pins
  were documented earlier in this project

## Component verification checklist status

Added to the checklist alongside the existing verified parts
(`docs/CM4_PIN_VERIFICATION.md`, `docs/BQ25792_VERIFICATION.md`, etc.):

| Item | Status |
|---|---|
| U8 (Quectel EC25) real pinout | **Verified** — extracted from a real, working KiCad symbol (SPIRIT-org/SPIRIT), manufacturer/description metadata confirms it models a genuine Quectel part, internal consistency-checked (no duplicate pins, full 132/132 pin count) |
| U8 real footprint/mechanical dimensions | **UNRESOLVED FABRICATION BLOCKER** — no real footprint or mechanical drawing found across two full search passes (13+ distinct queries total, see `docs/assumptions.md` #12 for the full exhaustion record); built from commonly-cited package dimensions only. This is not an approximation pending refinement, it is a hard fabrication stop: do not place U8 from the current footprint. |
| U8 exact power consumption | **NOT verified** — datasheet unreachable from this environment; power design provisioned conservatively but not against confirmed numbers |
| U8 exact regional/band variant | **Purchasing decision, not yet made** — must match actual operating region/carrier before ordering |
| SIM holder, U.FL connector | Generic, industry-standard connector classes — not tied to a specific verified manufacturer part number this pass |
