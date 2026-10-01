from lib import S, OUT, shade

SKINS = ["#ffd5b5", "#f1c27d", "#d9a066", "#a8714a", "#7a4a2d", "#ffe0c8"]
HAIRS = ["#3b2f2f", "#a0522d", "#f4d35e", "#1f1f24", "#c1440e", "#8338ec", "#e8e8f0"]
SHIRTS = ["#ef476f", "#06d6a0", "#118ab2", "#ffd166", "#9b5de5", "#ff9f1c"]

# every head is drawn on a 112x120 canvas, head circle centre (56, 68), radius 38
HEAD_C = (56, 68)


def head(skin, hair, style):
    s = S(112, 120)
    cx, cy = HEAD_C
    hair_c = s.grad(shade(hair, 0.18), shade(hair, -0.15))
    if style == 2:      # long hair behind
        s.rect(12, 38, 88, 76, 34, hair_c)
    if style == 4:      # afro puffs behind
        for (x, y, r) in [(24, 44, 22), (88, 44, 22), (56, 22, 30), (36, 28, 22), (76, 28, 22)]:
            s.circle(x, y, r, hair_c)
    # ears
    s.circle(cx - 38, cy + 2, 9, s.grad(shade(skin, 0.1), shade(skin, -0.1)))
    s.circle(cx + 38, cy + 2, 9, s.grad(shade(skin, 0.1), shade(skin, -0.1)))
    # face
    s.circle(cx, cy, 38, s.grad(shade(skin, 0.18), shade(skin, -0.08)))
    s.circle(cx - 23, cy + 12, 7, "#ff6b81", None, 0, 0.35)
    s.circle(cx + 23, cy + 12, 7, "#ff6b81", None, 0, 0.35)
    s.shine(cx - 18, cy - 20, 10, 4, 0.35)
    # hair front
    if style == 0:      # short with side fringe
        s.path("M18 62 C14 22 46 14 60 18 C84 18 98 38 94 62 C86 44 70 38 52 40 C38 42 26 50 18 62 Z", hair_c, OUT, 5)
    elif style == 1:    # top bun
        s.circle(cx, 12, 15, hair_c)
        s.path("M18 62 C16 28 38 20 56 20 C76 20 96 28 94 62 C84 44 70 40 56 40 C40 40 26 46 18 62 Z", hair_c, OUT, 5)
    elif style == 2:    # long straight with fringe
        s.path("M16 66 C12 24 40 14 58 16 C84 16 100 34 96 66 C88 46 74 38 56 38 C38 38 24 48 16 66 Z", hair_c, OUT, 5)
    elif style == 3:    # cap
        s.path("M16 58 C14 22 44 12 58 12 C82 12 100 28 96 58 Z", s.grad("#ef476f", "#b0233f"), OUT, 5)
        s.path("M52 52 L108 52 C112 52 112 60 106 60 L52 60 Z", s.grad("#d63a5c", "#9a1d38"), OUT, 5)
        s.circle(56, 14, 6, "#ffffff", OUT, 4)
    elif style == 4:    # afro front
        s.path("M20 52 C24 26 44 22 56 24 C70 22 90 28 92 52 C80 40 68 38 56 38 C44 38 32 40 20 52 Z", hair_c, OUT, 5)
    else:               # tuft / spiky
        s.path("M18 60 L26 24 L40 40 L52 14 L66 40 L82 20 L94 60 C84 44 70 40 56 40 C40 40 26 46 18 60 Z", hair_c, OUT, 5)
    return s


def body(shirt, skin):
    s = S(112, 96)
    s.shadow(56, 88, 40, 6, 0.22)
    s.path("M10 92 C8 50 26 30 56 30 C86 30 104 50 102 92 Z", s.grad(shade(shirt, 0.2), shade(shirt, -0.2)))
    s.path("M40 31 Q56 56 72 31", s.grad(skin, shade(skin, -0.1)), OUT, 5)
    s.path("M40 31 Q56 56 72 31", "none", OUT, 5)
    s.rect(18, 66, 76, 7, 3, "#ffffff", None, 0, 0.22)
    return s


def make(out):
    # ---- chef
    s = S(128, 150)
    cx, cy = 64, 100
    # hat
    s.rect(30, 46, 68, 26, 8, s.grad("#ffffff", "#dde2ee"))
    s.circle(44, 34, 24, s.grad("#ffffff", "#e6eaf4"))
    s.circle(84, 34, 24, s.grad("#ffffff", "#e6eaf4"))
    s.circle(64, 24, 28, s.grad("#ffffff", "#e6eaf4"))
    s.line(48, 52, 48, 70, "#c9cfde", 3)
    s.line(64, 52, 64, 70, "#c9cfde", 3)
    s.line(80, 52, 80, 70, "#c9cfde", 3)
    s.shine(50, 16, 12, 5, 0.6)
    # head
    s.circle(cx - 40, cy + 2, 9, "#f2c4a0")
    s.circle(cx + 40, cy + 2, 9, "#f2c4a0")
    s.circle(cx, cy, 38, s.grad("#ffe3cb", "#f5c9a6"))
    s.circle(cx - 24, cy + 12, 7, "#ff6b81", None, 0, 0.4)
    s.circle(cx + 24, cy + 12, 7, "#ff6b81", None, 0, 0.4)
    s.rect(30, 58, 68, 10, 4, s.grad("#ffffff", "#dde2ee"))
    s.shine(cx - 18, cy - 16, 10, 4, 0.4)
    out("chef_head", s)

    s = S(120, 110)
    s.shadow(60, 102, 40, 6, 0.2)
    s.path("M12 106 C8 54 26 26 60 26 C94 26 112 54 108 106 Z", s.grad("#ffffff", "#d8deea"))
    s.rect(20, 76, 80, 28, 8, s.grad("#4cc9f0", "#1d96c4"))     # apron
    s.path("M44 26 L60 52 L76 26 Z", s.grad("#ff6b6b", "#c9304b"))   # neckerchief
    for y in (60, 76):
        s.circle(60, y, 4.5, "#c9cfde", OUT, 3)
    s.shine(36, 44, 10, 4, 0.5)
    out("chef_body", s)

    s = S(32, 32)
    s.circle(16, 16, 12, s.grad("#ffe3cb", "#f0bd98"))
    s.shine(12, 11, 4, 2, 0.6)
    out("hand", s)
    s = S(48, 30)
    s.path("M4 24 C4 8 18 4 28 6 C40 8 44 14 44 24 Z", s.grad("#5b6bbf", "#343f8a"))
    s.shine(16, 12, 6, 2.5, 0.5)
    out("shoe", s)

    # ---- customers: 6 looks
    specs = [(SKINS[0], HAIRS[0], SHIRTS[0], 0), (SKINS[1], HAIRS[2], SHIRTS[1], 1), (SKINS[3], HAIRS[3], SHIRTS[2], 2),
             (SKINS[2], HAIRS[1], SHIRTS[3], 3), (SKINS[4], HAIRS[3], SHIRTS[4], 4), (SKINS[5], HAIRS[5], SHIRTS[5], 5)]
    for i, (skin, hair, shirt, style) in enumerate(specs):
        out("cust_head_%d" % i, head(skin, hair, style))
        out("cust_body_%d" % i, body(shirt, skin))

