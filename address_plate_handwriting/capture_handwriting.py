#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handwriting capture for a two-hand address plate.

Two people write the same thing -- by default "Alyvų g. 4" -- on an XP-Pen
Artist 15.6 (V2) or any other pressure-sensitive tablet. This records every
pen position, how hard you pressed and how fast you moved, and saves it all
into one file that also carries its own prompt for Claude Code. Hand that
file to Claude Code and it blends the two hands into one piece of joined-up
cursive for the plate.

Just run it. There is nothing to type: the window walks you through it.

    python3 capture_handwriting.py

(or double-click the script, or the start_windows.bat / start_mac_linux.command
launcher next to it). If Qt is missing, the app offers to install it for you.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

SCHEMA = "handwriting-capture/v2"
TARGET_TEXT_DEFAULT = "Alyvų g. 4"          # "Alyvų g. 4"
DEFAULT_OUT = "alyvu_g4_handwriting.json"
POINT_FORMAT = ["x", "y", "p", "t", "tx", "ty"]
DEVICE_HINT = "XP-Pen Artist 15.6 (V2) -- 1920x1080, 8192 pressure levels"

# --------------------------------------------------------------------------
# Qt binding shim: PySide6 / PyQt6 / PyQt5 all expose tablet events, but they
# disagree about scoped enums and about the name of the sub-pixel position.
# --------------------------------------------------------------------------

QT_BINDING = None
QtCore = QtGui = QtWidgets = None
for _name, _imp in (
    ("PySide6", "PySide6"),
    ("PyQt6", "PyQt6"),
    ("PyQt5", "PyQt5"),
):
    try:
        _mod = __import__(_imp, fromlist=["QtCore", "QtGui", "QtWidgets"])
        QtCore, QtGui, QtWidgets = _mod.QtCore, _mod.QtGui, _mod.QtWidgets
        QT_BINDING = _name
        break
    except ImportError:
        continue


class _Enums:
    """Flatten Qt5's unscoped enums and Qt6's scoped ones behind one namespace."""

    def __init__(self, root):
        object.__setattr__(self, "_root", root)

    def __getattr__(self, name):
        root = object.__getattribute__(self, "_root")
        value = getattr(root, name, None)
        if value is None:
            for attr in dir(root):
                holder = getattr(root, attr, None)
                if isinstance(holder, type) and hasattr(holder, name):
                    value = getattr(holder, name)
                    break
        if value is None:
            raise AttributeError("%r has no enum member %r" % (root, name))
        object.__setattr__(self, name, value)
        return value


def _event_pos(ev):
    """Sub-pixel widget-local position, Qt5 (posF) and Qt6 (position)."""
    for getter in ("position", "posF", "pos"):
        fn = getattr(ev, getter, None)
        if fn is None:
            continue
        p = fn()
        return float(p.x()), float(p.y())
    raise AttributeError("event has no position accessor")


def _pointer_name(ev):
    fn = getattr(ev, "pointerType", None)
    if fn is None:
        return "pen"
    try:
        raw = fn()
    except TypeError:
        return "pen"
    name = getattr(raw, "name", None) or str(raw)
    name = name.rsplit(".", 1)[-1].lower()
    for known in ("eraser", "cursor", "pen"):
        if known in name:
            return known
    return name or "pen"


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------
# The prompt that ships inside the capture file
# --------------------------------------------------------------------------

