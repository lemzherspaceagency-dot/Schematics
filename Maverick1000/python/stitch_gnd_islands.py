#!/usr/bin/env python3
"""
Finds and fixes electrically-isolated GND zone islands on F.Cu.

Real DRC flagged an "unconnected_items" finding between the F.Cu GND
zone and itself -- KiCad's own way of saying the zone's fill produced
more than one electrically-disconnected copper region on that layer.
Investigated (not just silenced): the F.Cu GND pour is the only layer
with more than one fill outline -- In1.Cu/In2.Cu/B.Cu each fill as one
single continuous plane (checked via GetFilledPolysList().OutlineCount()
on each layer). This means any F.Cu island IS reachable from the real,
single, continuous ground plane the moment a via connects it there --
this is a routing-geometry gap (a pocket of F.Cu copper walled off by
other nets' tracks/pads with no via nearby), not an accidental zone
fragment or a legitimately-intentional separate ground region.

This script locates every extra F.Cu GND island (anything beyond the
first/largest, which is the main plane) and drops one real via inside it,
on the GND net, at a real GND-net pad already inside that island where
possible (so the via lands on existing GND copper, not floating mid-pour)
-- stitching it to the continuous inner-layer planes.

Usage: python3 stitch_gnd_islands.py   (run AFTER zone fill; re-fill and
re-run DRC afterward to confirm)
"""
import pcbnew

PCB_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb"
VIA_DIA = 0.6
VIA_DRILL = 0.4


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    gnd_net = None
    for n in board.GetNetInfo().NetsByNetcode().values():
        if n.GetNetname() == "GND":
            gnd_net = n
            break
    assert gnd_net is not None

    f_cu_zone = None
    for z in board.Zones():
        if z.GetLayer() == pcbnew.F_Cu and z.GetNetname() == "GND":
            f_cu_zone = z
            break
    if f_cu_zone is None:
        print("No F.Cu GND zone found -- nothing to do.")
        return

    fp_polys = f_cu_zone.GetFilledPolysList(pcbnew.F_Cu)
    n_outlines = fp_polys.OutlineCount()
    print(f"F.Cu GND zone fill outline count: {n_outlines}")
    if n_outlines <= 1:
        print("Already a single connected island -- nothing to do.")
        return

    # Identify the main (largest-area) island; every other island needs
    # its own via to reach the continuous inner-layer planes.
    areas = [(f_cu_zone.GetFilledPolysList(pcbnew.F_Cu).Outline(i).Area(), i)
             for i in range(n_outlines)]
    areas.sort(reverse=True)
    main_idx = areas[0][1]
    stitched = 0
    for area, i in areas[1:]:
        outline = f_cu_zone.GetFilledPolysList(pcbnew.F_Cu).Outline(i)
        bbox = outline.BBox()
        cx = pcbnew.VECTOR2I(bbox.GetCenter().x, bbox.GetCenter().y)
        cx_mm, cy_mm = cx.x / 1e6, cx.y / 1e6
        print(f"Isolated island: bbox center ({cx_mm:.2f}, {cy_mm:.2f}) mm, area {area/1e12:.2f} mm^2")

        # Prefer to land the via exactly on a real GND pad already inside
        # this island (mechanically sound -- via lands on existing
        # copper, not mid-pour) -- fall back to the bbox center otherwise.
        best_pad = None
        best_d = None
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetname() != "GND" or not pad.IsOnLayer(pcbnew.F_Cu):
                    continue
                p = pad.GetPosition()
                if not outline.PointInside(pcbnew.VECTOR2I(p.x, p.y)):
                    continue
                d = ((p.x - cx.x) ** 2 + (p.y - cx.y) ** 2)
                if best_d is None or d < best_d:
                    best_d = d
                    best_pad = pad

        via_pos = best_pad.GetPosition() if best_pad is not None else cx
        already = any(
            t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"
            and abs(t.GetPosition().x - via_pos.x) < 10000
            and abs(t.GetPosition().y - via_pos.y) < 10000
            for t in board.GetTracks()
        )
        if already:
            print(f"  GND via already present near ({via_pos.x/1e6:.2f}, {via_pos.y/1e6:.2f}) mm -- skipping duplicate")
            continue
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(via_pos)
        via.SetWidth(pcbnew.FromMM(VIA_DIA))
        via.SetDrill(pcbnew.FromMM(VIA_DRILL))
        via.SetNet(gnd_net)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        board.Add(via)
        stitched += 1
        loc = "on pad " + best_pad.GetParent().GetReference() + "." + best_pad.GetPadName() if best_pad else "at bbox center"
        print(f"  Added GND stitching via {loc} at ({via_pos.x/1e6:.2f}, {via_pos.y/1e6:.2f}) mm")

    print(f"\nStitched {stitched} isolated island(s). Re-fill zones and re-run DRC to confirm.")
    board.Save(PCB_PATH)
    print(f"Saved {PCB_PATH}")


if __name__ == "__main__":
    main()
