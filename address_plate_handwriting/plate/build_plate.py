#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_plate.py -- fuse two hands into one piece of joined-up cursive.

Reads the capture written by ../capture_handwriting.py, blends the two
writers into a single set of letterforms, and writes:

    alyvu_g4.svg    the plate, in millimetres (plate / centreline / outline)
    compare.svg     each hand and the blend on a shared baseline

Deterministic: same capture + same flags == same SVG.
Needs Python 3 and numpy, nothing else.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

TARGET_TEXT_DEFAULT = "Alyvų g. 4"

# Roles a stroke can play. Order matters: it is the drawing order.
ROLES = ["body", "crossbar", "ogonek", "g", "period", "four"]

# Roles that are really two loops joined by a stem (bowl above the baseline,
# tail below it) and so need matching lobe-to-lobe, not point-index-to-index
# -- see split_lobes(). Currently just "g"; "y" or "j" would need the same
# treatment if a future address ever needs them.
LOBE_ROLES = {"g"}

# --------------------------------------------------------------------------
# Loading and normalising
# --------------------------------------------------------------------------


def normalise(sample):
    """Sample -> list of (n,3) arrays [x, y, pressure] in x-height units.

    Baseline is y = 0, y grows UP, x starts at 0 at the leftmost ink.
    """
    g = sample["guides"]
    base, xh = g["baseline_y_px"], g["x_height_px"]
    strokes = []
    for st in sample["strokes"]:
        P = np.asarray(st["points"], dtype=float)
        strokes.append(np.stack([P[:, 0] / xh, (base - P[:, 1]) / xh, P[:, 2]],
                                axis=1))
    x0 = min(float(s[:, 0].min()) for s in strokes)
    for s in strokes:
        s[:, 0] -= x0
    return strokes


def dedupe(P, eps=1e-9):
    keep = [0]
    for i in range(1, len(P)):
        if math.hypot(P[i, 0] - P[keep[-1], 0], P[i, 1] - P[keep[-1], 1]) > eps:
            keep.append(i)
    return P[keep] if len(keep) > 1 else P[:1]


def arclen(P):
    if len(P) < 2:
        return 0.0
    return float(np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1])).sum())


def resample(P, n):
    """Uniform resampling by arc length, carrying every column."""
    P = dedupe(P)
    if len(P) < 2:
        return np.repeat(P[:1], n, axis=0)
    d = np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))
    s = np.concatenate([[0.0], np.cumsum(d)])
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, k]) for k in range(P.shape[1])],
                    axis=1)


# --------------------------------------------------------------------------
# Segmentation: which stroke is which part of "Alyvų g. 4"
# --------------------------------------------------------------------------


def stroke_facts(P):
    x0, x1 = float(P[:, 0].min()), float(P[:, 0].max())
    y0, y1 = float(P[:, 1].min()), float(P[:, 1].max())
    return {"x0": x0, "x1": x1, "y0": y0, "y1": y1,
            "w": x1 - x0, "h": y1 - y0, "len": arclen(P)}


def split_blocks(strokes, gap=0.34):
    """Group strokes into words/glyph clusters by gaps along x."""
    order = sorted(range(len(strokes)), key=lambda i: strokes[i][:, 0].min())
    blocks, cur, reach = [], [], None
    for i in order:
        f = stroke_facts(strokes[i])
        if cur and f["x0"] - reach > gap:
            blocks.append(cur)
            cur, reach = [], None
        cur.append(i)
        reach = f["x1"] if reach is None else max(reach, f["x1"])
    if cur:
        blocks.append(cur)
    return blocks