def build_prompt(target_text, filename):
    """Return the Claude Code prompt as a list of lines (readable inside JSON)."""
    return [
        "# PROMPT FOR CLAUDE CODE",
        "",
        "Read this entire JSON file first, then carry out the task below.",
        "",
        "## What this file is",
        "",
        "`%s` is a raw digitiser capture from an XP-Pen Artist 15.6 (V2) pen" % filename,
        "display. Two people (see `writers`) each hand-wrote the same text,",
        "\"%s\", in Lithuanian CURSIVE (rašytinėmis, not spausdintinėmis)," % target_text,
        "several times each. Nothing has been smoothed, resampled or cleaned.",
        "",
        "## The goal",
        "",
        "Produce ONE piece of joined-up cursive that is a genuine fusion of BOTH",
        "hands -- not writer A's word next to writer B's word, not one hand with the",
        "other's flourishes bolted on, and not a script font. Every letter must be a",
        "blend of the two: shared skeleton, shared slant, shared connecting strokes.",
        "The result is the engraved face of a house address plate, so it has to be",
        "manufacturable, not just a picture.",
        "",
        "## File layout",
        "",
        "  schema          format id",
        "  target_text     the text both writers wrote",
        "  device          which tablet produced this",
        "  canvas          width_px / height_px / px_per_mm / dpi diagnostics",
        "  guides          baseline, x-height, ascender, descender in canvas px",
        "  samples[i].guides / .canvas  the geometry that sample was actually",
        "                  written against -- ALWAYS use the sample's own copy,",
        "                  the top-level one is just the most recent window",
        "  point_format    the meaning of each number in a point tuple",
        "  writers         per-writer summary (sample count, tablet or mouse)",
        "  samples[]       every capture: writer, index, input, duration_ms,",
        "                  strokes[] -> points[] -> [x, y, p, t, tx, ty]",
        "",
        "  x, y   canvas pixels, y grows DOWNWARD (screen convention). Flip y for",
        "         SVG-up or CAD. `canvas.px_per_mm` converts to millimetres; it is",
        "         derived from the reported display DPI, so treat it as approximate",
        "         and drive the final size from `--height-mm`, not from it.",
        "  p      pen pressure, 0.0 .. 1.0. If a sample's `input` is \"mouse\" the",
        "         pressure is synthetic and constant -- use that sample for geometry",
        "         only, never for width modulation.",
        "  t      milliseconds since the start of that sample. Gives you velocity",
        "         (for velocity-based thinning) and keeps stroke order and direction.",
        "  tx, ty pen tilt in degrees, may be 0 if the driver does not report it.",
        "",
        "## Method -- follow this order, do not skip the alignment step",
        "",
        "1. Parse and normalise. For every sample: translate so the baseline is y=0,",
        "   flip y up, and scale so (baseline - x_height) == 1.0 using that",
        "   sample's own `guides` block (`x_height_px` is precomputed for you).",
        "   This puts both writers in the same space and is the single most",
        "   important step -- blending unnormalised strokes just gives mush.",
        "2. Pick one reference sample per writer: the one whose stroke count is the",
        "   modal count for that writer and whose normalised outline is closest to",
        "   that writer's mean. Say which you picked and why. Do not average a",
        "   writer's samples together before step 4 if their stroke counts differ.",
        "3. Segment each reference into letters/glyph groups by walking the stroke",
        "   order and the pen-up gaps: A / l / y / v / u-with-ogonek / g / . / 4,",
        "   plus the separate diacritic and punctuation marks.",
        "4. Build a correspondence between the two writers. Match glyph group to",
        "   glyph group first, then stroke to stroke inside a group, then point to",
        "   point with DTW over arc-length-resampled strokes (~200 samples each).",
        "   If stroke counts inside a group differ, concatenate that group's strokes",
        "   into one polyline with the pen-up gaps recorded, then DTW that.",
        "5. Blend: point = (1-w)*A + w*B, default w = 0.5, exposed as `--weight`.",
        "   Blend pressure the same way. Blend the global slant explicitly (measure",
        "   each writer's mean stroke angle, interpolate, re-skew) instead of hoping",
        "   the point average gets it right.",
        "6. Connect it. After blending, weld glyphs that cursive joins: if the end of",
        "   one glyph and the start of the next are within a threshold, fuse them",
        "   into a single continuous polyline; where a real join is implied but the",
        "   gap is large, insert a ligature arc tangent to both ends. Keep the",
        "   genuine pen-ups separate -- the dot of the i-like strokes, the ogonek",
        "   under u, the period after g, and the 4.",
        "7. Smooth with Chaikin or centripetal Catmull-Rom, lightly. Do NOT",
        "   oversmooth: the small wobble is what makes it read as handwriting.",
        "8. Width from pressure: width(s) = w_min + (w_max - w_min) * p(s)**gamma,",
        "   gamma default 1.0. Clamp to the minimum engravable width.",
        "9. Outline: offset each variable-width centreline into a closed polygon",
        "   (both sides plus round caps), union overlapping glyphs, so the plate can",
        "   be laser cut, CNC engraved or vinyl cut. Keep BOTH the centreline",
        "   version and the outlined version.",
        "",
        "## Deliverables -- write real files in this repo",
        "",
        "  plate/alyvu_g4.svg      mm units, correct physical size, layers:",
        "                          `guides` (hidden), `centreline`, `outline`",
        "  plate/compare.svg       writer A, writer B and the blend stacked on the",
        "                          same baseline, for eyeballing the fusion",
        "  plate/build_plate.py    deterministic regeneration from this JSON, flags:",
        "                          --weight --height-mm --plate-size --stroke-mm",
        "                          --gamma --outline/--no-outline",
        "  plate/README.md         what each parameter does and what to check",
        "                          before cutting",
        "",
        "## Constraints",
        "",
        "- Python 3, standard library + numpy only. No ML, no network, no font",
        "  files: every letterform must come from the capture, never from a font.",
        "- Deterministic: same JSON + same flags => byte-identical SVG.",
        "- Keep the Lithuanian text exact: u keeps its ogonek (u-nosine), A stays a",
        "  capital, \"g.\" keeps its period, and 4 is the handwritten digit from the",
        "  capture, not a font glyph.",
        "- State the minimum engraved stroke width you assumed (default 1.2 mm) in",
        "  the README, and warn if the blend goes thinner anywhere.",
        "- If a writer has only one usable sample, say so; never silently fall back",
        "  to the other writer's shape to fill a gap.",
        "",
        "## Report back first",
        "",
        "Before writing any output files, tell me, per writer: sample count, stroke",
        "count, point count, mean and peak pressure, total ink time, which sample",
        "you chose as the reference and why -- and flag anything that looks like a",
        "bad capture (stray dot, missing letter, mouse input).",
    ]


# --------------------------------------------------------------------------
# Capture file I/O
# --------------------------------------------------------------------------

def load_capture(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("schema") != SCHEMA:
        print("warning: %s has schema %r, expected %r -- merging anyway"
              % (path, data.get("schema"), SCHEMA), file=sys.stderr)
    data.setdefault("samples", [])
    return data


def summarise_writers(samples):
    writers = {}
    for s in samples:
        w = writers.setdefault(s["writer"], {
            "samples": 0, "strokes": 0, "points": 0, "input": set(),
        })
        w["samples"] += 1
        w["strokes"] += len(s["strokes"])
        w["points"] += sum(len(st["points"]) for st in s["strokes"])
        w["input"].add(s.get("input", "tablet"))
    for w in writers.values():
        w["input"] = "+".join(sorted(w.pop("input")))
    return writers


def write_capture(path, header, samples):
    doc = {"schema": SCHEMA}
    doc["claude_code_prompt"] = build_prompt(header["target_text"],
                                             os.path.basename(path))
    doc["target_text"] = header["target_text"]
    doc["device"] = header["device"]
    doc["captured_with"] = header["captured_with"]
    doc["updated_at"] = utcnow()
    doc["canvas"] = header["canvas"]
    doc["guides"] = header["guides"]
    doc["point_format"] = POINT_FORMAT
    doc["writers"] = summarise_writers(samples)
    doc["samples"] = samples

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)
    return doc


# --------------------------------------------------------------------------
# Offline modes: inspect / SVG preview (no Qt needed)
# --------------------------------------------------------------------------

