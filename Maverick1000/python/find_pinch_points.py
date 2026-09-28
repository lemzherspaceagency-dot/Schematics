#!/usr/bin/env python3
"""
For a given net's gap, finds the actual geometric pinch point(s): where
ALL modeled layers are simultaneously blocked in a perpendicular band
crossing the direct line between the two endpoints. This is a much more
precise "what is actually in the way" test than bounding-box overlap
(which, on this densely populated board, flags nearly every other net
as a "blocker" for nearly every gap -- not useful signal).

Read-only. Usage: python3 find_pinch_points.py <net_name> <ref_a.pin_a> <ref_b.pin_b>
"""
import sys, math

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from route_inner_layer import LocalWindow3L, PCB_PATH, GRID_LAYERS, GRID
from board_rules import ClearanceModel
import pcbnew


def mm(nm):
    return nm / 1e6


def main():
    net_name = sys.argv[1]
    ref_a, pin_a = sys.argv[2].split(".")
    ref_b, pin_b = sys.argv[3].split(".")

    board = pcbnew.LoadBoard(PCB_PATH)
    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p

    pa, pb = find_pad(ref_a, pin_a), find_pad(ref_b, pin_b)
    ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
    bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
    dist = math.hypot(bx - ax, by - ay)
    print(f"{net_name}: {ref_a}.{pin_a} ({ax:.2f},{ay:.2f}) -- {ref_b}.{pin_b} ({bx:.2f},{by:.2f}) dist={dist:.1f}mm")

    clearance_model = ClearanceModel(board)
    win = LocalWindow3L(board, net_name, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by),
                         clearance_model=clearance_model)

    ux, uy = (bx - ax) / dist, (by - ay) / dist  # direction unit vector
    nx_, ny_ = -uy, ux  # perpendicular unit vector

    N = int(dist / 0.5) + 1  # sample every ~0.5mm along the line
    PERP_RANGE = 8.0  # mm each side
    PERP_STEP = 0.1

    pinch_points = []
    for i in range(N + 1):
        t = i / N
        cx = ax + (bx - ax) * t
        cy = ay + (by - ay) * t
        # scan perpendicular to find if ANY layer has an open crossing
        # within +/- PERP_RANGE
        layer_open_width = [0.0, 0.0, 0.0]
        for li in range(3):
            open_run = 0.0
            best_run = 0.0
            s = -PERP_RANGE
            while s <= PERP_RANGE:
                px, py = cx + nx_ * s, cy + ny_ * s
                gx, gy = win.to_cell(px, py)
                if win._passable(li, gx, gy, 1):
                    open_run += PERP_STEP
                    best_run = max(best_run, open_run)
                else:
                    open_run = 0.0
                s += PERP_STEP
            layer_open_width[li] = best_run
        max_open = max(layer_open_width)
        if max_open < 0.3:  # less than one grid-cell-ish continuous opening on ANY layer
            pinch_points.append((t, cx, cy, layer_open_width))

    if not pinch_points:
        print("No pinch point found (every cross-section sampled has >=0.3mm continuous opening on some layer)")
        print("-> genuinely distributed congestion, not a single choke point")
        return

    print(f"\n{len(pinch_points)} pinch point samples found (perpendicular opening <0.3mm on ALL layers):")
    for t, cx, cy, widths in pinch_points[:20]:
        print(f"  t={t:.2f} ({cx:.2f},{cy:.2f})  F.Cu={widths[0]:.2f}mm In1.Cu={widths[1]:.2f}mm B.Cu={widths[2]:.2f}mm")

    # For the tightest point, identify what's actually there.
    worst = min(pinch_points, key=lambda p: max(p[3]))
    t, cx, cy, widths = worst
    print(f"\nTightest point: ({cx:.2f},{cy:.2f})")
    for tt in board.GetTracks():
        if tt.GetNetname() == net_name:
            continue
        if tt.GetClass() == "PCB_VIA":
            p = tt.GetPosition()
            d = math.hypot(mm(p.x) - cx, mm(p.y) - cy)
            if d < 1.0:
                print(f"  nearby VIA net={tt.GetNetname()} at ({mm(p.x):.2f},{mm(p.y):.2f}) dist={d:.2f}mm")
        else:
            s, e = tt.GetStart(), tt.GetEnd()
            sx, sy, ex, ey = mm(s.x), mm(s.y), mm(e.x), mm(e.y)
            # distance from point to segment
            dx, dy = ex - sx, ey - sy
            L2 = dx * dx + dy * dy
            tt2 = max(0, min(1, ((cx - sx) * dx + (cy - sy) * dy) / L2)) if L2 > 0 else 0
            px, py = sx + tt2 * dx, sy + tt2 * dy
            d = math.hypot(cx - px, cy - py)
            if d < 0.5:
                print(f"  nearby TRACK net={tt.GetNetname()} layer={tt.GetLayer()} seg=({sx:.2f},{sy:.2f})-({ex:.2f},{ey:.2f}) dist={d:.2f}mm")


if __name__ == "__main__":
    main()
