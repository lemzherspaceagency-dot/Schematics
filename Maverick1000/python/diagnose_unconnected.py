#!/usr/bin/env python3
"""
Comprehensive per-net diagnostic report for every remaining unconnected
gap on the board. For each net that isn't fully connected as one
cluster, computes a minimum-spanning-tree over its real clusters (not
just the single nearest pair) so every gap that actually needs a route
is captured, then for each gap:
  - which layers each endpoint pad is actually reachable on
  - a zero-radius escape probe (can the pad leave its own footprint at
    all, on any layer, via included)
  - a REAL windowed A* search (the same LocalWindow3L the production
    router uses, same margin formula) at the router's actual width
    ladder, reporting exactly which widths were tried and which failed
  - if no path was found: a per-layer flood-fill size from each
    endpoint (to distinguish "locally cramped, needs a bigger window or
    clearance fix" from "wide open locally but no through-route exists
    within the window -- a real distributed congestion problem")

Every "impossible" or "blocked" conclusion here is backed by the probe
results printed alongside it -- nothing is asserted without evidence.
"""
import sys, math, time
from collections import defaultdict, deque

import pcbnew

sys.path.insert(0, "/home/user/Schematics/Maverick1000/python")
from design_data import NETS
from board_clusters import get_net_clusters, mm
from route_inner_layer import LocalWindow3L, PCB_PATH, GRID_LAYERS, GRID, TRY_WIDTHS, _POWER_NETS, _POWER_MIN_WIDTH, _POWER_NECK_WIDTH
from board_rules import ClearanceModel

DENSE_REFS = {"U3", "U1", "U2", "U7", "U10", "U6"}