def classify(strokes):
    """Assign every stroke a role. Returns {role: [stroke indices]}."""
    blocks = split_blocks(strokes)
    if len(blocks) < 3:
        raise ValueError("expected three clusters (Alyvų / g. / 4), got %d"
                         % len(blocks))
    # Widest-spanning cluster on the left is the word; last is the 4.
    word, mid, four = blocks[0], blocks[1], blocks[-1]
    if len(blocks) > 3:                      # stray cluster -> merge into mid
        for extra in blocks[2:-1]:
            mid = mid + extra
    roles = {r: [] for r in ROLES}
    facts = {i: stroke_facts(strokes[i]) for i in range(len(strokes))}

    word_x1 = max(facts[i]["x1"] for i in word)
    for i in word:
        f = facts[i]
        flat = f["h"] < 0.34 * f["w"] and f["len"] < 1.2
        low_right = (f["x0"] > word_x1 - 0.9 and f["y0"] < -0.03
                     and f["len"] < 1.2)
        if flat and not low_right:
            roles["crossbar"].append(i)
        elif low_right:
            roles["ogonek"].append(i)
        else:
            roles["body"].append(i)

    for i in mid:
        f = facts[i]
        if f["len"] < 0.3 and f["w"] < 0.3:
            roles["period"].append(i)
        else:
            roles["g"].append(i)
    # The period is the rightmost tiny mark; if several were caught, keep one.
    if len(roles["period"]) > 1:
        roles["period"].sort(key=lambda i: facts[i]["x0"])
        roles["g"].extend(roles["period"][:-1])
        roles["period"] = roles["period"][-1:]

    roles["four"] = list(four)
    roles["body"].sort()                     # writing order
    roles["g"].sort()
    roles["four"].sort(key=lambda i: facts[i]["x0"])
    return roles


def role_paths(strokes, roles):
    return {r: [strokes[i] for i in idx] for r, idx in roles.items() if idx}


# --------------------------------------------------------------------------
# Joining pen-lifts: a straight bridge, written faintly
# --------------------------------------------------------------------------


def bridge(parts, spacing, pressure_factor):
    """Concatenate strokes into one path, filling pen-up gaps with ink."""
    out = [parts[0]]
    for prev, nxt in zip(parts, parts[1:]):
        a, b = prev[-1], nxt[0]
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(2, int(round(d / max(spacing, 1e-6))))
        t = np.linspace(0.0, 1.0, n + 1)[1:-1]
        if len(t):
            seg = np.stack([a[0] + (b[0] - a[0]) * t,
                            a[1] + (b[1] - a[1]) * t,
                            (a[2] + (b[2] - a[2]) * t) * pressure_factor],
                           axis=1)
            out.append(seg)
        out.append(nxt)
    return np.concatenate(out, axis=0)


# --------------------------------------------------------------------------
# Slant
# --------------------------------------------------------------------------


def slant(strokes, min_dy=0.55, aspect=1.8, straightness=1.25):
    """Weighted-median lean of this writer's straight ascenders/stems.

    Whole-stroke chord direction (first point to last), not per-segment
    diffs -- cursive curves make per-segment angles far too noisy. Only
    strokes that are tall, steep and nearly straight qualify (a loopy 'g'
    or a flat crossbar should never vote on the slant); weight is how much
    vertical distance each stroke covers, so a short stem doesn't outvote
    a long one. Returns radians, positive leaning right, 0.0 if nothing
    in `strokes` qualifies.
    """
    angles, weights = [], []
    for P in strokes:
        dx, dy = float(P[-1, 0] - P[0, 0]), float(P[-1, 1] - P[0, 1])
        length = arclen(P)
        chord = math.hypot(dx, dy)
        if (abs(dy) < min_dy or abs(dy) < aspect * abs(dx)
                or length > straightness * max(chord, 1e-6)):
            continue
        if dy < 0:
            dx, dy = -dx, -dy
        angles.append(math.atan2(dx, dy))
        weights.append(abs(dy))
    if not angles:
        return 0.0
    a = np.array(angles)
    w = np.array(weights)
    order = np.argsort(a)
    a, w = a[order], w[order]
    c = np.cumsum(w)
    return float(a[int(np.searchsorted(c, c[-1] / 2.0))])


def shear(P, theta):
    """Lean the writing by theta about the baseline (y = 0)."""
    out = P.copy()
    out[:, 0] = P[:, 0] + math.tan(theta) * P[:, 1]
    return out


