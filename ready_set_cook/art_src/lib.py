# Tiny SVG builder used by gen_art.py. Style: chunky dark outline, 2-stop gradients, glossy highlights.
OUT = "#3b2618"
SW = 5


class S:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.defs = []
        self.body = []
        self.n = 0

    def grad(self, top, bot, horizontal=False):
        self.n += 1
        gid = "g%d" % self.n
        x2, y2 = ("1", "0") if horizontal else ("0", "1")
        self.defs.append('<linearGradient id="%s" x1="0" y1="0" x2="%s" y2="%s"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient>' % (gid, x2, y2, top, bot))
        return "url(#%s)" % gid

    def radial(self, inner, outer, inner_a=1.0, outer_a=0.0):
        self.n += 1
        gid = "r%d" % self.n
        self.defs.append('<radialGradient id="%s"><stop offset="0" stop-color="%s" stop-opacity="%s"/><stop offset="1" stop-color="%s" stop-opacity="%s"/></radialGradient>' % (gid, inner, inner_a, outer, outer_a))
        return "url(#%s)" % gid

    def add(self, s):
        self.body.append(s)

    def _paint(self, fill, stroke, sw):
        st = ' stroke="%s" stroke-width="%s" stroke-linejoin="round" stroke-linecap="round"' % (stroke, sw) if stroke else ""
        return 'fill="%s"%s' % (fill, st)

    def rect(self, x, y, w, h, r, fill, stroke=OUT, sw=SW, op=1.0):
        self.add('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" %s opacity="%s"/>' % (x, y, w, h, r, self._paint(fill, stroke, sw), op))

    def ell(self, cx, cy, rx, ry, fill, stroke=OUT, sw=SW, op=1.0, rot=0):
        t = ' transform="rotate(%s %s %s)"' % (rot, cx, cy) if rot else ""
        self.add('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" %s opacity="%s"%s/>' % (cx, cy, rx, ry, self._paint(fill, stroke, sw), op, t))

    def circle(self, cx, cy, r, fill, stroke=OUT, sw=SW, op=1.0):
        self.add('<circle cx="%s" cy="%s" r="%s" %s opacity="%s"/>' % (cx, cy, r, self._paint(fill, stroke, sw), op))

    def path(self, d, fill="none", stroke=OUT, sw=SW, op=1.0):
        self.add('<path d="%s" %s opacity="%s"/>' % (d, self._paint(fill, stroke, sw), op))

    def poly(self, pts, fill, stroke=OUT, sw=SW):
        self.add('<polygon points="%s" %s/>' % (" ".join("%s,%s" % p for p in pts), self._paint(fill, stroke, sw)))

    def line(self, x1, y1, x2, y2, col=OUT, sw=SW, op=1.0):
        self.add('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s" stroke-linecap="round" opacity="%s"/>' % (x1, y1, x2, y2, col, sw, op))

    def shine(self, cx, cy, rx, ry, op=0.55, rot=-25):
        self.ell(cx, cy, rx, ry, "#ffffff", None, 0, op, rot)

    def shadow(self, cx, cy, rx, ry, op=0.28):
        self.ell(cx, cy, rx, ry, "#000000", None, 0, op)

    def save(self, path):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d"><defs>%s</defs>%s</svg>' % (self.w, self.h, self.w, self.h, "".join(self.defs), "".join(self.body))
        open(path, "w").write(svg)


def shade(hexcol, f):
    # f > 0 lighten toward white, f < 0 darken toward black
    c = hexcol.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    if f >= 0:
        r, g, b = [int(v + (255 - v) * f) for v in (r, g, b)]
    else:
        r, g, b = [int(v * (1 + f)) for v in (r, g, b)]
    return "#%02x%02x%02x" % (r, g, b)
