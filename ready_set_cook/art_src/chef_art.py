"""Tintable chef layers (white shaded art that the game multiplies by the player's chosen colours)."""
from lib import S, OUT, shade

W_TOP, W_BOT = "#ffffff", "#d8d8e0"


def make(out):
    # ---- skin head (tintable) on a 112x120 canvas, head circle centre (56,68) r38
    s = S(112, 120)
    cx, cy = 56, 68
    s.circle(cx - 38, cy + 2, 9, s.grad(W_TOP, W_BOT))
    s.circle(cx + 38, cy + 2, 9, s.grad(W_TOP, W_BOT))
    s.circle(cx, cy, 38, s.grad(W_TOP, "#e2e2ea"))
    s.shine(cx - 18, cy - 20, 10, 4, 0.5)
    out("chef_skin", s)
    s = S(112, 120)
    s.circle(cx - 23, cy + 12, 7, "#ff6b81", None, 0, 0.38)
    s.circle(cx + 23, cy + 12, 7, "#ff6b81", None, 0, 0.38)
    out("chef_blush", s)

    # ---- hats, canvas 128x100, bottom edge at y~96
    s = S(128, 100)    # toque
    s.rect(30, 62, 68, 32, 8, s.grad(W_TOP, W_BOT))
    s.circle(44, 40, 24, s.grad(W_TOP, W_BOT))
    s.circle(84, 40, 24, s.grad(W_TOP, W_BOT))
    s.circle(64, 30, 28, s.grad(W_TOP, W_BOT))
    for x in (48, 64, 80):
        s.line(x, 62, x, 90, "#000000", 3, 0.15)
    s.shine(50, 22, 12, 5, 0.6)
    out("hat_toque", s)
    s = S(128, 100)    # cap with brim
    s.path("M26 88 C22 40 48 22 66 22 C90 22 108 42 104 88 Z", s.grad(W_TOP, W_BOT))
    s.path("M70 80 L124 80 C128 80 128 92 120 92 L70 92 Z", s.grad(W_TOP, "#c9c9d2"))
    s.circle(64, 22, 6, W_TOP)
    s.shine(52, 40, 12, 5, 0.5)
    out("hat_cap", s)
    s = S(128, 100)    # beanie
    s.path("M24 90 C20 34 48 16 66 16 C90 16 110 36 104 90 Z", s.grad(W_TOP, W_BOT))
    s.rect(20, 74, 88, 20, 8, s.grad(W_TOP, "#cfcfd8"))
    for x in (34, 50, 66, 82, 98):
        s.line(x, 76, x, 92, "#000000", 3, 0.15)
    s.circle(64, 12, 11, s.grad(W_TOP, W_BOT))
    out("hat_beanie", s)
    s = S(128, 100)    # bandana
    s.path("M18 94 C16 54 36 44 64 44 C92 44 112 54 110 94 C96 80 32 80 18 94 Z", s.grad(W_TOP, W_BOT))
    s.path("M104 80 L124 70 L120 96 Z", s.grad(W_TOP, W_BOT))
    s.path("M104 80 L126 90 L112 100 Z", s.grad(W_TOP, W_BOT))
    for (x, y) in [(40, 66), (64, 58), (88, 66)]:
        s.circle(x, y, 4, "#000000", None, 0, 0.18)
    out("hat_bandana", s)
    s = S(128, 100)    # tall fancy hat with band
    s.rect(32, 8, 64, 84, 12, s.grad(W_TOP, W_BOT))
    s.rect(32, 66, 64, 14, 0, "#000000", None, 0, 0.18)
    s.shine(48, 26, 8, 12, 0.5, 0)
    out("hat_tall", s)

    s = S(128, 100)    # hair (for "no hat")
    s.path("M22 92 C14 40 44 16 64 16 C88 16 114 38 106 92 C98 62 84 52 64 52 C44 52 30 64 22 92 Z", s.grad(W_TOP, W_BOT))
    s.shine(48, 30, 12, 5, 0.5)
    out("hat_hair", s)

    # ---- jacket, apron, scarf (120x110, same frame as the old body)
    s = S(120, 110)
    s.shadow(60, 102, 40, 6, 0.2)
    s.path("M12 106 C8 54 26 26 60 26 C94 26 112 54 108 106 Z", s.grad(W_TOP, W_BOT))
    s.shine(36, 44, 10, 4, 0.5)
    out("chef_jacket", s)
    s = S(120, 110)
    s.path("M12 106 C8 54 26 26 60 26 C94 26 112 54 108 106 Z", "none", OUT, 5)
    for y in (62, 80):
        s.circle(60, y, 4.5, "#c9cfde", OUT, 3)
    out("chef_jacket_line", s)
    s = S(120, 110)
    s.path("M36 52 L84 52 L104 106 L16 106 Z", s.grad(W_TOP, W_BOT))
    s.rect(46, 84, 28, 16, 5, "#000000", None, 0, 0.12)
    out("chef_apron", s)
    s = S(120, 110)
    s.path("M42 26 L60 56 L78 26 Z", s.grad(W_TOP, W_BOT))
    out("chef_scarf", s)
    s = S(32, 32)
    s.circle(16, 16, 12, s.grad(W_TOP, "#dcdce4"))
    s.shine(12, 11, 4, 2, 0.6)
    out("hand", s)
    s = S(48, 30)
    s.path("M4 24 C4 8 18 4 28 6 C40 8 44 14 44 24 Z", s.grad(W_TOP, "#c8c8d4"))
    s.shine(16, 12, 6, 2.5, 0.5)
    out("shoe", s)

    # ---- accessories (drawn in head canvas coordinates, eyes at +-18)
    s = S(112, 120)
    for sx in (-1, 1):
        s.circle(56 + sx * 18, 66, 14, "#ffffff", OUT, 4, 0.28)
    s.line(56 - 4, 64, 56 + 4, 64, OUT, 4)
    out("acc_glasses", s)
    s = S(112, 120)
    for sx in (-1, 1):
        s.rect(56 + sx * 18 - 15, 56, 30, 22, 9, s.grad("#4a4a58", "#14141c"), OUT, 4)
    s.line(56 - 3, 62, 56 + 3, 62, OUT, 4)
    s.shine(40, 62, 6, 2, 0.5, 0)
    out("acc_sunglasses", s)
    s = S(112, 120)
    s.path("M30 92 C38 78 52 84 56 90 C60 84 74 78 82 92 C74 100 62 96 56 94 C50 96 38 100 30 92 Z", s.grad("#6b4a32", "#2e1d12"), OUT, 4)
    out("acc_mustache", s)
    s = S(112, 120)
    s.path("M22 74 C20 108 40 124 56 124 C72 124 92 108 90 74 C84 92 72 96 56 96 C40 96 28 92 22 74 Z", s.grad("#6b4a32", "#2e1d12"), OUT, 4)
    out("acc_beard", s)

    # ---- VIP crown and gold aura
    s = S(80, 60)
    s.path("M8 50 L8 18 L26 32 L40 8 L54 32 L72 18 L72 50 Z", s.grad("#ffe27a", "#f0a81c"), OUT, 4)
    for (x, y, c) in [(26, 42, "#ef476f"), (40, 42, "#4cc9f0"), (54, 42, "#06d6a0")]:
        s.circle(x, y, 4, c, OUT, 2)
    s.shine(24, 28, 5, 2, 0.7)
    out("vip_crown", s)