def cmd_inspect(path):
    data = load_capture(path)
    if data is None:
        print("no such file: %s" % path, file=sys.stderr)
        return 1
    samples = data.get("samples", [])
    print("file        : %s" % path)
    print("schema      : %s" % data.get("schema"))
    print("target text : %s" % data.get("target_text"))
    print("device      : %s" % data.get("device"))
    print("updated     : %s" % data.get("updated_at"))
    print("samples     : %d" % len(samples))
    if not samples:
        print("\n(no samples yet)")
        return 0

    by_writer = {}
    for s in samples:
        by_writer.setdefault(s["writer"], []).append(s)

    for writer in sorted(by_writer):
        group = by_writer[writer]
        print("\nwriter: %s" % writer)
        for s in group:
            pressures = [p[2] for st in s["strokes"] for p in st["points"]]
            n = len(pressures) or 1
            mean_p = sum(pressures) / n
            print("  #%-2d  %2d strokes  %5d points  "
                  "p mean %.3f  p max %.3f  %6.1f s  input=%s"
                  % (s["index"], len(s["strokes"]), len(pressures), mean_p,
                     max(pressures) if pressures else 0.0,
                     s.get("duration_ms", 0) / 1000.0, s.get("input", "?")))
        counts = [len(s["strokes"]) for s in group]
        if len(set(counts)) > 1:
            print("  note: stroke counts differ %s -- fine, but Claude will have "
                  "to group strokes into letters before matching." % counts)
        if any(s.get("input") == "mouse" for s in group):
            print("  note: mouse samples present -- their pressure is synthetic.")

    missing = [w for w, g in by_writer.items() if len(g) < 2]
    if missing:
        print("\nonly one sample for: %s -- capture 2-3 more so a reference "
              "can be chosen." % ", ".join(missing))
    if len(by_writer) < 2:
        print("\nonly one writer so far. Run again with --writer <other name> "
              "to add the second hand to the same file.")
    return 0


def _svg_paths(strokes, dy, stroke_scale):
    """Emit polyline paths, grouped into runs of similar width."""
    out = []
    for st in strokes:
        pts = st["points"]
        if len(pts) < 2:
            if pts:
                a = pts[0]
                w = stroke_scale * (0.8 + 5.5 * a[2])
                out.append('<circle cx="%.2f" cy="%.2f" r="%.2f"/>'
                           % (a[0], a[1] + dy, w / 2.0))
            continue
        run = [pts[0]]
        run_w = None
        for a, b in zip(pts, pts[1:]):
            w = stroke_scale * (0.8 + 5.5 * (0.5 * (a[2] + b[2])))
            bucket = round(w * 4.0) / 4.0
            if run_w is None:
                run_w = bucket
            if bucket != run_w:
                d = " ".join("%.2f,%.2f" % (p[0], p[1] + dy) for p in run)
                out.append('<polyline points="%s" stroke-width="%.2f"/>'
                           % (d, run_w))
                run = [run[-1]]
                run_w = bucket
            run.append(b)
        if len(run) > 1:
            d = " ".join("%.2f,%.2f" % (p[0], p[1] + dy) for p in run)
            out.append('<polyline points="%s" stroke-width="%.2f"/>' % (d, run_w))
    return out


def render_svg(data, dest, stroke_scale=1.0):
    """Draw every captured sample, one per row, into an SVG file."""
    samples = sorted(data.get("samples", []),
                     key=lambda s: (s["writer"], s["index"]))
    width = max(s.get("canvas", {}).get("width_px", 1600) for s in samples)
    row_h = max(s.get("canvas", {}).get("height_px", 620) for s in samples)
    height = row_h * len(samples)

    body = []
    for i, s in enumerate(samples):
        dy = i * row_h
        g = s.get("guides") or data.get("guides") or {}
        body.append('<g id="%s-%d">' % (s["writer"], s["index"]))
        if "baseline_y_px" in g:
            body.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                        'stroke="#c8d3de" stroke-width="1" fill="none"/>'
                        % (g.get("left_px", 0), g["baseline_y_px"] + dy,
                           g.get("right_px", width), g["baseline_y_px"] + dy))
        body.append('<text x="20" y="%.1f" font-family="monospace" '
                    'font-size="14" fill="#8a94a0">%s #%d (%s)</text>'
                    % (dy + 24, s["writer"], s["index"], s.get("input", "?")))
        body.append('<g fill="none" stroke="#14110d" stroke-linecap="round" '
                    'stroke-linejoin="round">')
        body.extend(_svg_paths(s["strokes"], dy, stroke_scale))
        body.append("</g>")
        body.append("</g>")

    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d">\n'
        '<rect width="100%%" height="100%%" fill="#faf9f5"/>\n%s\n</svg>\n'
        % (width, height, width, height, "\n".join(body))
    )
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(svg)
    return len(samples)


def cmd_svg(src, dest, stroke_scale=1.0):
    data = load_capture(src)
    if data is None:
        print("no such file: %s" % src, file=sys.stderr)
        return 1
    if not data.get("samples"):
        print("nothing to draw: %s has no samples" % src, file=sys.stderr)
        return 1
    print("wrote %s (%d samples)" % (dest, render_svg(data, dest, stroke_scale)))
    return 0


# --------------------------------------------------------------------------
# The app
# --------------------------------------------------------------------------