# --------------------------------------------------------------------------
# Correspondence and blending
# --------------------------------------------------------------------------


def unit_box(P):
    """Copy of P scaled into [0,1]^2 -- for matching only, never for output."""
    Q = P[:, :2].astype(float).copy()
    for k in (0, 1):
        lo, hi = Q[:, k].min(), Q[:, k].max()
        Q[:, k] = (Q[:, k] - lo) / (hi - lo) if hi - lo > 1e-9 else 0.5
    return Q


def dtw_pairs(A, B, band=0.18, x_weight=1.6):
    """Monotonic point-to-point match inside a Sakoe-Chiba band."""
    n, m = len(A), len(B)
    w = max(int(band * max(n, m)), abs(n - m) + 2)
    INF = float("inf")
    D = np.full((n + 1, m + 1), INF)
    D[0, 0] = 0.0
    for i in range(1, n + 1):
        centre = int(round(i * m / n))
        lo, hi = max(1, centre - w), min(m, centre + w)
        dx = (B[lo - 1:hi, 0] - A[i - 1, 0]) * x_weight
        dy = B[lo - 1:hi, 1] - A[i - 1, 1]
        cost = np.hypot(dx, dy)
        prev, cur = D[i - 1], D[i]
        for j in range(lo, hi + 1):
            cur[j] = cost[j - lo] + min(prev[j], cur[j - 1], prev[j - 1])
    pairs, i, j = [], n, m
    while i > 0 and j > 0:
        pairs.append((i - 1, j - 1))
        step = min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
        if step == D[i - 1, j - 1]:
            i, j = i - 1, j - 1
        elif step == D[i - 1, j]:
            i -= 1
        else:
            j -= 1
    while i > 0:
        pairs.append((i - 1, 0)); i -= 1
    while j > 0:
        pairs.append((0, j - 1)); j -= 1
    return pairs[::-1]


def blend_paths(A, B, w, samples, band, x_weight):
    """Average two paths point-for-point once they've been matched up."""
    A = resample(A, samples)
    B = resample(B, samples)
    pairs = dtw_pairs(unit_box(A), unit_box(B), band, x_weight)
    ai = np.array([p[0] for p in pairs])
    bi = np.array([p[1] for p in pairs])
    mixed = (1.0 - w) * A[ai] + w * B[bi]
    return resample(mixed, samples)


