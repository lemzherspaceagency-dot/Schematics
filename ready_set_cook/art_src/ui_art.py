from lib import S, OUT, shade
import math


def star_pts(cx, cy, r, n=5, inner=0.5):
    pts = []
    for i in range(n * 2):
        rad = r if i % 2 == 0 else r * inner
        a = -math.pi / 2 + i * math.pi / n
        pts.append((round(cx + math.cos(a) * rad, 2), round(cy + math.sin(a) * rad, 2)))
    return pts


def make(out):
    s = S(72, 72)
    s.circle(36, 36, 30, s.grad("#ffe27a", "#f0a81c"))
    s.circle(36, 36, 21, s.grad("#f9c43a", "#e69a12"), "#b5740c", 3)
    s.path("M30 28 L42 28 M36 28 L36 46 M30 46 L42 46", "none", "#b5740c", 4)
    s.shine(26, 22, 10, 4, 0.7)
    out("coin", s)

    for name, c1, c2 in [("star_on", "#ffe27a", "#f5a50f"), ("star_off", "#6d7088", "#4b4e66")]:
        s = S(128, 128)
        s.poly(star_pts(64, 68, 54, 5, 0.52), s.grad(c1, c2), OUT, 6)
        if name == "star_on":
            s.shine(50, 48, 14, 5, 0.7)
        out(name, s)

    s = S(64, 64)
    s.path("M32 56 C4 36 8 10 24 10 C30 10 32 16 32 18 C32 16 34 10 40 10 C56 10 60 36 32 56 Z", s.grad("#ff6b81", "#d92b4b"), OUT, 4)
    s.shine(22, 22, 6, 3, 0.7)
    out("heart", s)

    # speech bubble, tail on top (points at the customer above)
    s = S(240, 200)
    s.path("M104 34 L120 6 L136 34 Z", "#ffffff", OUT, 6)
    s.rect(8, 28, 224, 164, 34, s.grad("#ffffff", "#e8ecf6"))
    s.rect(110, 31, 20, 8, 0, "#ffffff", None, 0)
    s.rect(20, 38, 200, 8, 4, "#ffffff", None, 0, 0.7)
    out("bubble", s)

    # 9-slice button: white-ish so it can be tinted with modulate
    s = S(96, 112)
    s.rect(4, 22, 88, 86, 30, "#9a9a9a", OUT, 6)
    s.rect(4, 6, 88, 86, 30, s.grad("#ffffff", "#dcdcdc"), OUT, 6)
    s.rect(16, 14, 64, 10, 5, "#ffffff", None, 0, 0.75)
    out("btn", s)
    s = S(96, 112)
    s.rect(4, 22, 88, 86, 30, "#7a7a7a", OUT, 6)
    s.rect(4, 14, 88, 86, 30, s.grad("#efefef", "#c9c9c9"), OUT, 6)
    out("btn_down", s)

    # 9-slice panel
    s = S(96, 96)
    s.rect(4, 10, 88, 82, 26, "#9a9a9a", None, 0, 0.5)
    s.rect(4, 4, 88, 82, 26, s.grad("#ffffff", "#e6e6ee"), OUT, 5)
    s.rect(14, 10, 68, 8, 4, "#ffffff", None, 0, 0.7)
    out("panel", s)

    s = S(64, 64)
    s.circle(32, 32, 30, s.radial("#ffffff", "#ffffff", 0.9, 0.0), None, 0)
    out("puff", s)
    s = S(128, 128)
    s.circle(64, 64, 62, s.radial("#fff3a8", "#ffd23f", 0.95, 0.0), None, 0)
    out("glow", s)
    s = S(48, 48)
    s.path("M24 2 Q27 21 46 24 Q27 27 24 46 Q21 27 2 24 Q21 21 24 2 Z", "#fff6c8", "#f5b50f", 2)
    out("spark", s)

    # wall decor
    s = S(80, 140)
    s.line(40, 0, 40, 46, "#2a2c3a", 4)
    s.path("M12 94 C12 62 24 46 40 46 C56 46 68 62 68 94 Z", s.grad("#ff8a5c", "#d6502b"))
    s.ell(40, 96, 30, 7, "#ffe9a8", OUT, 4)
    s.shine(28, 64, 8, 4, 0.6)
    out("lamp", s)
    s = S(160, 160)
    s.circle(80, 80, 70, s.radial("#ffd98a", "#ffd98a", 0.55, 0.0), None, 0)
    out("lamp_glow", s)
    s = S(96, 150)
    s.line(48, 0, 48, 26, "#2a2c3a", 4)
    s.circle(48, 34, 7, "#8d96ab", OUT, 4)
    s.circle(48, 96, 44, s.grad("#9aa3bb", "#5b6580"))
    s.circle(48, 96, 34, s.grad("#4a5268", "#2e3446"), OUT, 4)
    s.rect(40, 36, 16, 44, 7, s.grad("#c68b4e", "#8d5629"))
    s.shine(30, 78, 10, 4, 0.45)
    out("wall_pan", s)
    s = S(110, 110)
    s.circle(55, 55, 48, s.grad("#ffffff", "#dde2ee"), OUT, 6)
    s.circle(55, 55, 40, "#f6f8fc", "#c9cfdf", 3)
    for i in range(12):
        a = i * math.pi / 6
        s.line(55 + math.cos(a) * 34, 55 + math.sin(a) * 34, 55 + math.cos(a) * 38, 55 + math.sin(a) * 38, "#4a5268", 3)
    s.line(55, 55, 55, 28, "#2a2c3a", 5)
    s.line(55, 55, 74, 62, "#2a2c3a", 5)
    s.circle(55, 55, 5, "#ef476f", OUT, 3)
    out("wall_clock", s)
    s = S(170, 120)
    s.rect(6, 78, 158, 16, 6, s.grad("#c68b4e", "#8d5629"))
    for (x, c) in [(28, "#ef476f"), (68, "#ffd166"), (108, "#7bc043")]:
        s.rect(x - 18, 30, 36, 50, 8, s.grad(shade(c, 0.3), c), OUT, 4)
        s.rect(x - 14, 20, 28, 14, 5, s.grad("#e6e9f2", "#9aa1b6"), OUT, 4)
        s.shine(x - 8, 46, 4, 8, 0.5, 0)
    out("wall_shelf", s)

    # banner ribbon for titles
    s = S(480, 120)
    s.path("M0 30 L50 30 L50 100 L0 100 L20 65 Z", s.grad("#d94a3a", "#a82a1f"))
    s.path("M480 30 L430 30 L430 100 L480 100 L460 65 Z", s.grad("#d94a3a", "#a82a1f"))
    s.rect(30, 8, 420, 90, 14, s.grad("#ff7b54", "#e0482a"))
    s.rect(46, 14, 388, 12, 6, "#ffffff", None, 0, 0.35)
    out("ribbon", s)