if QT_BINDING:
    QT = _Enums(QtCore.Qt)
    EV = _Enums(QtCore.QEvent)
    RENDER = _Enums(QtGui.QPainter)
    MSG = _Enums(QtWidgets.QMessageBox)

    # Guide lines as fractions of the writing band's height.
    GUIDE_FRACTIONS = {
        "ascender": 0.10,
        "x_height": 0.42,
        "baseline": 0.74,
        "descender": 0.96,
    }

    PAPER = QtGui.QColor("#faf9f5")
    INK = QtGui.QColor("#14110d")
    GHOST = QtGui.QColor(20, 17, 13, 32)
    GUIDE = QtGui.QColor("#b9c7d6")
    GUIDE_STRONG = QtGui.QColor("#7f96ad")

    STYLE = """
    QWidget { background: #faf9f5; color: #14110d;
              font-size: 15px; }
    QLabel#title    { font-size: 30px; font-weight: 600; }
    QLabel#big      { font-size: 22px; font-weight: 600; }
    QLabel#sub      { color: #6f6759; }
    QLabel#quiet    { color: #8d8477; font-size: 13px; }
    QLabel#step     { color: #6f6759; font-size: 15px; }
    QLabel#warn     { color: #a8480f; }
    QFrame#card     { background: #f2ede1; border: 1px solid #e2dacb;
                      border-radius: 14px; }
    QFrame#card QLabel { background: transparent; }
    QLabel#mono     { font-family: monospace; font-size: 14px;
                      background: transparent; }
    QPushButton { background: #ffffff; border: 1px solid #ddd8cc;
                  border-radius: 10px; padding: 10px 18px; }
    QPushButton:hover   { border-color: #b0a693; }
    QPushButton:pressed { background: #f0ebe0; }
    QPushButton:disabled { color: #b3ab9d; border-color: #eae5da; }
    QPushButton:checked { background: #ece5d6; border-color: #cfc5b1; }
    QPushButton#primary { background: #b4531f; color: #ffffff; border: none;
                          padding: 14px 28px; font-size: 16px;
                          font-weight: 600; }
    QPushButton#primary:hover   { background: #9c4619; }
    QPushButton#primary:disabled{ background: #dcd4c6; color: #ffffff; }
    QPushButton#writer  { padding: 14px 20px; font-size: 16px;
                          text-align: left; }
    QPushButton#link    { border: none; color: #8d8477; padding: 6px 8px;
                          text-decoration: underline; }
    QPushButton#link:hover { color: #14110d; }
    QLineEdit { border: 1px solid #ddd8cc; border-radius: 10px;
                padding: 11px 13px; font-size: 16px; background: #ffffff; }
    QLineEdit:focus { border-color: #b4531f; }
    """

    def label(text, kind=None, wrap=False):
        lb = QtWidgets.QLabel(text)
        if kind:
            lb.setObjectName(kind)
        lb.setWordWrap(wrap)
        return lb

    def button(text, kind=None, on_click=None, tip=None):
        b = QtWidgets.QPushButton(text)
        if kind:
            b.setObjectName(kind)
        if on_click:
            b.clicked.connect(on_click)
        if tip:
            b.setToolTip(tip)
        b.setCursor(QT.PointingHandCursor)
        return b

    class Dots(QtWidgets.QWidget):
        """Little progress pips: filled = samples captured."""

        def __init__(self):
            super().__init__()
            self.done = 0
            self.total = 3
            self.setFixedHeight(18)
            self.setMinimumWidth(80)

        def set_progress(self, done, total):
            self.done, self.total = done, max(total, done)
            self.updateGeometry()
            self.update()

        def sizeHint(self):
            return QtCore.QSize(max(1, self.total) * 20, 18)

        def paintEvent(self, _ev):
            p = QtGui.QPainter(self)
            p.setRenderHint(RENDER.Antialiasing, True)
            p.setPen(QT.NoPen)
            for i in range(self.total):
                filled = i < self.done
                p.setBrush(QtGui.QColor("#b4531f") if filled
                           else QtGui.QColor("#ddd8cc"))
                p.drawEllipse(QtCore.QRectF(i * 20 + 2, 5, 9, 9))
            p.end()

    # ----------------------------------------------------------------------

    class InkCanvas(QtWidgets.QWidget):
        """Paper: guides, the ghost of the last sample, and live pen ink."""

        def __init__(self, pen_scale=1.0):
            super().__init__()
            self.pen_scale = pen_scale
            self.strokes = []
            self.ghost = None
            self.drawing = False
            self.saw_tablet = False
            self.t0 = None
            self.show_guides = True
            self.show_ghost = True
            self.on_change = None        # called whenever the strokes change
            self.on_input_kind = None    # called the first time a pen is seen
            self.setMinimumHeight(300)
            self.setFocusPolicy(QT.StrongFocus)
            try:
                self.setAttribute(QT.WA_TabletTracking, True)
            except AttributeError:
                pass
            self.setCursor(QT.CrossCursor)

        # -- geometry ----------------------------------------------------

        def band(self):
            m, top, bottom = 36.0, 30.0, 30.0
            return QtCore.QRectF(m, top,
                                 max(1.0, self.width() - 2 * m),
                                 max(1.0, self.height() - top - bottom))

        def guides(self):
            b = self.band()
            g = {"left_px": round(b.left(), 2), "right_px": round(b.right(), 2)}
            for name, frac in GUIDE_FRACTIONS.items():
                g[name + "_y_px"] = round(b.top() + frac * b.height(), 2)
            g["x_height_px"] = round(g["baseline_y_px"] - g["x_height_y_px"], 2)
            g["note"] = ("y grows downward; normalise with "
                         "(baseline_y_px - y) / x_height_px")
            return g

        def canvas_info(self):
            screen = self.screen() if hasattr(self, "screen") else None
            phys_dpi = float(screen.physicalDotsPerInch()) if screen else 96.0
            log_dpi = float(screen.logicalDotsPerInch()) if screen else 96.0
            dpr = float(screen.devicePixelRatio()) if screen else 1.0
            px_per_mm = (phys_dpi / dpr) / 25.4 if phys_dpi > 0 else 96.0 / 25.4
            return {
                "width_px": self.width(),
                "height_px": self.height(),
                "px_per_mm": round(px_per_mm, 4),
                "physical_dpi": round(phys_dpi, 2),
                "logical_dpi": round(log_dpi, 2),
                "device_pixel_ratio": dpr,
                "px_per_mm_note": ("derived from the display's reported DPI -- "
                                   "approximate, drive final size from a target "
                                   "letter height in mm instead"),
            }

        # -- recording ---------------------------------------------------

        def _now_ms(self):
            if self.t0 is None:
                self.t0 = time.perf_counter()
            return round((time.perf_counter() - self.t0) * 1000.0, 1)

        def _point(self, x, y, p, tx, ty):
            return [round(x, 2), round(y, 2), round(max(0.0, min(1.0, p)), 4),
                    self._now_ms(), round(tx, 1), round(ty, 1)]

        def _changed(self):
            self.update()
            if self.on_change:
                self.on_change()

        def begin_stroke(self, x, y, p, tx, ty, source):
            self.strokes.append({"source": source,
                                 "points": [self._point(x, y, p, tx, ty)]})
            self.drawing = True
            self._changed()

        def extend_stroke(self, x, y, p, tx, ty):
            if not self.drawing or not self.strokes:
                return
            pts = self.strokes[-1]["points"]
            last = pts[-1]
            if abs(last[0] - x) < 0.05 and abs(last[1] - y) < 0.05:
                return
            pts.append(self._point(x, y, p, tx, ty))
            self.update()

        def end_stroke(self, x, y, p, tx, ty):
            if self.drawing and self.strokes:
                self.extend_stroke(x, y, p, tx, ty)
            self.drawing = False
            self._changed()

        def undo(self):
            if self.strokes:
                self.strokes.pop()
                self._changed()
                return True
            return False

        def clear(self):
            self.strokes = []
            self.t0 = None
            self._changed()

        def take(self):
            """Hand over the current strokes and reset for the next sample."""
            strokes, self.strokes = self.strokes, []
            self.ghost = strokes
            self.t0 = None
            self._changed()
            return strokes

        def point_count(self):
            return sum(len(s["points"]) for s in self.strokes)

        # -- input -------------------------------------------------------

        def tabletEvent(self, ev):
            ev.accept()
            if not self.saw_tablet:
                self.saw_tablet = True
                if self.on_input_kind:
                    self.on_input_kind()
            if _pointer_name(ev) == "eraser":
                return
            x, y = _event_pos(ev)
            p = float(ev.pressure())
            tx, ty = float(ev.xTilt()), float(ev.yTilt())
            et = ev.type()
            if et == EV.TabletPress:
                self.begin_stroke(x, y, p, tx, ty, "pen")
            elif et == EV.TabletMove:
                self.extend_stroke(x, y, p, tx, ty)
            elif et == EV.TabletRelease:
                self.end_stroke(x, y, p, tx, ty)

        def mousePressEvent(self, ev):
            if self.saw_tablet or ev.button() != QT.LeftButton:
                return
            x, y = _event_pos(ev)
            self.begin_stroke(x, y, 0.5, 0.0, 0.0, "mouse")

        def mouseMoveEvent(self, ev):
            if self.saw_tablet or not self.drawing:
                return
            x, y = _event_pos(ev)
            self.extend_stroke(x, y, 0.5, 0.0, 0.0)

        def mouseReleaseEvent(self, ev):
            if self.saw_tablet or not self.drawing:
                return
            x, y = _event_pos(ev)
            self.end_stroke(x, y, 0.5, 0.0, 0.0)

        # -- painting ----------------------------------------------------

        def width_for(self, pressure):
            return self.pen_scale * (0.8 + 5.5 * max(0.0, min(1.0, pressure)))

        def draw_strokes(self, painter, strokes, color):
            pen = QtGui.QPen(color)
            pen.setCapStyle(QT.RoundCap)
            pen.setJoinStyle(QT.RoundJoin)
            for st in strokes:
                pts = st["points"]
                if not pts:
                    continue
                if len(pts) == 1:
                    a = pts[0]
                    pen.setWidthF(self.width_for(a[2]))
                    painter.setPen(pen)
                    painter.drawPoint(QtCore.QPointF(a[0], a[1]))
                    continue
                for a, b in zip(pts, pts[1:]):
                    pen.setWidthF(self.width_for(0.5 * (a[2] + b[2])))
                    painter.setPen(pen)
                    painter.drawLine(QtCore.QPointF(a[0], a[1]),
                                     QtCore.QPointF(b[0], b[1]))

        def draw_guides(self, painter):
            b = self.band()
            g = self.guides()
            for name in ("ascender", "x_height", "baseline", "descender"):
                y = g[name + "_y_px"]
                strong = name == "baseline"
                pen = QtGui.QPen(GUIDE_STRONG if strong else GUIDE)
                pen.setWidthF(1.6 if strong else 1.0)
                if not strong:
                    pen.setStyle(QT.DashLine)
                painter.setPen(pen)
                painter.drawLine(QtCore.QPointF(b.left(), y),
                                 QtCore.QPointF(b.right(), y))

        def paintEvent(self, _ev):
            painter = QtGui.QPainter(self)
            painter.setRenderHint(RENDER.Antialiasing, True)
            rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            path = QtGui.QPainterPath()
            path.addRoundedRect(rect, 14, 14)
            painter.fillPath(path, QtGui.QColor("#ffffff"))
            painter.setPen(QtGui.QPen(QtGui.QColor("#e6e0d3"), 1))
            painter.drawPath(path)
            painter.setClipPath(path)
            if self.show_guides:
                self.draw_guides(painter)
            if self.show_ghost and self.ghost:
                self.draw_strokes(painter, self.ghost, GHOST)
            self.draw_strokes(painter, self.strokes, INK)
            painter.end()

    # ----------------------------------------------------------------------

    def clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

    class WelcomePage(QtWidgets.QWidget):
        def __init__(self, app):
            super().__init__()
            self.app = app
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(56, 44, 56, 32)
            root.setSpacing(0)

            root.addWidget(label("Two hands, one address plate", "title"))
            root.addSpacing(10)
            root.addWidget(label(
                "You and your brother each write the same thing a few times. "
                "This records exactly how each of you moves the pen — every "
                "position and how hard you press — so Claude Code can blend "
                "the two hands into one piece of joined-up writing.",
                "sub", wrap=True))
            root.addSpacing(28)

            root.addWidget(label("What you'll write", "big"))
            root.addSpacing(8)
            self.text_edit = QtWidgets.QLineEdit(app.target_text)
            self.text_edit.setMaximumWidth(420)
            self.text_edit.textChanged.connect(self.on_text_changed)
            root.addWidget(self.text_edit)
            self.text_warning = label("", "warn", wrap=True)
            self.text_warning.hide()
            root.addSpacing(6)
            root.addWidget(self.text_warning)
            root.addSpacing(6)
            root.addWidget(label(
                "In cursive — rašytinėmis, ne spausdintinėmis.", "quiet"))
            root.addSpacing(28)

            root.addWidget(label("Who's writing?", "big"))
            root.addSpacing(10)
            self.writer_box = QtWidgets.QVBoxLayout()
            self.writer_box.setSpacing(8)
            root.addLayout(self.writer_box)
            root.addSpacing(10)

            row = QtWidgets.QHBoxLayout()
            row.setSpacing(10)
            self.name_edit = QtWidgets.QLineEdit()
            self.name_edit.setPlaceholderText("Your name")
            self.name_edit.setMaximumWidth(300)
            self.name_edit.textChanged.connect(self.on_name_changed)
            self.name_edit.returnPressed.connect(self.start_new)
            self.start_btn = button("Start writing", "primary", self.start_new)
            self.start_btn.setEnabled(False)
            row.addWidget(self.name_edit)
            row.addWidget(self.start_btn)
            row.addStretch(1)
            root.addLayout(row)

            root.addStretch(1)
            foot = QtWidgets.QHBoxLayout()
            self.path_label = label("", "quiet", wrap=True)
            foot.addWidget(self.path_label, 1)
            foot.addWidget(button("Show the file", "link", self.app.open_folder))
            root.addLayout(foot)

        def on_text_changed(self, text):
            self.app.target_text = text.strip() or TARGET_TEXT_DEFAULT
            mismatch = (self.app.samples
                        and self.app.file_text
                        and self.app.target_text != self.app.file_text)
            if mismatch:
                self.text_warning.setText(
                    "Heads up: this file already has writing of “%s”. Mixing "
                    "two different texts in one file will confuse the blend — "
                    "put the new text in a fresh file instead."
                    % self.app.file_text)
                self.text_warning.show()
            else:
                self.text_warning.hide()

        def on_name_changed(self, text):
            self.start_btn.setEnabled(bool(text.strip()))

        def start_new(self):
            name = self.name_edit.text().strip()
            if name:
                self.app.start(name)

        def refresh(self):
            self.path_label.setText("Saving to  %s" % self.app.path)
            self.text_edit.blockSignals(True)
            self.text_edit.setText(self.app.target_text)
            self.text_edit.blockSignals(False)
            clear_layout(self.writer_box)
            info = summarise_writers(self.app.samples)
            for name in sorted(info):
                n = info[name]["samples"]
                b = button("%s   ·   %d sample%s so far   →  write more"
                           % (name, n, "" if n == 1 else "s"), "writer")
                b.setMaximumWidth(520)
                b.clicked.connect(lambda _=False, w=name: self.app.start(w))
                self.writer_box.addWidget(b)
            if not info:
                self.writer_box.addWidget(label(
                    "Nobody yet — type a name below to start.", "quiet"))
            self.name_edit.clear()
            self.name_edit.setFocus()

    # ----------------------------------------------------------------------

    class CapturePage(QtWidgets.QWidget):
        def __init__(self, app):
            super().__init__()
            self.app = app
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(28, 20, 28, 20)
            root.setSpacing(12)

            head = QtWidgets.QHBoxLayout()
            head.setSpacing(16)
            self.who = label("", "big")
            head.addWidget(self.who)
            head.addStretch(1)
            self.dots = Dots()
            head.addWidget(self.dots)
            self.progress = label("", "sub")
            head.addWidget(self.progress)
            head.addStretch(1)
            self.input_kind = label("", "quiet")
            head.addWidget(self.input_kind)
            root.addLayout(head)

            self.hint = label("", "step")
            root.addWidget(self.hint)

            self.canvas = InkCanvas()
            self.canvas.on_change = self.refresh_buttons
            self.canvas.on_input_kind = self.refresh_input_kind
            root.addWidget(self.canvas, 1)

            bar = QtWidgets.QHBoxLayout()
            bar.setSpacing(10)
            self.undo_btn = button("Undo", None, self.undo,
                                   "Rub out the last stroke  (Backspace)")
            self.clear_btn = button("Start over", None, self.clear,
                                    "Rub out this whole line and try again")
            self.guides_btn = button("Guides", None, self.toggle_guides,
                                     "Show or hide the writing lines")
            self.guides_btn.setCheckable(True)
            self.guides_btn.setChecked(True)
            self.ghost_btn = button("Last one", None, self.toggle_ghost,
                                    "Show your previous writing faintly, so "
                                    "you can keep the size the same")
            self.ghost_btn.setCheckable(True)
            self.ghost_btn.setChecked(True)
            self.full_btn = button("Fullscreen", None, self.app.toggle_fullscreen,
                                   "Drag the window onto the pen display first")
            bar.addWidget(self.undo_btn)
            bar.addWidget(self.clear_btn)
            bar.addWidget(self.guides_btn)
            bar.addWidget(self.ghost_btn)
            bar.addWidget(self.full_btn)
            bar.addStretch(1)
            self.done_btn = button("Finish", None, self.app.finish,
                                   "Save this one and stop here")
            self.next_btn = button("Save this one", "primary",
                                   self.app.commit,
                                   "Save it and start the next  (Enter)")
            self.next_btn.setMinimumWidth(180)
            bar.addWidget(self.done_btn)
            bar.addWidget(self.next_btn)
            root.addLayout(bar)

        def undo(self):
            self.canvas.undo()

        def clear(self):
            if not self.canvas.strokes:
                return
            ok = QtWidgets.QMessageBox.question(
                self, "Start this one over?",
                "This rubs out the whole line you're working on.")
            if ok == MSG.Yes:
                self.canvas.clear()

        def toggle_guides(self):
            self.canvas.show_guides = self.guides_btn.isChecked()
            self.canvas.update()

        def toggle_ghost(self):
            self.canvas.show_ghost = self.ghost_btn.isChecked()
            self.canvas.update()

        def refresh_input_kind(self):
            if self.canvas.saw_tablet:
                self.input_kind.setText("pen connected ✓")
            else:
                self.input_kind.setText("no pen yet — mouse works too")

        def refresh_buttons(self):
            has = bool(self.canvas.strokes)
            self.undo_btn.setEnabled(has)
            self.clear_btn.setEnabled(has)
            self.next_btn.setEnabled(has)
            self.done_btn.setEnabled(has or self.app.mine() > 0)

        def refresh(self):
            done = self.app.mine()
            self.who.setText(self.app.writer)
            self.progress.setText("writing number %d of %d"
                                  % (done + 1, max(self.app.wanted, done + 1)))
            self.dots.set_progress(done, self.app.wanted)
            self.hint.setText(
                "Write  “%s”  in cursive — sit it on the solid line, with the "
                "small letters reaching the dashed line above."
                % self.app.target_text)
            self.refresh_input_kind()
            self.refresh_buttons()
            self.canvas.setFocus()

    # ----------------------------------------------------------------------

    class DonePage(QtWidgets.QWidget):
        def __init__(self, app):
            super().__init__()
            self.app = app
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(56, 44, 56, 32)
            root.setSpacing(0)

            root.addWidget(label("Saved.", "title"))
            root.addSpacing(14)
            self.summary = label("", "sub", wrap=True)
            root.addWidget(self.summary)
            root.addSpacing(10)
            self.advice = label("", "warn", wrap=True)
            root.addWidget(self.advice)
            root.addSpacing(26)

            card = QtWidgets.QFrame()
            card.setObjectName("card")
            card.setMaximumWidth(760)
            cl = QtWidgets.QVBoxLayout(card)
            cl.setContentsMargins(24, 22, 24, 22)
            cl.setSpacing(12)
            cl.addWidget(label("Next: open Claude Code in this folder and say", "big"))
            self.say = label("", "mono", wrap=True)
            self.say.setTextInteractionFlags(QT.TextSelectableByMouse)
            cl.addWidget(self.say)
            crow = QtWidgets.QHBoxLayout()
            crow.setSpacing(10)
            self.copy_btn = button("Copy that line", None, self.copy_line)
            crow.addWidget(self.copy_btn)
            crow.addWidget(button("Open the folder", None, self.app.open_folder))
            crow.addStretch(1)
            cl.addLayout(crow)
            cl.addWidget(label(
                "Everything Claude needs — what the numbers mean and what to "
                "do with them — is written inside the file itself.", "quiet",
                wrap=True))
            root.addWidget(card)
            root.addSpacing(28)

            row = QtWidgets.QHBoxLayout()
            row.setSpacing(10)
            row.addWidget(button("Someone else's turn", "primary",
                                 self.app.go_welcome))
            row.addWidget(button("Write another one myself", None,
                                 self.app.write_more))
            row.addWidget(button("See what I wrote", None, self.app.preview))
            row.addStretch(1)
            row.addWidget(button("Quit", None, self.app.close))
            root.addLayout(row)
            root.addStretch(1)

        def copy_line(self):
            QtWidgets.QApplication.clipboard().setText(self.app.claude_line())
            self.copy_btn.setText("Copied ✓")
            QtCore.QTimer.singleShot(
                2000, lambda: self.copy_btn.setText("Copy that line"))

        def refresh(self):
            info = summarise_writers(self.app.samples)
            lines = []
            for name in sorted(info):
                i = info[name]
                lines.append("%s — %d sample%s, %d strokes%s"
                             % (name, i["samples"],
                                "" if i["samples"] == 1 else "s", i["strokes"],
                                "  (mouse, no real pressure)"
                                if i["input"] == "mouse" else ""))
            self.summary.setText("In the file now:\n" + "\n".join(lines))
            self.say.setText(self.app.claude_line())

            notes = []
            if len(info) < 2:
                notes.append("Only one person so far — the blend needs both of "
                             "you, so hand the pen over and hit “Someone "
                             "else's turn”.")
            thin = [n for n, i in info.items() if i["samples"] < 2]
            if thin:
                notes.append("Only one sample from %s. Two or three each gives "
                             "Claude a clean one to work from."
                             % ", ".join(sorted(thin)))
            self.advice.setText("\n".join(notes))
            self.advice.setVisible(bool(notes))

    # ----------------------------------------------------------------------

    class MainWindow(QtWidgets.QWidget):
        def __init__(self, path):
            super().__init__()
            self.path = path
            doc = load_capture(path) or {}
            self.samples = list(doc.get("samples", []))
            self.file_text = doc.get("target_text") or ""
            self.target_text = self.file_text or TARGET_TEXT_DEFAULT
            self.writer = ""
            self.wanted = 3
            self.dirty = False

            self.setWindowTitle("Handwriting")
            self.resize(1180, 800)
            self.setMinimumSize(880, 600)
            self.setStyleSheet(STYLE)

            self.stack = QtWidgets.QStackedWidget()
            self.welcome = WelcomePage(self)
            self.capture = CapturePage(self)
            self.done = DonePage(self)
            for page in (self.welcome, self.capture, self.done):
                self.stack.addWidget(page)
            lay = QtWidgets.QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(self.stack)
            self.go_welcome()

        # -- state -------------------------------------------------------

        def mine(self):
            return sum(1 for s in self.samples if s["writer"] == self.writer)

        def claude_line(self):
            return ("read %s and do what the prompt inside says"
                    % os.path.basename(self.path))

        def header(self):
            return {
                "target_text": self.target_text,
                "device": DEVICE_HINT,
                "captured_with": "capture_handwriting.py (%s)" % QT_BINDING,
                "canvas": self.capture.canvas.canvas_info(),
                "guides": self.capture.canvas.guides(),
            }

        # -- navigation --------------------------------------------------

        def go_welcome(self):
            self.welcome.refresh()
            self.stack.setCurrentWidget(self.welcome)

        def go_done(self):
            self.done.refresh()
            self.stack.setCurrentWidget(self.done)

        def start(self, writer):
            self.writer = writer.strip()
            if not self.writer:
                return
            self.capture.canvas.clear()
            self.capture.canvas.ghost = None
            self.capture.refresh()
            self.stack.setCurrentWidget(self.capture)

        def write_more(self):
            self.capture.refresh()
            self.stack.setCurrentWidget(self.capture)

        def toggle_fullscreen(self):
            self.showNormal() if self.isFullScreen() else self.showFullScreen()

        # -- capturing ---------------------------------------------------

        def _commit_strokes(self):
            canvas = self.capture.canvas
            if not canvas.strokes:
                return False
            strokes = canvas.take()
            sources = sorted({("tablet" if s["source"] == "pen" else s["source"])
                              for s in strokes})
            self.samples.append({
                "writer": self.writer,
                "index": self.mine(),
                "captured_at": utcnow(),
                "input": "mouse" if sources == ["mouse"] else "+".join(sources),
                "duration_ms": max((s["points"][-1][3] for s in strokes),
                                   default=0.0),
                "stroke_count": len(strokes),
                "point_count": sum(len(s["points"]) for s in strokes),
                "canvas": canvas.canvas_info(),
                "guides": canvas.guides(),
                "strokes": strokes,
            })
            self.dirty = True
            return self.save()

        def commit(self):
            if not self._commit_strokes():
                return
            if self.mine() >= self.wanted:
                self.go_done()
            else:
                self.capture.refresh()

        def finish(self):
            self._commit_strokes()
            self.go_done()

        def save(self):
            try:
                write_capture(self.path, self.header(), self.samples)
            except OSError as exc:
                QtWidgets.QMessageBox.critical(
                    self, "Could not save",
                    "Writing to\n%s\nfailed:\n\n%s" % (self.path, exc))
                return False
            self.dirty = False
            return True

        # -- extras ------------------------------------------------------

        def open_folder(self):
            folder = os.path.dirname(os.path.abspath(self.path)) or "."
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))

        def preview(self):
            if not self.samples:
                QtWidgets.QMessageBox.information(
                    self, "Nothing yet", "Write something first.")
                return
            dest = os.path.splitext(self.path)[0] + "_preview.svg"
            try:
                render_svg({"samples": self.samples,
                            "guides": self.header()["guides"]}, dest)
            except OSError as exc:
                QtWidgets.QMessageBox.critical(self, "Could not write preview",
                                               str(exc))
                return
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(dest))

        # -- keys (all optional -- every one has a button) ----------------

        def keyPressEvent(self, ev):
            on_canvas = self.stack.currentWidget() is self.capture
            key = ev.key()
            ctrl = bool(ev.modifiers() & QT.ControlModifier)
            if key == QT.Key_Escape and self.isFullScreen():
                self.showNormal()
            elif on_canvas and key in (QT.Key_Return, QT.Key_Enter):
                self.commit()
            elif on_canvas and (key == QT.Key_Backspace
                                or (ctrl and key == QT.Key_Z)):
                self.capture.canvas.undo()
            else:
                super().keyPressEvent(ev)

        def closeEvent(self, ev):
            if self.stack.currentWidget() is self.capture:
                self._commit_strokes()
            if self.dirty:
                self.save()
            ev.accept()

