#!/usr/bin/env python3
"""Generates every sprite for Ready, Set, Cook! as SVG into ../art/. Run: python3 art_src/gen_art.py"""
import os
from lib import S, OUT, SW, shade

HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, "..", "art")
os.makedirs(DST, exist_ok=True)


def out(name, s):
    s.save(os.path.join(DST, name + ".svg"))


def block(s, x, y, w, top_h, front_h, top_col, front_col, r=12):
    """3/4-view chunky block: front face under a lighter top face."""
    s.rect(x, y + top_h - r, w, front_h + r, r, s.grad(shade(front_col, 0.12), shade(front_col, -0.2)))
    s.rect(x, y, w, top_h, r, s.grad(shade(top_col, 0.22), top_col))
    s.rect(x + 8, y + 6, w - 16, 7, 3, "#ffffff", None, 0, 0.28)


def faint(s, op):
    s.body[-1] = s.body[-1].replace("/>", ' opacity="%s"/>' % op)


# --------------------------------------------------------------- tiles
def tiles():
    for name, (c1, c2) in {"floor_a": ("#f8eedb", "#efe1c6"), "floor_b": ("#f1e5cc", "#e6d7b8")}.items():
        s = S(128, 128)
        s.rect(0, 0, 128, 128, 0, s.grad(c1, c2), None, 0)
        s.line(0, 126, 128, 126, "#cdbb94", 4, 0.8)
        s.line(126, 0, 126, 128, "#cdbb94", 4, 0.8)
        s.line(2, 2, 126, 2, "#ffffff", 4, 0.7)
        s.line(2, 2, 2, 126, "#ffffff", 4, 0.7)
        s.poly([(14, 14), (70, 14), (14, 70)], "#ffffff", None, 0)
        faint(s, 0.16)
        out(name, s)
    s = S(128, 128)
    s.rect(0, 0, 128, 128, 0, s.grad("#4a5a86", "#37446a"), None, 0)
    for row in range(4):
        y = row * 32
        s.line(0, y, 128, y, "#2a3558", 4, 0.9)
        off = 0 if row % 2 == 0 else 32
        for k in range(-1, 4):
            x = off + k * 64
            s.line(x, y, x, y + 32, "#2a3558", 4, 0.9)
    s.rect(0, 0, 128, 10, 0, "#ffffff", None, 0, 0.12)
    out("wall", s)
    for name, (c1, c2) in {"carpet_a": ("#6a559c", "#5b4789"), "carpet_b": ("#5f4c90", "#503f7d")}.items():
        s = S(128, 128)
        s.rect(0, 0, 128, 128, 0, s.grad(c1, c2), None, 0)
        for (cx, cy) in [(32, 32), (96, 32), (32, 96), (96, 96), (64, 64)]:
            s.poly([(cx, cy - 14), (cx + 14, cy), (cx, cy + 14), (cx - 14, cy)], "#ffffff", None, 0)
            faint(s, 0.10)
        s.line(0, 126, 128, 126, "#000000", 4, 0.15)
        out(name, s)
    s = S(128, 128)
    s.shadow(64, 118, 56, 8)
    block(s, 6, 14, 116, 78, 24, "#e4b27c", "#a96f3d")
    for x in (40, 80):
        s.line(x, 24, x, 88, "#b5834e", 3, 0.6)
    out("counter", s)
    for name, col in {"seat": "#e4b27c", "seat_closed": "#8d7f74"}.items():
        s = S(128, 128)
        s.shadow(64, 118, 56, 8)
        block(s, 6, 14, 116, 78, 24, col, shade(col, -0.35))
        if name == "seat":
            s.rect(26, 34, 76, 44, 8, s.grad("#ffffff", "#eef0f5"), "#c9ccd8", 3)
            s.ell(64, 56, 15, 11, "#ffffff", "#c9ccd8", 3)
            s.line(36, 42, 36, 70, "#b8bcc9", 4)
            s.line(92, 42, 92, 70, "#b8bcc9", 4)
        else:
            s.line(40, 36, 88, 74, "#5a4f48", 8, 0.8)
            s.line(88, 36, 40, 74, "#5a4f48", 8, 0.8)
        out(name, s)


