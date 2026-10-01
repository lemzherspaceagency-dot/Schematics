"""Floor / wall / carpet tiles for the three kitchen worlds."""
from lib import S, OUT, shade


def faint(s, op):
    s.body[-1] = s.body[-1].replace("/>", ' opacity="%s"/>' % op)


def make(out):
    # ------------------------------------------------ world 0: cozy diner (cream tile, blue brick, purple rug)
    for name, (c1, c2) in {"floor_0a": ("#f8eedb", "#efe1c6"), "floor_0b": ("#f1e5cc", "#e6d7b8")}.items():
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
            s.line(off + k * 64, y, off + k * 64, y + 32, "#2a3558", 4, 0.9)
    s.rect(0, 0, 128, 10, 0, "#ffffff", None, 0, 0.12)
    out("wall_0", s)
    for name, (c1, c2) in {"carpet_0a": ("#6a559c", "#5b4789"), "carpet_0b": ("#5f4c90", "#503f7d")}.items():
        s = S(128, 128)
        s.rect(0, 0, 128, 128, 0, s.grad(c1, c2), None, 0)
        for (cx, cy) in [(32, 32), (96, 32), (32, 96), (96, 96), (64, 64)]:
            s.poly([(cx, cy - 14), (cx + 14, cy), (cx, cy + 14), (cx - 14, cy)], "#ffffff", None, 0)
            faint(s, 0.10)
        s.line(0, 126, 128, 126, "#000000", 4, 0.15)
        out(name, s)

    # ------------------------------------------------ world 1: bistro (mint tile, red brick, teal rug)
    for name, (c1, c2) in {"floor_1a": ("#f2fbf6", "#d9efe3"), "floor_1b": ("#b9ddcd", "#a6cfbd")}.items():
        s = S(128, 128)
        s.rect(0, 0, 128, 128, 0, s.grad(c1, c2), None, 0)
        s.line(0, 126, 128, 126, "#8fb9a6", 4, 0.8)
        s.line(126, 0, 126, 128, "#8fb9a6", 4, 0.8)
        s.line(2, 2, 126, 2, "#ffffff", 4, 0.6)
        s.line(2, 2, 2, 126, "#ffffff", 4, 0.6)
        s.circle(64, 64, 22, "#ffffff", None, 0)
        faint(s, 0.18)
        out(name, s)
    s = S(128, 128)
    s.rect(0, 0, 128, 128, 0, s.grad("#c0583f", "#9a3f2c"), None, 0)
    for row in range(4):
        y = row * 32
        s.line(0, y, 128, y, "#6e2a1c", 4, 0.9)
        off = 0 if row % 2 == 0 else 32
        for k in range(-1, 4):
            s.line(off + k * 64, y, off + k * 64, y + 32, "#6e2a1c", 4, 0.9)
    s.rect(0, 0, 128, 10, 0, "#ffffff", None, 0, 0.14)
    out("wall_1", s)
    for name, (c1, c2) in {"carpet_1a": ("#2f8a92", "#256f77"), "carpet_1b": ("#2a7d85", "#216269")}.items():
        s = S(128, 128)
        s.rect(0, 0, 128, 128, 0, s.grad(c1, c2), None, 0)
        for (cx, cy) in [(32, 32), (96, 32), (32, 96), (96, 96)]:
            s.circle(cx, cy, 12, "#ffffff", None, 0)
            faint(s, 0.10)
        s.circle(64, 64, 18, "#ffd166", None, 0)
        faint(s, 0.18)
        s.line(0, 126, 128, 126, "#000000", 4, 0.15)
        out(name, s)

    # ------------------------------------------------ world 2: grand hall (dark wood, green panel, burgundy rug)
    for name, (c1, c2) in {"floor_2a": ("#c4915f", "#a87848"), "floor_2b": ("#b8864f", "#9a6c3e")}.items():
        s = S(128, 128)
        s.rect(0, 0, 128, 128, 0, s.grad(c1, c2), None, 0)
        for y in (32, 64, 96):
            s.line(0, y, 128, y, "#6e4624", 4, 0.8)
        for (x, y0) in [(40, 0), (90, 32), (20, 64), (70, 96)]:
            s.line(x, y0, x, y0 + 32, "#6e4624", 4, 0.8)
        for (x, y) in [(20, 16), (70, 48), (100, 80), (40, 112)]:
            s.line(x, y, x + 24, y, "#ffffff", 3, 0.18)
        out(name, s)
    s = S(128, 128)
    s.rect(0, 0, 128, 128, 0, s.grad("#3f7a68", "#2a5a4b"), None, 0)
    s.rect(10, 18, 108, 92, 6, "#ffffff", None, 0, 0.0)
    s.rect(12, 20, 104, 90, 8, s.grad("#356b5a", "#2a5a4b"), "#e9c46a", 4)
    s.rect(0, 0, 128, 10, 0, "#e9c46a", None, 0, 0.9)
    s.rect(0, 0, 128, 14, 0, "#ffffff", None, 0, 0.1)
    out("wall_2", s)
    for name, (c1, c2) in {"carpet_2a": ("#8a3447", "#722a3a"), "carpet_2b": ("#7d2f40", "#66263a")}.items():
        s = S(128, 128)
        s.rect(0, 0, 128, 128, 0, s.grad(c1, c2), None, 0)
        s.rect(8, 8, 112, 112, 6, "none", "#e9c46a", 3, 0.5)
        for (cx, cy) in [(64, 64)]:
            s.poly([(cx, cy - 22), (cx + 22, cy), (cx, cy + 22), (cx - 22, cy)], "#e9c46a", None, 0)
            faint(s, 0.22)
        s.line(0, 126, 128, 126, "#000000", 4, 0.15)
        out(name, s)