# --------------------------------------------------------------------------
# Starting up (including installing Qt for you, with no terminal)
# --------------------------------------------------------------------------

QT_MISSING_HELP = """\
This app needs Qt, which is what lets it read pen pressure.

Install it with:

    pip install PySide6

then start the app again.
"""


def default_path():
    """Keep the capture next to the script, whatever folder we were run from."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, DEFAULT_OUT)


def pip_install(package):
    import subprocess
    base = [sys.executable, "-m", "pip", "install", package]
    for cmd in (base, base + ["--user"]):
        try:
            done = subprocess.run(cmd, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
        except OSError as exc:
            return 1, str(exc)
        if done.returncode == 0:
            return 0, ""
        tail = (done.stdout or b"").decode("utf-8", "replace")
    return 1, "\n".join(tail.strip().splitlines()[-12:])


def offer_install():
    """No Qt yet: ask, in a window, whether to install it. True if installed."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        print(QT_MISSING_HELP, file=sys.stderr)
        return False

    state = {"ok": False}
    root = tk.Tk()
    root.title("Handwriting")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=28)
    frame.grid()
    ttk.Label(frame, font=("", 15, "bold"),
              text="One thing to set up first").grid(sticky="w")
    ttk.Label(frame, wraplength=430, justify="left",
              text="\nTo read how hard you press on the pen, this needs a "
                   "piece of software called PySide6. It's a one-time "
                   "download of about 100 MB.\n").grid(sticky="w")
    status = ttk.Label(frame, wraplength=430, justify="left", text="")
    status.grid(sticky="w")
    bar = ttk.Progressbar(frame, mode="indeterminate", length=430)
    buttons = ttk.Frame(frame)
    buttons.grid(sticky="e", pady=(18, 0))

    def finish(code, detail):
        bar.stop()
        bar.grid_remove()
        if code == 0:
            state["ok"] = True
            root.destroy()
        else:
            status.config(text="That didn't work. You can install it by hand:\n"
                               "    pip install PySide6")
            if detail:
                messagebox.showerror("Install failed", detail)
            install_btn.config(state="normal", text="Try again")
            quit_btn.config(state="normal")

    def start():
        import threading
        install_btn.config(state="disabled", text="Installing…")
        quit_btn.config(state="disabled")
        status.config(text="Downloading and installing. This takes a minute or "
                           "two — you can leave it running.")
        bar.grid(sticky="w", pady=(12, 0))
        bar.start(12)

        def work():
            code, detail = pip_install("PySide6")
            root.after(0, finish, code, detail)

        threading.Thread(target=work, daemon=True).start()

    quit_btn = ttk.Button(buttons, text="Not now", command=root.destroy)
    quit_btn.grid(row=0, column=0, padx=(0, 8))
    install_btn = ttk.Button(buttons, text="Install it for me", command=start)
    install_btn.grid(row=0, column=1)
    root.update_idletasks()
    root.eval("tk::PlaceWindow . center")
    root.mainloop()
    return state["ok"]