# --------------------------------------------------------------- stations
def stations():
    def crate(name, fill_fn):
        s = S(128, 128)
        s.shadow(64, 118, 54, 8)
        s.rect(10, 44, 108, 70, 10, s.grad("#d89d5b", "#a8693a"))
        for y in (62, 84):
            s.line(14, y, 114, y, "#8d5629", 4, 0.8)
        fill_fn(s)
        s.rect(6, 76, 116, 36, 10, s.grad("#dca25f", "#a76a3a"))
        s.line(10, 94, 118, 94, "#8d5629", 4, 0.7)
        s.rect(14, 82, 100, 5, 3, "#ffffff", None, 0, 0.3)
        out(name, s)

    def meat(s):
        s.rect(14, 28, 100, 40, 14, "#4a2a1a", None, 0)
        for (cx, cy, rot) in [(38, 40, -18), (72, 36, 12), (94, 46, -6), (58, 52, 20)]:
            s.ell(cx, cy, 24, 16, s.grad("#ff8d9a", "#d9455c"), OUT, 4, 1, rot)
            s.ell(cx + 4, cy - 2, 12, 7, "#ffd9de", None, 0, 0.85, rot)
            s.shine(cx - 8, cy - 7, 8, 3, 0.7, rot)

    def veg(s):
        s.rect(14, 28, 100, 40, 14, "#254a1e", None, 0)
        s.circle(38, 38, 22, s.grad("#9fd45c", "#5a9a3a"))
        s.path("M24 40 Q38 20 52 40", "none", "#3f7a2a", 3)
        s.path("M30 30 Q38 44 46 30", "none", "#3f7a2a", 3)
        s.shine(30, 28, 9, 4)
        s.circle(78, 36, 20, s.grad("#ff7a5a", "#d63f2b"))
        s.path("M72 22 l6 -8 l6 8", "none", "#3f7a2a", 5)
        s.shine(72, 28, 7, 3)
        for (x, y) in [(100, 42), (96, 54)]:
            s.path("M%d %d l16 -22 l8 6 z" % (x - 8, y + 6), s.grad("#ffb347", "#f07c1d"), OUT, 4)

    def dough(s):
        s.rect(14, 30, 100, 40, 14, "#6b5130", None, 0)
        for (cx, cy, r) in [(38, 40, 20), (76, 36, 22), (100, 48, 16)]:
            s.circle(cx, cy, r, s.grad("#fff6df", "#e8d3a2"))
            s.shine(cx - r * 0.35, cy - r * 0.4, r * 0.4, r * 0.2)

    crate("crate_meat", meat)
    crate("crate_veg", veg)
    crate("crate_dough", dough)

    s = S(128, 128)
    s.shadow(64, 112, 54, 8)
    block(s, 6, 20, 116, 78, 20, "#e4b27c", "#a96f3d")
    s.rect(18, 30, 92, 54, 10, s.grad("#f1cf9a", "#d9a769"), "#a96f3d", 4)
    for y in (46, 60, 74):
        s.line(26, y, 102, y, "#b98350", 3, 0.5)
    s.path("M34 78 L88 36 L100 44 L48 84 Z", s.grad("#f4f7fb", "#aeb7c4"), OUT, 4)
    s.shine(70, 52, 14, 3, 0.8, -38)
    s.rect(22, 76, 30, 14, 6, s.grad("#a8693a", "#6b3f1d"), OUT, 4)
    out("chop_board", s)

    s = S(128, 128)
    s.shadow(64, 118, 56, 8)
    block(s, 6, 16, 116, 80, 26, "#5b6078", "#3a3e52")
    s.circle(64, 54, 32, "#2a2c3a", "#1b1c26", 4)
    s.circle(64, 54, 22, "#3d4054", "#1b1c26", 3)
    s.circle(64, 54, 12, "#2a2c3a", "#1b1c26", 3)
    for x in (28, 64, 100):
        s.circle(x, 106, 7, s.grad("#e8e8ef", "#9a9cb0"), OUT, 4)
    out("stove", s)
    s = S(128, 128)
    s.shadow(64, 72, 38, 8, 0.3)
    s.rect(24, 34, 80, 44, 14, s.grad("#c4c9d8", "#7d8398"))
    s.rect(18, 28, 92, 16, 8, s.grad("#e6e9f2", "#a0a6ba"))
    s.shine(40, 36, 12, 3, 0.8, 0)
    s.rect(6, 40, 14, 8, 4, "#4a4e63", OUT, 4)
    s.rect(108, 40, 14, 8, 4, "#4a4e63", OUT, 4)
    out("pot", s)
    s = S(64, 80)
    s.path("M32 6 C50 28 58 40 52 56 C48 70 16 70 12 56 C8 40 22 32 32 6 Z", s.grad("#ffd23f", "#ff5a1f"), "#c93a0c", 3)
    s.path("M32 34 C42 46 44 54 40 62 C36 68 28 68 24 62 C20 54 26 44 32 34 Z", "#fff3a8", None, 0)
    out("flame", s)

    s = S(128, 128)
    s.shadow(64, 118, 56, 8)
    block(s, 6, 12, 116, 34, 76, "#c3c9d6", "#8d96ab", 12)
    for x in (30, 64, 98):
        s.circle(x, 28, 8, s.grad("#6b7288", "#3a3f52"), OUT, 4)
    s.rect(20, 56, 88, 50, 10, "#2a2c3a", OUT, 5)
    s.rect(28, 62, 72, 38, 6, s.grad("#4a4f68", "#262836"), None, 0)
    s.shine(48, 70, 18, 4, 0.35, -10)
    s.rect(30, 50, 68, 8, 4, s.grad("#eef0f6", "#9aa1b6"), OUT, 4)
    out("oven", s)
    s = S(128, 128)
    s.rect(28, 62, 72, 38, 6, s.grad("#ffd36b", "#ff7a1f"), None, 0)
    s.rect(28, 62, 72, 38, 6, s.radial("#fff3a8", "#ff7a1f", 0.9, 0.0), None, 0)
    out("oven_glow", s)

    s = S(128, 128)
    s.shadow(64, 118, 56, 8)
    block(s, 6, 14, 116, 78, 24, "#c9b6e0", "#8a76a8")
    s.ell(64, 56, 42, 30, s.grad("#ffffff", "#dfe3ee"), "#9aa0b4", 4)
    s.ell(64, 56, 30, 21, "#f4f6fb", "#c7ccdb", 3)
    s.shine(46, 42, 10, 3, 0.8)
    out("plate_station", s)

    s = S(128, 128)
    s.shadow(64, 118, 46, 7)
    s.path("M26 50 L36 112 Q64 120 92 112 L102 50 Z", s.grad("#7f8aa3", "#4d566c"), OUT, 5)
    for x in (48, 64, 80):
        s.line(x - 4 + (x - 64) * 0.1, 62, x - 2 + (x - 64) * 0.18, 102, "#3a4256", 4, 0.7)
    s.path("M18 48 Q64 30 110 48 L106 60 Q64 46 22 60 Z", s.grad("#9aa5bf", "#6a7690"), OUT, 5)
    s.ell(64, 38, 18, 8, "#3a4256", OUT, 4)
    s.shine(40, 52, 8, 2.5, 0.7)
    out("bin", s)


