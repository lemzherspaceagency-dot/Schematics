#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
capture_handwriting.py -- record cursive handwriting from an XP-Pen Artist 15.6 (V2)
(or any pressure-sensitive tablet Qt can see) and dump x / y / pressure / tilt / time
into one JSON file that also carries a ready-made prompt for Claude Code.

Two people write the same text (default: "Alyvų g. 4"), a few repetitions each,
into the SAME file. Afterwards you drop the file into Claude Code and it fuses
both hands into one joined-up cursive address plate.

    # you
    python3 capture_handwriting.py --writer laurynas

    # your brother, same file, appends
    python3 capture_handwriting.py --writer brolis

    # sanity checks
    python3 capture_handwriting.py --inspect alyvu_g4_handwriting.json
    python3 capture_handwriting.py --svg preview.svg alyvu_g4_handwriting.json

Keys while capturing:
    Enter / Return .... commit this sample, start the next one
    Backspace / Ctrl+Z  undo last stroke
    C ................ clear current sample
    G ................ toggle the ghost of your previous sample
    L ................ toggle guide lines
    H ................ toggle the help overlay
    F ................ toggle fullscreen (put it on the pen display first)
    S ................ save now
    Esc / Q .......... save and quit
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
# Capture window
# --------------------------------------------------------------------------