def smooth(P, window):
    """Light moving average; endpoints stay put."""
    if window < 3 or len(P) < window:
        return P
    if window % 2 == 0:
        window += 1
    k = np.ones(window) / window
    out = P.copy()
    for c in (0, 1, 2):
        pad = np.concatenate([np.repeat(P[:1, c], window // 2), P[:, c],
                              np.repeat(P[-1:, c], window // 2)])
        out[:, c] = np.convolve(pad, k, mode="valid")
    out[0], out[-1] = P[0], P[-1]
    return out


# --------------------------------------------------------------------------
# Per-writer template: average this writer's own repeats, role by role
# --------------------------------------------------------------------------


def canonical_direction(P):
    """Make direction-of-drawing consistent across writers and samples.

    Two people can draw the same little mark (a crossbar, a dot) in opposite
    pen directions -- one left-to-right, the other right-to-left. Point-index
    correspondence (DTW, or even a plain average) then matches one writer's
    start to the other's end and produces a crossed-out zigzag instead of a
    blend. Reorienting every instance the same way -- along whichever axis
    the stroke actually travels along -- fixes that before any matching or
    averaging happens; the shape is unchanged, only which end is "first".
    """
    dx, dy = float(P[-1, 0] - P[0, 0]), float(P[-1, 1] - P[0, 1])
    backwards = dx < 0 if abs(dx) >= abs(dy) else dy < 0
    return P[::-1].copy() if backwards else P


def split_lobes(P, min_frac=0.08):
    """Split a path into above-/below-baseline runs (merging tiny crossings).

    A "g" is really two loops -- a bowl above the baseline, a tail below it
    -- joined by a stem, and the two writers can trace bowl-then-tail or
    tail-then-bowl, spending very different fractions of their pen time on
    each. Point-index correspondence (DTW included) has no way to know
    that "halfway along the path" means the middle of the bowl for one
    writer and the middle of the tail loop for the other, so it matches
    unrelated parts of the two loops and the blend collapses. Matching the
    bowl to the bowl and the tail to the tail -- using the one landmark
    every cursive letter agrees on, the baseline -- fixes that. Returns
    (above_or_none, below_or_none), each a concatenation of that side's
    runs in original path order.
    """
    y = P[:, 1]
    sign = np.where(y >= 0, 1, -1)
    total = arclen(P)
    cuts = [0] + [i for i in range(1, len(P)) if sign[i] != sign[i - 1]] + [len(P)]
    runs = [(sign[a], P[a:b]) for a, b in zip(cuts, cuts[1:]) if b > a]
    merged = []
    for s_, chunk in runs:
        if merged and arclen(chunk) < min_frac * total:
            merged[-1] = (merged[-1][0], np.concatenate([merged[-1][1], chunk]))
        else:
            merged.append((s_, chunk))
    above = [c for s_, c in merged if s_ > 0]
    below = [c for s_, c in merged if s_ < 0]
    cat = lambda parts: np.concatenate(parts) if parts else None
    return cat(above), cat(below)


def best_stitch(path_a, path_b, spacing, tail_factor):
    """Join two independently-built paths, picking whichever end-pairing
    and orientation makes for the shortest connecting bridge."""
    options = []
    for first, second in ((path_a, path_b), (path_b, path_a)):
        for f in (first, first[::-1]):
            for g in (second, second[::-1]):
                gap = math.hypot(g[0, 0] - f[-1, 0], g[0, 1] - f[-1, 1])
                options.append((gap, f, g))
    _, f, g = min(options, key=lambda o: o[0])
    return bridge([f, g], spacing, tail_factor)


def bridged_role_instances(samples, role, spacing=0.02, tail_factor=0.35):
    """One bridged, upright-corrected path per sample that has this role."""
    out = []
    for strokes, roles, theta in samples:
        idx = roles.get(role)
        if not idx:
            continue
        parts = [dedupe(strokes[i][:, :3]) for i in idx]
        path = bridge(parts, spacing, tail_factor) if len(parts) > 1 else parts[0]
        out.append(canonical_direction(shear(path, -theta)))
    return out


def average_role(instances, n):
    if not instances:
        return None
    if len(instances) == 1:
        return resample(instances[0], n)
    stack = np.stack([resample(p, n) for p in instances], axis=0)
    return stack.mean(axis=0)


def writer_template(samples_for_writer, n=220):
    """samples_for_writer: list of (strokes, roles) for one writer.

    Returns (theta, {role: (n,3) averaged upright path}).
    """
    all_strokes = [st for strokes, _ in samples_for_writer for st in strokes]
    theta = slant(all_strokes)
    tagged = [(strokes, roles, theta) for strokes, roles in samples_for_writer]
    template = {}
    for role in ROLES:
        instances = bridged_role_instances(tagged, role)
        if not instances:
            continue
        if role in LOBE_ROLES:
            aboves, belows = [], []
            for inst in instances:
                above, below = split_lobes(inst)
                if above is not None:
                    aboves.append(canonical_direction(above))
                if below is not None:
                    belows.append(canonical_direction(below))
            avg_above = average_role(aboves, n)
            avg_below = average_role(belows, n)
            if avg_above is not None:
                template[role + "__above"] = avg_above
            if avg_below is not None:
                template[role + "__below"] = avg_below
        else:
            avg = average_role(instances, n)
            if avg is not None:
                template[role] = avg
    return theta, template


# --------------------------------------------------------------------------
# Pressure -> stroke width, and width -> a fillable ribbon polygon
# --------------------------------------------------------------------------


def width_for(pressure, w_min, w_max, gamma):
    return w_min + (w_max - w_min) * np.clip(pressure, 0.0, 1.0) ** gamma


def _round_cap(center, tangent, radius, at_start, n=10):
    """Points for a semicircular cap, tangent-aligned, radius `radius`."""
    ang0 = math.atan2(tangent[1], tangent[0]) + (math.pi if at_start else 0.0)
    return [(center[0] + radius * math.cos(ang0 + math.pi * t / n),
            center[1] + radius * math.sin(ang0 + math.pi * t / n))
            for t in range(n + 1)]


def stroke_polygon(path, widths, cap_segments=10):
    """A centreline + per-point width -> one closed, fillable polygon.

    `path` is (N,2) in the final (already-scaled) coordinate system.
    Degenerates to a filled circle if the path barely has any length --
    e.g. a period.
    """
    P = np.asarray(path, dtype=float)
    total = arclen(np.column_stack([P, np.zeros(len(P))]))
    if total < float(np.mean(widths)) * 0.6 or len(P) < 2:
        cx, cy = float(P[:, 0].mean()), float(P[:, 1].mean())
        r = max(float(np.mean(widths)) / 2.0, 1e-3)
        n = 20
        return [(cx + r * math.cos(2 * math.pi * k / n),
                cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]

    tang = np.zeros_like(P)
    tang[1:-1] = P[2:] - P[:-2]
    tang[0] = P[1] - P[0]
    tang[-1] = P[-1] - P[-2]
    norm = np.hypot(tang[:, 0], tang[:, 1])
    norm[norm < 1e-9] = 1.0
    tang = tang / norm[:, None]
    normal = np.stack([-tang[:, 1], tang[:, 0]], axis=1)

    left = P + normal * (widths[:, None] / 2.0)
    right = P - normal * (widths[:, None] / 2.0)

    poly = list(map(tuple, left))
    poly += _round_cap(tuple(P[-1]), tuple(tang[-1]), widths[-1] / 2.0,
                       at_start=False, n=cap_segments)
    poly += list(map(tuple, right[::-1]))
    poly += _round_cap(tuple(P[0]), tuple(tang[0]), widths[0] / 2.0,
                       at_start=True, n=cap_segments)
    return poly


# --------------------------------------------------------------------------
# Putting it together: two writers -> one blended, sized, widthed drawing
# --------------------------------------------------------------------------


class Blend:
    """Everything downstream (SVG, stats) needs from a finished blend."""

    def __init__(self, roles_mm, theta, scale, thetas, samples_per_role):
        self.roles_mm = roles_mm            # role -> (N,3) [x_mm, y_mm, pressure]
        self.theta = theta
        self.scale = scale                  # x-height-units -> mm
        self.writer_thetas = thetas
        self.n = samples_per_role

    def bbox_mm(self):
        xs = np.concatenate([p[:, 0] for p in self.roles_mm.values()])
        ys = np.concatenate([p[:, 1] for p in self.roles_mm.values()])
        return float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())


def blend_writers(template_a, template_b, weight, height_mm, n=220,
                  band=0.18, x_weight=1.6):
    theta_a, tpl_a = template_a
    theta_b, tpl_b = template_b
    theta = (1.0 - weight) * theta_a + weight * theta_b

    def blend_one(a, b):
        if a is None and b is None:
            return None
        if a is None:
            return b
        if b is None:
            return a
        return blend_paths(a, b, weight, n, band, x_weight)

    blended = {}
    for role in ROLES:
        if role in LOBE_ROLES:
            above = blend_one(tpl_a.get(role + "__above"),
                              tpl_b.get(role + "__above"))
            below = blend_one(tpl_a.get(role + "__below"),
                              tpl_b.get(role + "__below"))
            if above is None and below is None:
                continue
            path = (best_stitch(above, below, spacing=0.02, tail_factor=0.35)
                    if above is not None and below is not None
                    else (above if above is not None else below))
        elif role in tpl_a or role in tpl_b:
            path = blend_one(tpl_a.get(role), tpl_b.get(role))
        else:
            continue
        blended[role] = shear(path, theta)

    y0 = min(float(p[:, 1].min()) for p in blended.values())
    y1 = max(float(p[:, 1].max()) for p in blended.values())
    scale = height_mm / max(1e-6, (y1 - y0))
    roles_mm = {r: p * np.array([scale, scale, 1.0]) for r, p in blended.items()}
    return Blend(roles_mm, theta, scale, (theta_a, theta_b), n)


# --------------------------------------------------------------------------
# SVG export
# --------------------------------------------------------------------------

SVG_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'width="%.2fmm" height="%.2fmm" viewBox="%.3f %.3f %.3f %.3f">\n'
)


def poly_path_d(points):
    it = iter(points)
    x0, y0 = next(it)
    d = ["M %.3f,%.3f" % (x0, y0)]
    d += ["L %.3f,%.3f" % (x, y) for x, y in it]
    d.append("Z")
    return " ".join(d)


def centreline_segments(path, widths, flip_y):
    """Short round-capped line segments approximating a variable-width stroke."""
    out = []
    for a, b, wa, wb in zip(path, path[1:], widths, widths[1:]):
        ya = -a[1] if flip_y else a[1]
        yb = -b[1] if flip_y else b[1]
        out.append((a[0], ya, b[0], yb, (wa + wb) / 2.0))
    return out


def write_plate_svg(blend, dest, margin_mm, w_min, w_max, gamma, outline=True):
    x0, y0, x1, y1 = blend.bbox_mm()
    x0 -= margin_mm; y0 -= margin_mm; x1 += margin_mm; y1 += margin_mm
    width, height = x1 - x0, y1 - y0
    # SVG y grows down; our geometry has y up. Flip once, here, on export.
    vb = (x0, -y1, width, height)

    parts = [SVG_HEADER % (width, height, vb[0], vb[1], vb[2], vb[3])]
    parts.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" '
                 'fill="#ffffff"/>\n' % (vb[0], vb[1], vb[2], vb[3]))

    parts.append('<g id="guides" fill="none" stroke="#cfd8e3" '
                 'stroke-width="0.15" display="none">\n')
    parts.append('<line x1="%.3f" y1="0" x2="%.3f" y2="0"/>\n' % (x0, x1))
    parts.append("</g>\n")

    parts.append('<g id="centreline" fill="none" stroke="#14110d" '
                 'stroke-linecap="round">\n')
    for role in ROLES:
        if role not in blend.roles_mm:
            continue
        P = blend.roles_mm[role]
        widths = width_for(P[:, 2], w_min, w_max, gamma)
        for xa, ya, xb, yb, w in centreline_segments(P, widths, flip_y=True):
            parts.append('<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" '
                         'stroke-width="%.3f"/>\n' % (xa, ya, xb, yb, w))
    parts.append("</g>\n")

    if outline:
        parts.append('<g id="outline" fill="#14110d" stroke="none" '
                     'fill-rule="nonzero">\n')
        for role in ROLES:
            if role not in blend.roles_mm:
                continue
            P = blend.roles_mm[role]
            widths = width_for(P[:, 2], w_min, w_max, gamma)
            poly = stroke_polygon(P[:, :2], widths)
            poly = [(x, -y) for x, y in poly]
            parts.append('<path d="%s"/>\n' % poly_path_d(poly))
        parts.append("</g>\n")

    parts.append("</svg>\n")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))