def run_app(path):
    if not QT_BINDING:
        if not offer_install():
            return 2
        # Qt only becomes importable in a fresh interpreter, so start over.
        os.execv(sys.executable,
                 [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])

    if QT_BINDING == "PyQt5":          # Qt6 scales by default; these are no-ops
        for attr in ("AA_EnableHighDpiScaling", "AA_UseHighDpiPixmaps"):
            try:
                QtWidgets.QApplication.setAttribute(getattr(QT, attr), True)
            except AttributeError:
                pass

    app = QtWidgets.QApplication(sys.argv[:1])
    app.setApplicationName("Handwriting")
    win = MainWindow(path)
    win.show()
    win.raise_()
    win.activateWindow()
    run = getattr(app, "exec", None) or getattr(app, "exec_")
    return run()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Record two people's cursive handwriting (position and pen "
                    "pressure) into one file that carries its own Claude Code "
                    "prompt. Just run it -- everything is in the window.")
    parser.add_argument("file", nargs="?",
                        help="capture file to use (default: %s next to this "
                             "script)" % DEFAULT_OUT)
    parser.add_argument("--inspect", action="store_true",
                        help="optional: print a summary of the file and exit")
    parser.add_argument("--svg", metavar="OUT.SVG",
                        help="optional: render the file to an SVG and exit")
    args = parser.parse_args(argv)

    path = args.file or default_path()
    if args.inspect:
        return cmd_inspect(path)
    if args.svg:
        return cmd_svg(path, args.svg)
    return run_app(path)


if __name__ == "__main__":
    sys.exit(main())