if QT_BINDING:
    QT = _Enums(QtCore.Qt)
    EV = _Enums(QtCore.QEvent)
    RENDER = _Enums(QtGui.QPainter)

    # Guide lines as fractions of the writing band's height.
    GUIDE_FRACTIONS = {
        "ascender": 0.10,
        "x_height": 0.42,
        "baseline": 0.74,
        "descender": 0.96,
    }

    PAPER = QtGui.QColor("#faf9f5")
    INK = QtGui.QColor("#14110d")
    GHOST = QtGui.QColor(20, 17, 13, 38)
    GUIDE = QtGui.QColor("#b9c7d6")
    GUIDE_STRONG = QtGui.QColor("#7f96ad")
    HUD = QtGui.QColor("#5c6672")

    class Canvas(QtWidgets.QWidget):
        def __init__(self, writer, target_text, out_path, existing, wanted, pen_scale):
            super().__init__()
            self.writer = writer
            self.target_text = target_text
            self.out_path = out_path
            self.existing = existing          # samples already in the file
            self.wanted = wanted              # how many samples we're asking for
            self.pen_scale = pen_scale

            self.session = []                 # samples committed this run
            self.strokes = []                 # strokes of the sample in progress
            self.ghost = None                 # last committed sample, drawn faintly
            self.drawing = False
            self.saw_tablet = False
            self.t0 = None
            self.dirty = False
            self.show_guides = True
            self.show_ghost = True
            self.show_help = True
            self.message = ""
            self.message_until = 0.0

            self.setWindowTitle("Handwriting capture -- %s -- %s"
                                % (writer, target_text))
            self.resize(1600, 620)
            self.setMinimumSize(700, 320)
            self.setAutoFillBackground(True)
            self.setFocusPolicy(QT.StrongFocus)
            try:
                self.setAttribute(QT.WA_TabletTracking, True)
            except AttributeError:
                pass
            self.setCursor(QT.CrossCursor)

        # -- geometry ----------------------------------------------------

        def band(self):
            """The writing band, in widget pixels."""
            m = 40.0
            top = 84.0
            bottom = 58.0
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

        def header(self):
            return {
                "target_text": self.target_text,
                "device": DEVICE_HINT,
                "captured_with": "capture_handwriting.py (%s)" % QT_BINDING,
                "canvas": self.canvas_info(),
                "guides": self.guides(),
            }

        # -- stroke recording --------------------------------------------

        def _now_ms(self):
            if self.t0 is None:
                self.t0 = time.perf_counter()
            return round((time.perf_counter() - self.t0) * 1000.0, 1)

        def _point(self, x, y, p, tx, ty):
            return [round(x, 2), round(y, 2), round(max(0.0, min(1.0, p)), 4),
                    self._now_ms(), round(tx, 1), round(ty, 1)]

        def begin_stroke(self, x, y, p, tx, ty, source):
            self.strokes.append({"source": source,
                                 "points": [self._point(x, y, p, tx, ty)]})
            self.drawing = True
            self.dirty = True
            self.update()

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
                if len(self.strokes[-1]["points"]) < 2:
                    # a tap: keep it, dots and diacritics are single points
                    pass
            self.drawing = False
            self.update()

        # -- events ------------------------------------------------------

        def tabletEvent(self, ev):
            ev.accept()
            self.saw_tablet = True
            if _pointer_name(ev) == "eraser":
                self.flash("eraser ignored -- press Backspace to undo a stroke")
                return
            x, y = _event_pos(ev)
            p = float(ev.pressure())
            tx = float(ev.xTilt())
            ty = float(ev.yTilt())
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

        def keyPressEvent(self, ev):
            key = ev.key()
            ctrl = bool(ev.modifiers() & QT.ControlModifier)
            if key in (QT.Key_Return, QT.Key_Enter):
                self.commit_sample()
            elif key == QT.Key_Backspace or (ctrl and key == QT.Key_Z):
                self.undo_stroke()
            elif key == QT.Key_C:
                self.clear_sample()
            elif key == QT.Key_G:
                self.show_ghost = not self.show_ghost
                self.update()
            elif key == QT.Key_L:
                self.show_guides = not self.show_guides
                self.update()
            elif key == QT.Key_H:
                self.show_help = not self.show_help
                self.update()
            elif key == QT.Key_F:
                self.showNormal() if self.isFullScreen() else self.showFullScreen()
            elif key == QT.Key_S:
                self.save(explicit=True)
            elif key in (QT.Key_Escape, QT.Key_Q):
                self.close()
            else:
                super().keyPressEvent(ev)

        def closeEvent(self, ev):
            if self.strokes:
                self.commit_sample(quiet=True)
            if self.dirty or self.session:
                self.save()
            ev.accept()

        # -- actions -----------------------------------------------------

        def flash(self, text, seconds=2.5):
            self.message = text
            self.message_until = time.time() + seconds
            self.update()

        def undo_stroke(self):
            if self.strokes:
                self.strokes.pop()
                self.flash("stroke undone")
            else:
                self.flash("nothing to undo")
            self.update()

        def clear_sample(self):
            if self.strokes:
                self.strokes = []
                self.flash("sample cleared")
            self.update()

        def commit_sample(self, quiet=False):
            if not self.strokes:
                if not quiet:
                    self.flash("write something first")
                return
            points = sum(len(s["points"]) for s in self.strokes)
            duration = max((s["points"][-1][3] for s in self.strokes), default=0.0)
            sources = sorted({("tablet" if s["source"] == "pen" else s["source"])
                              for s in self.strokes})
            sample = {
                "writer": self.writer,
                "index": self.next_index(),
                "captured_at": utcnow(),
                "input": "mouse" if sources == ["mouse"] else "+".join(sources),
                "duration_ms": duration,
                "stroke_count": len(self.strokes),
                "point_count": points,
                "canvas": self.canvas_info(),
                "guides": self.guides(),
                "strokes": self.strokes,
            }
            self.session.append(sample)
            self.ghost = self.strokes
            self.strokes = []
            self.t0 = None
            self.dirty = True
            self.save()
            done = self.mine()
            self.flash("sample %d saved (%d strokes, %d points)"
                       % (done, sample["stroke_count"], points))
            self.update()

        def mine(self):
            return sum(1 for s in self.all_samples() if s["writer"] == self.writer)

        def next_index(self):
            return self.mine()

        def all_samples(self):
            return self.existing + self.session

        def save(self, explicit=False):
            samples = self.all_samples()
            if not samples:
                if explicit:
                    self.flash("nothing to save yet")
                return
            try:
                write_capture(self.out_path, self.header(), samples)
            except OSError as exc:
                self.flash("SAVE FAILED: %s" % exc, seconds=8)
                print("save failed: %s" % exc, file=sys.stderr)
                return
            self.dirty = False
            if explicit:
                self.flash("saved -> %s" % self.out_path)

        # -- painting ----------------------------------------------------

        def width_for(self, pressure):
            return self.pen_scale * (0.8 + 5.5 * max(0.0, min(1.0, pressure)))

        def draw_strokes(self, painter, strokes, color, fixed_width=None):
            pen = QtGui.QPen(color)
            pen.setCapStyle(QT.RoundCap)
            pen.setJoinStyle(QT.RoundJoin)
            for st in strokes:
                pts = st["points"]
                if not pts:
                    continue
                if len(pts) == 1:
                    a = pts[0]
                    pen.setWidthF(fixed_width or self.width_for(a[2]))
                    painter.setPen(pen)
                    painter.drawPoint(QtCore.QPointF(a[0], a[1]))
                    continue
                for a, b in zip(pts, pts[1:]):
                    pen.setWidthF(fixed_width
                                  or self.width_for(0.5 * (a[2] + b[2])))
                    painter.setPen(pen)
                    painter.drawLine(QtCore.QPointF(a[0], a[1]),
                                     QtCore.QPointF(b[0], b[1]))

        def paintEvent(self, _ev):
            painter = QtGui.QPainter(self)
            painter.setRenderHint(RENDER.Antialiasing, True)
            painter.fillRect(self.rect(), PAPER)

            if self.show_guides:
                self.draw_guides(painter)
            if self.show_ghost and self.ghost:
                self.draw_strokes(painter, self.ghost, GHOST)
            self.draw_strokes(painter, self.strokes, INK)
            self.draw_hud(painter)
            painter.end()

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
            pen = QtGui.QPen(GUIDE)
            pen.setWidthF(1.0)
            pen.setStyle(QT.DotLine)
            painter.setPen(pen)
            painter.drawLine(QtCore.QPointF(b.left(), b.top()),
                             QtCore.QPointF(b.left(), b.bottom()))

        def draw_hud(self, painter):
            font = painter.font()
            font.setPointSizeF(max(9.0, font.pointSizeF()))
            painter.setFont(font)
            painter.setPen(QtGui.QPen(HUD))

            done = self.mine()
            src = "tablet" if self.saw_tablet else "mouse (no tablet seen yet)"
            head = ("write:  %s        writer: %s        sample %d of %d"
                    % (self.target_text, self.writer, done + 1, self.wanted))
            painter.drawText(QtCore.QRectF(40, 18, self.width() - 80, 26),
                             int(QT.AlignLeft | QT.AlignVCenter), head)
            painter.drawText(QtCore.QRectF(40, 18, self.width() - 80, 26),
                             int(QT.AlignRight | QT.AlignVCenter),
                             "input: %s" % src)

            sub = ("rašytinėmis, ne spausdintinėmis  --  sit on the solid "
                   "baseline, small letters up to the dashed x-height line")
            painter.drawText(QtCore.QRectF(40, 44, self.width() - 80, 22),
                             int(QT.AlignLeft | QT.AlignVCenter), sub)

            if self.show_help:
                keys = ("Enter commit   Backspace undo   C clear   "
                        "G ghost   L guides   H help   F fullscreen   "
                        "S save   Esc quit")
                painter.drawText(
                    QtCore.QRectF(40, self.height() - 46, self.width() - 80, 22),
                    int(QT.AlignLeft | QT.AlignVCenter), keys)

            painter.drawText(
                QtCore.QRectF(40, self.height() - 26, self.width() - 80, 22),
                int(QT.AlignLeft | QT.AlignVCenter),
                "-> %s   (%d strokes in progress)"
                % (self.out_path, len(self.strokes)))

            if self.message and time.time() < self.message_until:
                painter.setPen(QtGui.QPen(INK))
                painter.drawText(
                    QtCore.QRectF(40, self.height() - 26, self.width() - 80, 22),
                    int(QT.AlignRight | QT.AlignVCenter), self.message)


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