def write_compare_svg(dest, entries, w_min, w_max, gamma, px_per_unit=90.0,
                      stroke_px_per_mm=4.0):
    """entries: list of (label, colour, {role: (N,3)}, extra_scale).

    Every entry here is in x-height units, not millimetres -- this SVG is a
    diagnostic side-by-side, not the manufacturable plate. Position and
    stroke width are unrelated quantities here (`px_per_unit` blows a
    ~1-unit-tall letter up to something visible; `stroke_px_per_mm` is an
    independent, small px-per-real-mm for the width_for() output, which is
    already in millimetres) -- multiplying width by px_per_unit instead
    would draw a 1.2mm stroke over a hundred pixels wide.
    """
    rows = []
    for label, colour, roles, s in entries:
        pts = np.concatenate([p for p in roles.values()], axis=0)
        x0 = float(pts[:, 0].min()) * s
        x1 = float(pts[:, 0].max()) * s
        y0 = float(pts[:, 1].min()) * s
        y1 = float(pts[:, 1].max()) * s
        rows.append((label, colour, roles, s, x0, y0, x1, y1))

    pad = 10
    y1_max = max(r[7] for r in rows)          # tallest ascender, any writer
    y0_min = min(r[5] for r in rows)          # lowest descender, any writer
    row_h = (y1_max - y0_min) * px_per_unit + 2 * pad + 24
    width = max(r[6] - r[4] for r in rows) * px_per_unit + 2 * pad
    height = row_h * len(rows)

    out = ['<?xml version="1.0" encoding="UTF-8"?>\n',
          '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
          'viewBox="0 0 %d %d">\n' % (width, height, width, height),
          '<rect width="100%%" height="100%%" fill="#ffffff"/>\n']
    y_cursor = 0
    for label, colour, roles, s, x0, y0, x1, y1 in rows:
        base_y = y_cursor + pad + 24 + y1_max * px_per_unit
        out.append('<text x="10" y="%.1f" font-family="sans-serif" '
                   'font-size="13" fill="#666">%s</text>\n' % (y_cursor + 16, label))
        out.append('<line x1="0" y1="%.2f" x2="%.2f" y2="%.2f" '
                   'stroke="#e2e2e2"/>\n' % (base_y, width, base_y))
        out.append('<g fill="none" stroke="%s" stroke-linecap="round">\n' % colour)
        for role in ROLES:
            if role not in roles:
                continue
            P = roles[role] * s * px_per_unit
            # width_for() is already in mm, independent of the letter
            # scale `s`; only the (separate, small) px-per-mm display scale
            # applies to it -- see the docstring above.
            widths = width_for(roles[role][:, 2], w_min, w_max, gamma) \
                * stroke_px_per_mm
            for a, b, wa, wb in zip(P, P[1:], widths, widths[1:]):
                out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" '
                           'stroke-width="%.2f"/>\n'
                           % (pad + a[0], base_y - a[1], pad + b[0],
                              base_y - b[1], (wa + wb) / 2.0))
        out.append("</g>\n")
        y_cursor += row_h
    out.append("</svg>\n")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("".join(out))