# --------------------------------------------------------------- food items (96x96)
def items():
    def veg(s):
        s.shadow(48, 84, 30, 6)
        s.circle(48, 50, 34, s.grad("#a9dc64", "#5c9c3a"))
        s.path("M20 52 Q48 24 76 52", "none", "#3f7a2a", 4)
        s.path("M28 66 Q48 40 68 66", "none", "#3f7a2a", 4)
        s.path("M48 20 L48 80", "none", "#3f7a2a", 3)
        s.shine(34, 34, 12, 5, 0.65)

    def meat(s):
        s.shadow(48, 82, 32, 6)
        s.path("M14 52 C14 28 40 18 62 22 C84 26 88 48 78 64 C68 80 36 82 22 72 C16 68 14 60 14 52 Z", s.grad("#ff8d9a", "#d3405a"))
        s.path("M24 54 C26 38 42 30 58 32 C74 34 76 48 68 58 C58 70 36 70 28 64 C25 61 24 58 24 54 Z", "#ffd9de", None, 0, 0.8)
        s.circle(66, 40, 9, "#fff1e6", OUT, 4)
        s.shine(34, 32, 12, 4, 0.7)

    def dough(s):
        s.shadow(48, 82, 30, 6)
        s.circle(48, 50, 33, s.grad("#fff7e3", "#e5cf9c"))
        s.shine(36, 36, 12, 5, 0.8)
        for (x, y) in [(60, 60), (40, 66), (64, 42)]:
            s.circle(x, y, 2.2, "#ffffff", None, 0, 0.8)

    def veg_chop(s):
        s.shadow(48, 82, 32, 6)
        for (x, y, c) in [(30, 58, "#7bc043"), (52, 64, "#f7a541"), (66, 52, "#7bc043"), (40, 42, "#f7a541"), (58, 34, "#7bc043"), (28, 36, "#e84f3d"), (70, 70, "#f7a541")]:
            s.rect(x - 11, y - 11, 22, 22, 6, s.grad(shade(c, 0.25), shade(c, -0.1)), OUT, 4)
            s.rect(x - 5, y - 6, 8, 5, 2, "#ffffff", None, 0, 0.4)

    def meat_chop(s):
        s.shadow(48, 82, 32, 6)
        for (x, y) in [(30, 60), (52, 66), (66, 54), (40, 44), (58, 36), (28, 40), (70, 70), (46, 56)]:
            s.circle(x, y, 12, s.grad("#ff9aa6", "#d0455d"), OUT, 4)
            s.shine(x - 3, y - 4, 4, 2, 0.7)

    def veg_cook(s):
        s.shadow(48, 84, 34, 6)
        s.path("M12 48 Q48 60 84 48 Q84 82 48 84 Q12 82 12 48 Z", s.grad("#d8d3e0", "#9a95a8"), OUT, 5)
        s.ell(48, 48, 36, 12, s.grad("#e6993a", "#b56a1c"), OUT, 4)
        for (x, y) in [(32, 46), (52, 50), (66, 44), (44, 42)]:
            s.circle(x, y, 5, "#7bc043", OUT, 3)
        s.shine(30, 40, 8, 2.5, 0.6)

    def meat_cooked(s):
        s.shadow(48, 82, 32, 6)
        s.path("M14 52 C14 28 40 18 62 22 C84 26 88 48 78 64 C68 80 36 82 22 72 C16 68 14 60 14 52 Z", s.grad("#a8693a", "#5a3318"))
        for i in range(4):
            s.line(26 + i * 14, 30 + i * 3, 38 + i * 14, 66 + i * 2, "#2e180a", 5, 0.75)
        s.shine(34, 32, 12, 4, 0.45)

    def patty(s):
        s.shadow(48, 82, 32, 6)
        s.circle(48, 50, 33, s.grad("#9c6232", "#5a3318"))
        for (x, y) in [(36, 40), (58, 36), (62, 58), (38, 62), (50, 50)]:
            s.circle(x, y, 4, "#3a1f0e", None, 0, 0.7)
        s.shine(36, 34, 11, 4, 0.5)

    def bun(s):
        s.shadow(48, 82, 34, 6)
        s.path("M10 66 C8 30 34 14 48 14 C62 14 88 30 86 66 Q48 80 10 66 Z", s.grad("#f5b550", "#d17d22"))
        for (x, y, r) in [(34, 34, -30), (50, 28, 10), (66, 36, 40), (44, 46, 20), (60, 52, -20)]:
            s.ell(x, y, 5, 2.8, "#fff6d0", None, 0, 1, r)
        s.shine(30, 28, 12, 4, 0.5)

    def burnt(s):
        s.shadow(48, 82, 30, 6)
        s.path("M14 56 C10 34 30 22 48 24 C70 24 86 38 82 58 C80 74 56 82 40 78 C24 76 16 68 14 56 Z", s.grad("#4a4a52", "#17171b"), "#000000", 5)
        s.circle(36, 46, 5, "#6a6a74", None, 0, 0.6)
        s.circle(60, 60, 4, "#6a6a74", None, 0, 0.6)
        s.shine(32, 36, 9, 3, 0.25)

    for name, fn in [("veg", veg), ("meat", meat), ("dough", dough), ("veg_chop", veg_chop), ("meat_chop", meat_chop), ("veg_cook", veg_cook),
                     ("meat_cooked", meat_cooked), ("patty", patty), ("bun", bun), ("burnt", burnt)]:
        s = S(96, 96)
        fn(s)
        out("item_" + name, s)


