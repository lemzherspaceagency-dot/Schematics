# Power Architecture — SKYWARD-COMPUTE-CARRIER Rev A

## 1. Sources

| Source | Chemistry / range | Connects at |
|---|---|---|
| Main aircraft battery | 4S LiHV, 12.0 V (empty) – 17.4 V (4.35 V/cell full) | `BATT_IN` 2-pin JST-GH, low-current tap in parallel with the FC/ESC's own battery pads |
| Terra P1 auxiliary battery | Assumed same class as main pack (4S LiHV) so it can be safely ORed onto the same bus — **documented assumption, revisable if P1 chemistry differs** | Terra connector `PWR`/`PWR` pins (2 pins, current-shared) |
| Dock charging input | Regulated CC/CV supply from the ground dock, voltage/current profile matched to the 4S LiHV pack at system level (dock is the "smart" side; this board is the "dumb, protected" side) | `DOCK_PWR+` / `DOCK_GND` skid contacts |

## 2. Topology

```
                         ┌────────────────────────────┐
 Main 4S LiHV ───────────┤ F1 PTC + TVS + reverse-pol  │
  (BATT_IN)               │  -> Q1 ideal-diode OR (U1)  ├──┐
                         └────────────────────────────┘  │
                                                            │
                         ┌────────────────────────────┐    │      VBAT_BUS
 Terra P1 battery ───────┤ F2 PTC + TVS + reverse-pol  │    ├──────(12-17.4V)────┬──> 5V buck (U4) ──> +5V0 ─┬─> CM4 VDD_5V0 (J1/J2)
  (Terra PWR pins)        │  -> Q2 ideal-diode OR (U2)  ├────┘                    │                          ├─> Terra PWR (2 pins, fused)
                         └────────────────────────────┘                         │                          └─> INA3221 ch3 shunt -> 5V rail
                                                                                   │
                                                                                   ├──> INA3221 (U6) ch1 = Main batt, ch2 = P1 batt
                                                                                   │
                                                                                   └──> 3V3 LDO (U5, off +5V0) ──> +3V3 ─┬─> CM4 3V3 sense/EEPROM WP pull
                                                                                                                         ├─> GNSS, ELRS RX, VL53L5CX
 Dock (DOCK_PWR+/GND) ──> reverse-pol + fuse ──> BQ25792 charger (U3) ──charges──> Main battery node (upstream of Q1)   ├─> Terra I2C/SPI/UART/GPIO/IRQ pull-ups
   DOCK_DET-N (pulled to GND on mating) ──> CM4 GPIO "dock present"              │                                     └─> level-neutral logic supply (all 3.3V design, no shifting)
                                                                                   BQ25792 I2C telemetry (charge current/voltage, fault) -> CM4 I2C
```

- **U1/U2 — ideal-diode ORing:** LM74610-Q1 controller each driving an
  external P-channel MOSFET (SQJ438EP, 30 V, low RDS(on)). Conducts
  battery -> `VBAT_BUS` with ~tens-of-mV drop (vs. ~0.4-0.7 V for a passive
  Schottky OR), blocks `VBAT_BUS` -> battery in either direction. This is
  what makes the Main/P1 pairing safe: neither pack can be force-discharged
  or back-charged through the other via the bus.
- **U3 — BQ25792 (TI), 1-4S I2C buck charger, up to 24 V input:** charges
  the main pack only, from the dock contacts, gated by dock presence detect
  and CM4-side enable. All charge telemetry (voltage, current, temperature
  fault, charge state) is read by the CM4 over the onboard I2C bus — the
  dock contacts themselves only ever carry raw power + ground + a simple
  presence-detect line, keeping the mechanical skid-contact interface to 3
  pads.
- **U4 — TPS54331 (TI), 3 A sync buck, 28 V abs-max input:** `VBAT_BUS`
  (up to 17.4 V) -> regulated +5.0 V for the CM4 (worst-case ~3 A per the
  CM4 datasheet power budget) and the Terra payload power pins (fused to
  2 A independently so a shorted/faulted payload cannot brown out the CM4).
- **U5 — AP2112K-3.3 LDO, 600 mA:** +5V0 -> +3V3 for all sensor/logic rails
  (GNSS, ELRS RX, VL53L5CX, ID pull-ups, Terra low-speed logic). An LDO
  (not a switcher) is used here specifically to keep switching noise away
  from the GNSS receiver's RF front end, which shares the board.
- **U6 — INA3221 (TI), 3-channel I2C current/voltage monitor:** channel 1 =
  Main battery, channel 2 = Terra P1 battery, channel 3 = +5V0 CM4 rail.
  Gives the CM4 real per-source battery telemetry for RTL/low-battery
  logic and post-flight logging — this is the sensor that lets the
  autonomy stack know it actually has (or doesn't have) the P1 margin the
  30-minute endurance requirement depends on.

## 3. Protection, per input

Each of Main-battery-in, P1-in, and Dock-in gets: resettable PTC fuse,
reverse-polarity protection (series P-FET or Schottky per net, sized to the
expected current), and a TVS clamp rated above the 17.4 V LiHV ceiling
(SMBJ24A, 24 V standoff). Values/part numbers are in the BOM.

## 4. Test points

`TP_VBAT_BUS`, `TP_5V0`, `TP_3V3`, `TP_GND` (x2, near the CM4 and near the
power section) are placed on the PCB as bare 1 mm through-hole/via test
points for bring-up and field diagnostics without needing to probe fine-
pitch IC pins.

## 5. Docking / charging, explicitly

Per the requirement to not assume the main PCB handles large charging
currents directly: the **dock itself** is the intelligent, current-limited
CC/CV source, sized externally to the pack (dock design is out of scope for
this board). This board's job is only to (a) detect the dock is mated,
(b) gate/protect the charge path, and (c) report battery state so the dock
can decide when to stop — exactly the BQ25792's job, which already
implements JEITA-style safety charging and termination in hardware, so the
board doesn't need bespoke charge-control firmware to be safe by default
even before CM4 software is running charge-management logic.

## 6. Energy budget behind the 30-minute (+margin) requirement

This board does not select the propulsion system (explicitly out of scope
per the brief), but the power architecture is sized against the following
placeholder budget so the electronics are not the endurance bottleneck:

| Load | Typical draw |
|---|---|
| 4x motors (existing 1404 ~3800 KV prototype class, hover-ish cruise) | dominant term, propulsion-system dependent — **not sized by this board** |
| CM4 (autonomy workload) | ~2.5-3.5 W (~0.5-0.7 A @ 5 V) |
| FC + receiver + GNSS + VL53L5CX | ~1-1.5 W |
| Terra module (typical, e.g. L1) | up to 65 g slot allows for a module drawing several W; budgeted 5 W max continuous from the 2 A Terra 5 V fuse |

The avionics/compute load (CM4 + sensors, excluding Terra) is a small,
roughly constant fraction (~1-1.5 W) of a multi-hundred-watt-class
propulsion budget, so it is not the limiting term for the 30-minute
requirement — propulsion/airframe efficiency and battery energy (main +
P1) are. This board's contribution to meeting the requirement is (1) not
wasting energy (LDO where switching isn't needed, ideal-diode ORing instead
of lossy passive diode ORing) and (2) giving the CM4 accurate real-time
energy telemetry (INA3221) so mission planning can actually fly to the
available margin instead of a fixed conservative guess.