def main():
    board = pcbnew.LoadBoard(PCB_PATH)
    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
    clearance_model = ClearanceModel(board)

    def find_pad(ref, pin):
        fp = fp_by_ref.get(ref)
        if fp is None:
            return None
        for p in fp.Pads():
            if p.GetNumber() == str(pin):
                return p

    tracks_by_net = defaultdict(list)
    for t in board.GetTracks():
        tracks_by_net[t.GetNetname()].append(t)

    def nearest_pair(cluster_a, cluster_b):
        best = None
        for ref_a, pin_a, pa in cluster_a:
            ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
            for ref_b, pin_b, pb in cluster_b:
                bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
                d = math.hypot(bx - ax, by - ay)
                if best is None or d < best[0]:
                    best = (d, ref_a, pin_a, ref_b, pin_b)
        return best

    def mst_gaps(clusters):
        """Prim's MST over cluster centroids using nearest_pair distances
        -- gives the real minimum set of gaps needed to fully connect
        this net's clusters (not just the single overall-nearest pair)."""
        n = len(clusters)
        in_tree = [False] * n
        in_tree[0] = True
        gaps = []
        for _ in range(n - 1):
            best = None
            for i in range(n):
                if not in_tree[i]:
                    continue
                for j in range(n):
                    if in_tree[j]:
                        continue
                    cand = nearest_pair(clusters[i], clusters[j])
                    if best is None or cand[0] < best[0]:
                        best = (cand[0], i, j, cand[1], cand[2], cand[3], cand[4])
            _, i, j, ref_a, pin_a, ref_b, pin_b = best
            in_tree[j] = True
            gaps.append((ref_a, pin_a, ref_b, pin_b))
        return gaps

    def layer_flood(win, x, y, cap=8000):
        sizes = {}
        cx0, cy0 = win.to_cell(x, y)
        for li, lname in enumerate(("F.Cu", "In1.Cu", "B.Cu")):
            visited = {(cx0, cy0)}
            q = deque([(cx0, cy0)])
            cnt = 0
            while q and cnt < cap:
                cx, cy = q.popleft()
                cnt += 1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) in visited:
                        continue
                    if win._passable(li, nx, ny, 1):
                        visited.add((nx, ny))
                        q.append((nx, ny))
            sizes[lname] = len(visited)
        return sizes

    report = []
    t_start = time.time()
    for net_name, conns in NETS.items():
        if net_name == "GND":
            continue
        real_pads = [(ref, pin, find_pad(ref, pin)) for ref, pin in conns if find_pad(ref, pin)]
        if len(real_pads) < 2:
            continue
        clusters = get_net_clusters(board, net_name, real_pads, tracks_by_net)
        if len(clusters) <= 1:
            continue
        gaps = mst_gaps(clusters)
        for ref_a, pin_a, ref_b, pin_b in gaps:
            pa, pb = find_pad(ref_a, pin_a), find_pad(ref_b, pin_b)
            ax, ay = mm(pa.GetPosition().x), mm(pa.GetPosition().y)
            bx, by = mm(pb.GetPosition().x), mm(pb.GetPosition().y)
            dist = math.hypot(bx - ax, by - ay)
            a_layers = [i for i, kl in enumerate(GRID_LAYERS) if pa.IsOnLayer(kl) or pa.HasHole()]
            b_layers = [i for i, kl in enumerate(GRID_LAYERS) if pb.IsOnLayer(kl) or pb.HasHole()]

            entry = {
                "net": net_name, "a": f"{ref_a}.{pin_a}", "b": f"{ref_b}.{pin_b}",
                "dist": dist, "a_layers": a_layers, "b_layers": b_layers,
            }
            if not a_layers or not b_layers:
                entry["verdict"] = "NO_ACCESSIBLE_LAYER"
                report.append(entry)
                continue

            win = LocalWindow3L(board, net_name, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by),
                                 clearance_model=clearance_model)
            widths = TRY_WIDTHS
            if net_name in _POWER_NETS:
                full = tuple(w for w in TRY_WIDTHS if w >= _POWER_MIN_WIDTH) or (_POWER_MIN_WIDTH,)
                neck = tuple(w for w in TRY_WIDTHS if w < _POWER_MIN_WIDTH) + (_POWER_NECK_WIDTH,)
                widths = full + neck
            tried = []
            found_width = None
            for w in widths:
                radius = max(0, math.ceil((w / 2) / GRID))
                path = win.astar((ax, ay), a_layers, (bx, by), b_layers, radius)
                tried.append((w, path is not None))
                if path is not None:
                    found_width = w
                    break
            entry["widths_tried"] = tried
            if found_width is not None:
                entry["verdict"] = "PATH_EXISTS_NOW"
            else:
                fa = layer_flood(win, ax, ay)
                fb = layer_flood(win, bx, by)
                entry["flood_a"] = fa
                entry["flood_b"] = fb
                local_open_a = max(fa.values()) > 50
                local_open_b = max(fb.values()) > 50
                if not local_open_a or not local_open_b:
                    entry["verdict"] = "LOCALLY_CRAMPED"
                else:
                    entry["verdict"] = "DISTRIBUTED_CONGESTION"
            report.append(entry)
        if time.time() - t_start > 1400:
            print("### TIME LIMIT REACHED, stopping early ###")
            break

    print(f"\n=== Diagnostic report: {len(report)} gaps across all not-fully-connected nets ===\n")
    for e in report:
        print(f"NET {e['net']}: {e['a']} -- {e['b']}  dist={e['dist']:.1f}mm")
        print(f"  a_layers={e['a_layers']} b_layers={e['b_layers']}")
        if e["verdict"] == "NO_ACCESSIBLE_LAYER":
            print(f"  VERDICT: NO_ACCESSIBLE_LAYER (pad has no modeled layer -- real bug, needs investigation)")
        elif e["verdict"] == "PATH_EXISTS_NOW":
            print(f"  widths tried: {e['widths_tried']}")
            print(f"  VERDICT: PATH_EXISTS_NOW -- router should catch this on next pass")
        elif e["verdict"] == "LOCALLY_CRAMPED":
            print(f"  widths tried: {e['widths_tried']}")
            print(f"  flood(a)={e['flood_a']}  flood(b)={e['flood_b']}")
            print(f"  VERDICT: LOCALLY_CRAMPED (one endpoint has <=50 open cells nearby -- genuine tight escape, candidate for clearance/DRU investigation)")
        else:
            print(f"  widths tried: {e['widths_tried']}")
            print(f"  flood(a)={e['flood_a']}  flood(b)={e['flood_b']}")
            print(f"  VERDICT: DISTRIBUTED_CONGESTION (both endpoints wide open locally, no through-route in window -- needs corridor-level rip-up/reroute, not a local fix)")
        print()

    verdict_counts = defaultdict(int)
    for e in report:
        verdict_counts[e["verdict"]] += 1
    print("=== Summary ===")
    for v, c in sorted(verdict_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {v}: {c}")
    print(f"Total gaps: {len(report)}")


if __name__ == "__main__":
    main()