def cmd_svg(src, dest, stroke_scale=1.0):
    data = load_capture(src)
    if data is None:
        print("no such file: %s" % src, file=sys.stderr)
        return 1
    samples = data.get("samples", [])
    if not samples:
        print("nothing to draw: %s has no samples" % src, file=sys.stderr)
        return 1

    samples = sorted(samples, key=lambda s: (s["writer"], s["index"]))
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
    print("wrote %s (%d samples)" % (dest, len(samples)))
    return 0


# --------------------------------------------------------------------------
# Capture mode
# --------------------------------------------------------------------------

QT_MISSING_HELP = """\
No Qt binding found, and Qt is what gives us pen pressure.

    pip install PySide6          (or: pip install PyQt6 / PyQt5)

On Linux also make sure the tablet is on XInput2/libinput and that the
XP-Pen driver is running, otherwise you get mouse events with no pressure.
On Windows, PySide6 talks to Windows Ink; if pressure reads 0, turn on
"Windows Ink" (or Wintab, whichever your app profile uses) in the
XP-Pen driver.
"""


def cmd_capture(args):
    if not QT_BINDING:
        print(QT_MISSING_HELP, file=sys.stderr)
        return 2

    for attr in ("AA_EnableHighDpiScaling", "AA_UseHighDpiPixmaps"):
        try:
            QtWidgets.QApplication.setAttribute(getattr(QT, attr), True)
        except AttributeError:
            pass

    app = QtWidgets.QApplication(sys.argv[:1])

    writer = args.writer
    if not writer:
        text, ok = QtWidgets.QInputDialog.getText(
            None, "Who is writing?",
            "Writer name (use the same name every time):")
        writer = (text or "").strip() if ok else ""
    writer = writer.strip()
    if not writer:
        print("no writer name given -- nothing captured", file=sys.stderr)
        return 1

    existing_doc = load_capture(args.file)
    existing = existing_doc["samples"] if existing_doc else []
    target = args.text or (existing_doc or {}).get("target_text") \
        or TARGET_TEXT_DEFAULT
    if args.replace:
        dropped = [s for s in existing if s["writer"] == writer]
        existing = [s for s in existing if s["writer"] != writer]
        if dropped:
            print("--replace: dropping %d earlier sample(s) by %s"
                  % (len(dropped), writer))

    print("file   : %s%s" % (args.file,
                             "" if existing_doc else "  (new)"))
    print("writer : %s" % writer)
    print("text   : %s" % target)
    if existing:
        for w, info in sorted(summarise_writers(existing).items()):
            print("already in file: %s -- %d sample(s), %d strokes"
                  % (w, info["samples"], info["strokes"]))

    win = Canvas(writer, target, args.file, existing, args.samples,
                 args.pen_scale)
    if args.fullscreen:
        win.showFullScreen()
    else:
        win.show()
    win.raise_()
    win.activateWindow()

    run = getattr(app, "exec", None) or getattr(app, "exec_")
    code = run()

    total = win.mine()
    if total:
        print("captured %d sample(s) by %s -> %s" % (total, writer, args.file))
        print("next: give %s to Claude Code -- the prompt is inside the file."
              % args.file)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Capture cursive handwriting (x, y, pressure) from an "
                    "XP-Pen Artist 15.6 V2 into a JSON file that carries its "
                    "own Claude Code prompt.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
               "  %(prog)s --writer laurynas\n"
               "  %(prog)s --writer brolis\n"
               "  %(prog)s --inspect\n"
               "  %(prog)s --svg preview.svg\n")
    parser.add_argument("file", nargs="?", default=DEFAULT_OUT,
                        help="capture file to write/append to "
                             "(default: %(default)s)")
    parser.add_argument("--writer", "-w",
                        help="writer name; asked for in a dialog if omitted. "
                             "Use the SAME name each session.")
    parser.add_argument("--text", "-t",
                        help="text to write (default: %s, or whatever the "
                             "file already uses)" % TARGET_TEXT_DEFAULT)
    parser.add_argument("--samples", "-n", type=int, default=3,
                        help="how many repetitions to aim for (default: "
                             "%(default)s); it is only a target, write as "
                             "many as you like")
    parser.add_argument("--pen-scale", type=float, default=1.0,
                        help="on-screen ink thickness multiplier "
                             "(default: %(default)s)")
    parser.add_argument("--fullscreen", action="store_true",
                        help="start fullscreen (move the window to the pen "
                             "display first, or press F later)")
    parser.add_argument("--replace", action="store_true",
                        help="discard this writer's earlier samples instead "
                             "of appending")
    parser.add_argument("--inspect", action="store_true",
                        help="print a summary of the capture file and exit")
    parser.add_argument("--svg", metavar="OUT.SVG",
                        help="render the capture file to an SVG for checking "
                             "and exit")
    args = parser.parse_args(argv)

    if args.inspect:
        return cmd_inspect(args.file)
    if args.svg:
        return cmd_svg(args.file, args.svg, args.pen_scale)
    return cmd_capture(args)


if __name__ == "__main__":
    sys.exit(main())
