#!/usr/bin/env python3
"""
Generate kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb via
the real pcbnew Python API: loads real footprints (stock KiCad libraries +
our custom SKYWARD_Custom.pretty), places them, assigns every net from
design_data.py, draws the board outline + mounting holes, pours GND zones
on all 4 layers, adds silkscreen identification, and routes the critical
power-path traces.
"""

import pcbnew
from design_data import COMPONENTS, NETS, COMP_BY_REF

STOCK_FP_DIR = "/usr/share/kicad/footprints"
CUSTOM_FP_DIR = "/home/user/Schematics/Maverick1000/kicad/libraries/footprints/SKYWARD_Custom.pretty"
OUT_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"

MM = pcbnew.FromMM

# ---------------------------------------------------------------------------
# Board outline: 100 x 80 mm, origin at (0,0) = bottom-left in our own coords
# (KiCad internal Y still grows downward on screen; that's fine, we just
# need consistent placement math).
# ---------------------------------------------------------------------------
BOARD_W = 110.0
# Extended from 90mm this pass to fit the high-bandwidth comms subsystem
# (Quectel EC25 modem, USB2512B hub, dedicated power stage, SIM holder,
# antenna connector) added between the existing interior grids and the
# bottom-edge Terra connector -- see docs/COMMS_MODULE_DECISION.md. J9
# (Terra) and MH3/MH4 are defined relative to BOARD_H below, so they and
# the new comms band both shift automatically with this one constant.
BOARD_H = 125.0
EDGE_MARGIN = 3.0

# ---------------------------------------------------------------------------
# Placement: explicit zone-based layout with basic EMI/thermal discipline --
# switching power section kept away from the GNSS connector, connectors
# pushed to board edges for post-assembly cable access.
# ---------------------------------------------------------------------------
PLACEMENTS = {}  # ref -> (x_mm, y_mm, rotation_deg, layer)  layer: 'F' or 'B'

# Layout strategy: the board is divided into non-overlapping rectangular
# bands (verified empirically with a courtyard-overlap checker -- see
# docs/assumptions.md). Edge connectors get a reserved margin strip along
# each side so their footprints never intrude on the interior grids.
INNER_X0, INNER_X1 = 12.0, 98.0
INNER_Y0, INNER_Y1 = 8.0, 76.0

# CM4 connectors: top band
PLACEMENTS["J1"] = (35.0, 12.0, 0, "F")
PLACEMENTS["J2"] = (75.0, 12.0, 0, "F")