# --------------------------------------------------------------- dishes (128x128, on a plate)
def dishes():
    def plate(s):
        s.shadow(64, 108, 50, 8, 0.3)
        s.ell(64, 68, 54, 40, s.grad("#ffffff", "#d9deea"), "#8f96ab", 5)
        s.ell(64, 66, 40, 29, "#f6f8fc", "#c9cfdf", 3)

    s = S(128, 128)
    plate(s)
    out("plate", s)

    s = S(128, 128)
    plate(s)
    for (x, y, r, c) in [(46, 62, 20, "#7bc043"), (80, 58, 20, "#8fd14f"), (62, 48, 20, "#6aae35"), (62, 74, 20, "#86c946"), (90, 74, 14, "#7bc043"), (38, 78, 14, "#6aae35")]:
        s.circle(x, y, r, s.grad(shade(c, 0.2), shade(c, -0.12)), OUT, 4)
    s.path("M40 56 Q56 44 70 58", "none", "#3f7a2a", 3)
    for (x, y) in [(58, 60), (84, 70), (44, 76)]:
        s.circle(x, y, 8, s.grad("#ff7a5a", "#d63f2b"), OUT, 4)
        s.shine(x - 2, y - 3, 3, 1.5, 0.8)
    s.rect(70, 82, 10, 10, 4, "#f7a541", OUT, 3)
    s.shine(46, 48, 10, 4, 0.5)
    out("dish_salad", s)

    s = S(128, 128)
    plate(s)
    s.path("M26 66 C24 44 54 36 76 40 C98 44 102 66 92 80 C80 96 46 96 32 84 C28 80 26 74 26 66 Z", s.grad("#b0733f", "#5e3519"))
    for i in range(4):
        s.line(40 + i * 14, 48 + i * 2, 50 + i * 14, 84 + i, "#2e180a", 5, 0.75)
    s.shine(48, 48, 14, 4, 0.5)
    for (x, y, r) in [(94, 56, 11), (104, 70, 9), (86, 44, 8)]:
        s.circle(x, y, r, s.grad("#9fd45c", "#4f8f2e"), OUT, 4)
    s.circle(56, 78, 8, "#ffd166", OUT, 3)
    out("dish_steak", s)

    s = S(128, 128)
    s.shadow(64, 108, 50, 8, 0.3)
    s.path("M12 62 Q64 80 116 62 Q112 112 64 114 Q16 112 12 62 Z", s.grad("#ff9a62", "#d85a2c"))
    s.ell(64, 62, 52, 20, s.grad("#e08a2f", "#b4561b"))
    s.ell(64, 62, 44, 15, s.grad("#f2a640", "#d27425"), None, 0)
    for (x, y) in [(40, 60), (64, 66), (86, 60), (56, 56)]:
        s.circle(x, y, 7, "#7bc043", OUT, 3)
    s.circle(76, 56, 5, "#ffd166", OUT, 3)
    s.shine(36, 56, 12, 3, 0.6, -8)
    s.rect(26, 86, 76, 8, 4, "#ffffff", None, 0, 0.22)
    out("dish_soup", s)

    s = S(128, 128)
    plate(s)
    s.path("M24 80 Q64 98 104 80 L104 86 Q64 106 24 86 Z", s.grad("#f0a53c", "#c4721c"))
    s.rect(20, 64, 88, 20, 10, s.grad("#9c6232", "#5a3318"))
    s.path("M16 62 Q26 54 36 62 Q46 54 56 62 Q66 54 76 62 Q86 54 96 62 Q106 54 114 62 L112 68 L18 68 Z", s.grad("#9fd45c", "#4f8f2e"), OUT, 4)
    s.path("M26 52 L102 52 L98 62 L30 62 Z", s.grad("#ffd23f", "#f0a81c"), OUT, 4)
    s.path("M20 52 C18 22 44 12 64 12 C84 12 110 22 108 52 Q64 62 20 52 Z", s.grad("#f5b550", "#d17d22"))
    for (x, y, r) in [(44, 30, -30), (62, 24, 10), (82, 30, 35), (54, 40, 20), (74, 42, -20)]:
        s.ell(x, y, 6, 3.4, "#fff6d0", None, 0, 1, r)
    s.shine(44, 24, 14, 5, 0.5)
    out("dish_burger", s)


if __name__ == "__main__":
    tiles()
    stations()
    items()
    dishes()
    try:
        import characters
        characters.make(out)
    except ImportError:
        pass
    try:
        import ui_art
        ui_art.make(out)
    except ImportError:
        pass
    print("art written to", DST)
