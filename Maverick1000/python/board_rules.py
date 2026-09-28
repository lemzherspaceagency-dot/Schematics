#!/usr/bin/env python3
"""
Shared, board-truth-derived clearance rules for every router in this
project.

Real root cause of the earlier "J1 is impossible" misdiagnosis: every
router script (gen_routes_maze.py, local_fine_route.py,
route_inner_layer.py) hardcoded a blanket clearance constant (0.2 or
0.3mm) for all pad-halo obstacle painting, and never applied the
board's own real .kicad_dru rule that narrows clearance to 0.15mm for
any copper item inside J1 or J2's courtyard (and 0.05mm inside U3's).
Real KiCad DRC has always enforced the narrower rule; the routers'
internal obstacle model did not, so they refused to route paths real
DRC actually allows -- confirmed directly by adding real F.Cu escape
traces at J1 and verifying them with real KiCad DRC (zero clearance
violations) on branch j1-escape-geometry-proof.

This module parses the .kicad_dru file's courtyard-conditioned
clearance rules and the real courtyard graphic extent of every
footprint they reference, so routers can look up the correct clearance
directly from the board's own design rules instead of hardcoding a
number a second time.
"""
import re

import pcbnew

DRU_PATH = "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_dru"
DEFAULT_CLEARANCE = 0.2  # this board's single "Default" netclass, confirmed via the .kicad_pro net_settings


def parse_courtyard_clearance_rules(dru_path=DRU_PATH):
    """Returns {footprint_ref: clearance_mm} for every
    'A.insideCourtyard(<ref>) || B.insideCourtyard(<ref>)'-style rule in
    the board's real .kicad_dru file. Where a ref appears in more than
    one rule, the tightest (minimum) clearance wins, matching how
    multiple simultaneously-matching KiCad custom rules resolve."""
    text = open(dru_path).read()
    rules = {}
    for rule_match in re.finditer(
            r'\(rule\s+"[^"]*"\s*\(condition\s+"([^"]*)"\)\s*'
            r'\(constraint\s+clearance\s*\(min\s+([\d.]+)mm\)\)',
            text):
        condition, val = rule_match.groups()
        val_f = float(val)
        for ref in re.findall(r"insideCourtyard\('([^']+)'\)", condition):
            if ref not in rules or val_f < rules[ref]:
                rules[ref] = val_f
    return rules


def get_courtyard_bboxes(board, refs):
    """Returns {ref: (x0, y0, x1, y1)} in mm, the REAL courtyard extent
    (union of that footprint's F.Courtyard/B.Courtyard graphic items --
    not the footprint's overall bounding box, which is usually much
    larger due to silkscreen reference/value text placement well
    outside the courtyard)."""
    boxes = {}
    fp_by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for ref in refs:
        fp = fp_by_ref.get(ref)
        if fp is None:
            continue
        xs, ys = [], []
        for item in fp.GraphicalItems():
            try:
                layer_name = item.GetLayerName()
            except Exception:
                continue
            if "Courtyard" not in layer_name and "CrtYd" not in layer_name:
                continue
            bb = item.GetBoundingBox()
            xs += [bb.GetLeft() / 1e6, bb.GetRight() / 1e6]
            ys += [bb.GetTop() / 1e6, bb.GetBottom() / 1e6]
        if xs and ys:
            boxes[ref] = (min(xs), min(ys), max(xs), max(ys))
    return boxes


class ClearanceModel:
    """Real-rule-aware clearance lookup: default netclass clearance
    everywhere, except inside a special footprint's real courtyard
    extent, where the board's own .kicad_dru rule applies instead."""

    def __init__(self, board, default_clearance=DEFAULT_CLEARANCE, dru_path=DRU_PATH):
        self.default = default_clearance
        self.rules = parse_courtyard_clearance_rules(dru_path)
        self.boxes = get_courtyard_bboxes(board, self.rules.keys())

    def at_point(self, x_mm, y_mm):
        """Clearance (mm) that applies to an item located at (x, y).
        Matches the real rule's intent (A.insideCourtyard(ref) ||
        B.insideCourtyard(ref)) closely enough for obstacle-grid
        purposes: real DRC remains the actual authority on every
        route this produces."""
        best = self.default
        for ref, (x0, y0, x1, y1) in self.boxes.items():
            if x0 <= x_mm <= x1 and y0 <= y_mm <= y1:
                best = min(best, self.rules[ref])
        return best

    def for_pad(self, pad):
        pos = pad.GetPosition()
        return self.at_point(pos.x / 1e6, pos.y / 1e6)


if __name__ == "__main__":
    board = pcbnew.LoadBoard(
        "/home/user/Schematics/Maverick1000/kicad/SKYWARD-COMPUTE-CARRIER/SKYWARD-COMPUTE-CARRIER.kicad_pcb")
    model = ClearanceModel(board)
    print("Parsed courtyard clearance rules:", model.rules)
    print("Real courtyard bboxes:", model.boxes)
    print("Clearance at J1.45 (34.0, 10.5):", model.at_point(34.0, 10.5))
    print("Clearance at open board area (60, 30):", model.at_point(60.0, 30.0))