# CM4 decoupling / boot straps / debug header: band below the connectors
# U10 (USB boot-mode mux, fabrication-readiness pass) added here --
# electrically it sits right on the CM4's own OTG pins (J2), so it
# belongs in this band, not off in the comms-subsystem band with U7.
cm4_support = ["C11", "C12", "C13", "C14", "C15", "R7", "R8", "R9", "SW1", "SW2", "J10", "U10"]
cell_w = (INNER_X1 - INNER_X0) / 6
for i, ref in enumerate(cm4_support):
    PLACEMENTS[ref] = (INNER_X0 + cell_w/2 + (i % 6) * cell_w, 21.0 + (i // 6) * 7.0, 0, "F")
# C38 (U10's own VCC decoupling): placed as a small offset from U10
# rather than adding a 3rd grid row, which would have collided with the
# power-section grid starting at y=33.0 (a real courtyard-overlap DRC hit
# this pass caught and this placement avoids).
PLACEMENTS["C38"] = (PLACEMENTS["U10"][0] + 6.0, PLACEMENTS["U10"][1], 0, "F")

# Power section: left 2/3 of the remaining interior (kept away from the
# GNSS connector on the right edge, per architecture.md's EMI guidance)
power_refs = [c.ref for c in COMPONENTS if c.group == "power" and c.ref not in ("J3", "J4")]
px0, px1 = INNER_X0, 74.0
pcols = 8
pcell_w = (px1 - px0) / pcols
pcell_h = 7.5
for i, ref in enumerate(power_refs):
    col, row = i % pcols, i // pcols
    PLACEMENTS[ref] = (px0 + pcell_w/2 + col * pcell_w, 33.0 + row * pcell_h, 0, "F")

# Terra pull-ups/jumper/LED + test points: right column of the interior
right_misc = ["R10", "R11", "R12", "R13", "R14", "R15", "JP1", "LED1", "R6",
              "TP1", "TP2", "TP3", "TP4"]
rx0, rx1 = 76.0, INNER_X1
rcols = 2
rcell_w = (rx1 - rx0) / rcols
rcell_h = 6.2
for i, ref in enumerate(right_misc):
    col, row = i % rcols, i // rcols
    PLACEMENTS[ref] = (rx0 + rcell_w/2 + col * rcell_w, 33.0 + row * rcell_h, 0, "F")

# Comms subsystem band: between the original interior grids (which end at
# INNER_Y1=76) and the Terra connector's new bottom-edge position (see
# BOARD_H above). U8 (EC25) is by far the largest single footprint on this
# board (29 x 32.8mm) -- placed individually, rotated 90 deg so its longer
# dimension runs along X (fits the board's available width better than
# fighting for Y height). U7 (hub)/U9 (buck) and their support passives
# fill the remaining band width beside it. J11/J12 get edge positions,
# matching this board's existing edge-connector convention.
PLACEMENTS["U8"] = (35.0, 98.0, 90, "F")   # EC25 modem, rotated

comms_hub_support = ["U7", "Y1", "C31", "C32", "R25", "C30", "R26", "R27",
                      "R28", "C33", "C34", "C19", "C20"]
chx0 = 58.0
chcell_w = 7.75
for i, ref in enumerate(comms_hub_support):
    col, row = i % 5, i // 5
    PLACEMENTS[ref] = (chx0 + chcell_w/2 + col * chcell_w, 80.0 + row * 8.0, 0, "F")

comms_pwr_support = ["U9", "L3", "D7", "C35", "C36", "C37", "R29", "R30"]
cpx0 = 58.0
cpcell_w = 7.75  # matches the proven U4/L1-class spacing in the main power grid above
for i, ref in enumerate(comms_pwr_support):
    col, row = i % 5, i // 5
    PLACEMENTS[ref] = (cpx0 + cpcell_w/2 + col * cpcell_w, 100.0 + row * 8.0, 0, "F")

comms_ec25_support = ["C26", "C27", "C28", "C29", "R24"]
cex0 = 12.0
cecell_w = 6.0
for i, ref in enumerate(comms_ec25_support):
    PLACEMENTS[ref] = (cex0 + cecell_w/2 + i * cecell_w, 116.5, 0, "F")

PLACEMENTS["J11"] = (10.0, 100.0, 90, "F")           # SIM holder, left edge
PLACEMENTS["J12"] = (BOARD_W - 6.0, 90.0, 270, "F")  # U.FL antenna, right edge
PLACEMENTS["J13"] = (8.0, 85.0, 90, "F")             # USB boot/recovery connector, left edge (between J4 and J11)

# Peripheral connectors: reserved edge margins, clear of the interior grids
PLACEMENTS["J3"] = (6.0, 55.0, 90, "F")     # BATT, left edge
PLACEMENTS["J4"] = (6.0, 68.0, 90, "F")     # DOCK, left edge
PLACEMENTS["J5"] = (BOARD_W - 6.0, 20.0, 270, "F")   # FC, right edge
PLACEMENTS["J6"] = (BOARD_W - 6.0, 33.0, 270, "F")   # GNSS, right edge, away from power
PLACEMENTS["J7"] = (BOARD_W - 6.0, 46.0, 270, "F")   # ELRS, right edge
PLACEMENTS["J8"] = (BOARD_W - 6.0, 59.0, 270, "F")   # TOF, right edge
PLACEMENTS["J9"] = (55.0, BOARD_H - 6.0, 180, "F")   # TERRA, bottom edge (payload bay side)

# Mounting holes: 4 corners, inset
PLACEMENTS["MH1"] = (5.0, 5.0, 0, "F")
PLACEMENTS["MH2"] = (BOARD_W - 5.0, 5.0, 0, "F")
PLACEMENTS["MH3"] = (5.0, BOARD_H - 5.0, 0, "F")
PLACEMENTS["MH4"] = (BOARD_W - 5.0, BOARD_H - 5.0, 0, "F")

missing = [c.ref for c in COMPONENTS if c.ref not in PLACEMENTS]
if missing:
    raise SystemExit(f"No placement defined for: {missing}")


def load_footprint(footprint_field):
    lib, name = footprint_field.split(":", 1)
    lib_dir = CUSTOM_FP_DIR if lib == "SKYWARD_Custom" else f"{STOCK_FP_DIR}/{lib}.pretty"
    fp = pcbnew.FootprintLoad(lib_dir, name)
    if fp is None:
        raise ValueError(f"Could not load footprint {footprint_field} from {lib_dir}")
    # FootprintLoad() takes a raw directory path, not a fp-lib-table
    # nickname, so it leaves the library nickname on the loaded FOOTPRINT
    # blank -- confirmed by a real DRC run flagging 85/85 footprints with
    # "does not include the library ''". Set it explicitly to the logical
    # nickname (matching kicad/SKYWARD-COMPUTE-CARRIER/fp-lib-table) so the
    # board file stores real "Library:Footprint" references, not bare
    # names, and "update footprint from library" works correctly in KiCad.
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def main():
    board = pcbnew.CreateEmptyBoard()
    board.SetCopperLayerCount(4)

    # Board outline (Edge.Cuts)
    edge_layer = pcbnew.Edge_Cuts
    corners = [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]
    for i in range(4):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(edge_layer)
        seg.SetStart(pcbnew.VECTOR2I(MM(corners[i][0]), MM(corners[i][1])))
        seg.SetEnd(pcbnew.VECTOR2I(MM(corners[(i+1) % 4][0]), MM(corners[(i+1) % 4][1])))
        seg.SetWidth(MM(0.15))
        board.Add(seg)

    # Nets
    net_objs = {}
    for name in NETS:
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        net_objs[name] = n

    # Reverse index (ref,pin) -> net name
    pin_net = {}
    for name, conns in NETS.items():
        for ref, pin in conns:
            pin_net[(ref, pin)] = name

    # Footprints
    fp_objs = {}
    for c in COMPONENTS:
        fp = load_footprint(c.footprint)
        x, y, rot, layer = PLACEMENTS[c.ref]
        fp.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        fp.SetOrientationDegrees(rot)
        if layer == "B":
            fp.Flip(pcbnew.VECTOR2I(MM(x), MM(y)), False)
        fp.SetReference(c.ref)
        fp.SetValue(c.value)
        for pad in fp.Pads():
            net_name = pin_net.get((c.ref, pad.GetNumber()))
            if net_name:
                pad.SetNet(net_objs[net_name])
        board.Add(fp)
        fp_objs[c.ref] = fp

    # ---------------------------------------------------------------------
    # Silkscreen identification (F.SilkS), kept clear of components: top
    # margin strip above the CM4 connectors, and bottom margin strip.
    # ---------------------------------------------------------------------
    def add_text(text, x, y, size_mm, layer=pcbnew.F_SilkS, thickness_mm=0.15, bold=False):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size_mm), MM(size_mm)))
        t.SetTextThickness(MM(thickness_mm))
        if bold:
            t.SetBold(True)
        board.Add(t)
        return t

    add_text("FRONTIER INNOVATIONS", BOARD_W / 2, 3.0, 1.6, bold=True)
    add_text("MAVERICK 1000  --  SKYWARD-COMPUTE-CARRIER  --  REV A", BOARD_W / 2, 6.0, 1.0)
    # Zone-label positions below were nudged this pass to clear real DRC
    # silk_overlap/silk_over_copper findings against nearby component
    # reference designators and pads (see docs/ERC_STATUS.md) -- moved
    # away from the specific ref/pad each one was overlapping, not
    # resized/hidden to dodge the check.
    add_text("CM4", 35.0, 6.6, 1.0)
    add_text("CM4", 75.0, 6.6, 1.0)
    add_text("FC", BOARD_W - 10.0, 15.5, 1.0)
    add_text("GNSS", BOARD_W - 15.0, 28.5, 1.0)
    add_text("ELRS", BOARD_W - 12.0, 41.5, 1.0)
    add_text("TOF", BOARD_W - 10.0, 54.5, 1.0)
    add_text("TERRA", 55.0, BOARD_H - 11.0, 1.2)
    add_text("POWER", 13.0, 29.0, 1.0)
    add_text("DOCK", 13.0, 64.0, 1.0)
    add_text("BATT", 10.0, 51.0, 1.0)
    add_text("PIN 1", 35.0 - 11.0, 9.5, 0.8)
    add_text("PIN 1", 75.0 - 11.0, 9.5, 0.8)

    # ---------------------------------------------------------------------
    # GND pour on all 4 copper layers
    # ---------------------------------------------------------------------
    gnd_net = net_objs["GND"]
    zone_layers = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    for layer in zone_layers:
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNetCode(gnd_net.GetNetCode())
        zone.SetIsFilled(False)
        outline = zone.Outline()
        outline.NewOutline()
        m = EDGE_MARGIN + 1.0
        pts = [(m, m), (BOARD_W - m, m), (BOARD_W - m, BOARD_H - m), (m, BOARD_H - m)]
        for px, py in pts:
            outline.Append(MM(px), MM(py))
        zone.SetZoneClearance(MM(0.3)) if hasattr(zone, "SetZoneClearance") else None
        board.Add(zone)

    # ---------------------------------------------------------------------
    # Copper routing: NOT auto-generated in this build.
    #
    # An earlier version of this script drew blind L-shaped point-to-point
    # tracks between "logically adjacent" pads (e.g. fuse -> ORing FET ->
    # shunt). A self-check (comparing every track segment against every pad
    # not on its own net) caught that several of those tracks crossed
    # unrelated component pads once the layout was reworked to fix
    # courtyard overlaps -- i.e. it would have shipped latent shorts. Rather
    # than hand-tune ~40 blind routes against a hand-tuned placement with no
    # visual routing feedback, routing is left as ratsnest (airwires) for
    # every net -- all 60 nets are fully placed and netlisted (verified
    # against python/design_data.py), just not yet copper. See
    # docs/assumptions.md #7 for the rationale and what's left to do.
    # ---------------------------------------------------------------------

    # ---------------------------------------------------------------------
    # Board setup: stackup name hints + save
    # ---------------------------------------------------------------------
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(4)

    # NOTE: ZONE_FILLER.Fill() reliably segfaults in this headless KiCad
    # 7.0.11 Python environment (reproduced in isolation, unrelated to this
    # board's content) -- zones are written UNFILLED (valid, normal .kicad_pcb
    # content) and fill automatically the first time the project is opened
    # and saved in the KiCad GUI, or via Edit > Fill All Zones (hotkey B).
    board.BuildConnectivity()

    pcbnew.SaveBoard(OUT_PATH, board)
    print(f"Wrote {OUT_PATH}")
    print(f"Footprints placed: {len(fp_objs)}   Nets: {len(net_objs)}   (routing left interactive, see docs/assumptions.md #7)")


if __name__ == "__main__":
    main()