# --------------------------------------------------------------------------
# Report + CLI
# --------------------------------------------------------------------------


def load_writers(path):
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    by_writer = {}
    for s in sorted(doc["samples"], key=lambda s: (s["writer"], s["index"])):
        strokes = normalise(s)
        try:
            roles = classify(strokes)
        except ValueError as exc:
            print("warning: %s #%d -- %s -- skipped"
                  % (s["writer"], s["index"], exc), file=sys.stderr)
            continue
        by_writer.setdefault(s["writer"], []).append((strokes, roles, s))
    return doc, by_writer


def report(writer, samples, theta, template):
    n = len(samples)
    pts = sum(sum(len(st["points"]) for st in s["strokes"]) for _, _, s in samples)
    mean_p = float(np.mean([p for _, _, s in samples
                            for st in s["strokes"] for p in [pt[2] for pt in st["points"]]]))
    peak_p = max(pt[2] for _, _, s in samples for st in s["strokes"]
                for pt in st["points"])
    ink_s = sum(s.get("duration_ms", 0.0) for _, _, s in samples) / 1000.0
    mouse = [s["index"] for _, _, s in samples if s.get("input") == "mouse"]
    def has_role(r):
        if r in LOBE_ROLES:
            return (r + "__above") in template or (r + "__below") in template
        return r in template
    missing = [r for r in ROLES if not has_role(r)]
    print("  %s: %d sample(s), %d strokes total, %d points, "
         "pressure mean %.2f / peak %.2f, %.1fs ink, slant %.1f deg"
         % (writer, n, sum(len(roles) for _, roles, _ in samples), pts,
            mean_p, peak_p, ink_s, math.degrees(theta)))
    if mouse:
        print("    caution: sample(s) %s used a mouse, not the pen -- their "
             "pressure is synthetic" % mouse)
    if missing:
        print("    note: no clean %s found in any sample" % ", ".join(missing))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Blend two writers' capture of the same cursive text "
                    "into one address-plate SVG.")
    ap.add_argument("file", nargs="?",
                    default=os.path.join(os.path.dirname(__file__), os.pardir,
                                        "alyvu_g4_handwriting.json"),
                    help="capture file from capture_handwriting.py")
    ap.add_argument("--weight", type=float, default=0.5,
                    help="0.0 = first writer only, 1.0 = second writer only, "
                        "0.5 = even blend (default: %(default)s)")
    ap.add_argument("--height-mm", type=float, default=60.0,
                    help="overall letter-block height, ascender to descender, "
                        "in millimetres (default: %(default)s)")
    ap.add_argument("--stroke-min-mm", type=float, default=1.2,
                    help="stroke width at the lightest pressure (default: "
                        "%(default)s)")
    ap.add_argument("--stroke-max-mm", type=float, default=3.2,
                    help="stroke width at full pressure (default: %(default)s)")
    ap.add_argument("--gamma", type=float, default=1.0,
                    help="pressure-to-width curve; >1 favours thin strokes, "
                        "<1 favours thick ones (default: %(default)s)")
    ap.add_argument("--margin-mm", type=float, default=12.0,
                    help="white space around the text (default: %(default)s)")
    ap.add_argument("--no-outline", action="store_true",
                    help="skip the filled cuttable outline layer")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "alyvu_g4.svg"))
    ap.add_argument("--compare-out", default=os.path.join(
        os.path.dirname(__file__), "compare.svg"))
    args = ap.parse_args(argv)

    doc, by_writer = load_writers(args.file)
    writers = sorted(by_writer)
    if len(writers) < 2:
        print("error: need two writers in %s, found %s"
             % (args.file, writers or "none"), file=sys.stderr)
        return 1
    if len(writers) > 2:
        print("note: %d writers found (%s) -- using the first two: %s"
             % (len(writers), ", ".join(writers), ", ".join(writers[:2])))
        writers = writers[:2]

    print('target text: "%s"' % doc.get("target_text", TARGET_TEXT_DEFAULT))
    print("writers:")
    templates = {}
    for w in writers:
        samples = by_writer[w]
        theta, tpl = writer_template([(s, r) for s, r, _ in samples])
        templates[w] = (theta, tpl)
        report(w, samples, theta, tpl)

    blend = blend_writers(templates[writers[0]], templates[writers[1]],
                          args.weight, args.height_mm)

    write_plate_svg(blend, args.out, args.margin_mm, args.stroke_min_mm,
                    args.stroke_max_mm, args.gamma, outline=not args.no_outline)

    thin = args.stroke_min_mm
    if thin < 1.0:
        print("warning: --stroke-min-mm %.2f is thinner than the 1.0mm most "
             "laser/CNC engraving can hold" % thin)

    compare_entries = []
    palette = {writers[0]: "#c0392b", writers[1]: "#2c5fa8"}
    for w in writers:
        theta_w, tpl_w = templates[w]
        upright_back = {r: shear(p, theta_w) for r, p in tpl_w.items()}
        compare_entries.append((w, palette[w], upright_back, 1.0))
    xy_scale = np.array([1.0 / blend.scale, 1.0 / blend.scale, 1.0])
    blend_for_compare = {r: p * xy_scale for r, p in blend.roles_mm.items()}
    compare_entries.append(("blend (weight=%.2f)" % args.weight, "#14110d",
                            blend_for_compare, 1.0))
    write_compare_svg(args.compare_out, compare_entries, args.stroke_min_mm,
                      args.stroke_max_mm, args.gamma)

    x0, y0, x1, y1 = blend.bbox_mm()
    print("\nwrote %s  (%.0f x %.0f mm, weight=%.2f, slant %.1f deg)"
         % (args.out, x1 - x0, y1 - y0, args.weight, math.degrees(blend.theta)))
    print("wrote %s" % args.compare_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
