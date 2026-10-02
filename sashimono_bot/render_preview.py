"""Render preview.png of the assembled robot with a small numpy z-buffer rasteriser."""
import numpy as np, trimesh as tm
from PIL import Image, ImageDraw
import sys; sys.path.insert(0, '../scorpion_bot')
from build_scorpion import AXLE_X, AXLE_Z, WELL_Y0

names = ["chassis", "lid", "carapace", "kabuto", "katana", "banner", "wheel"]
chassis, lid, carapace, kabuto, katana, banner, wheel = [tm.load(f"{n}.stl") for n in names]
wheels = []
for sgn in (1, -1):
    w = wheel.copy(); w.apply_translation([AXLE_X, sgn * (WELL_Y0 + 1.5 + 6), AXLE_Z]); wheels.append(w)
COL = {"chassis": (45, 45, 55), "kabuto": (150, 25, 30), "wheel": (30, 30, 30), "lid": (80, 80, 90),
       "carapace": (170, 35, 40), "katana": (205, 210, 220), "banner": (235, 235, 225)}
def render(parts, elev, azim, size=(900, 700), scale=3.9):
    W, H = size
    a, e = np.radians(azim), np.radians(elev)
    # camera basis: right, up, forward(view dir)
    fwd = -np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    right = np.cross(fwd, [0, 0, 1]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    light = np.array([0.3, -0.6, 0.8]); light /= np.linalg.norm(light)
    img = np.full((H, W, 3), 245, np.uint8); zb = np.full((H, W), np.inf)
    center = np.array([18, 0, 55])
    for mesh, col in parts:
        tri = mesh.triangles - center
        px = tri @ right * scale + W / 2; py = H / 2 - (tri @ up) * scale; pz = tri @ fwd
        nrm = mesh.face_normals
        shade = np.clip(np.abs(nrm @ light), 0, 1) * 0.6 + 0.4
        facing = nrm @ fwd < 0
        for i in np.nonzero(facing)[0]:
            x, y, z = px[i], py[i], pz[i]
            x0, x1 = int(max(x.min(), 0)), int(min(x.max() + 1, W - 1)); y0, y1 = int(max(y.min(), 0)), int(min(y.max() + 1, H - 1))
            if x1 <= x0 or y1 <= y0: continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
            d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
            if abs(d) < 1e-9: continue
            l0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
            l1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
            l2 = 1 - l0 - l1
            m = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            zz = l0 * z[0] + l1 * z[1] + l2 * z[2]
            sub = zb[y0:y1 + 1, x0:x1 + 1]; upd = m & (zz < sub)
            sub[upd] = zz[upd]
            img[y0:y1 + 1, x0:x1 + 1][upd] = (np.array(col) * shade[i]).astype(np.uint8)
    return Image.fromarray(img)

base = [(chassis, COL["chassis"]), (kabuto, COL["kabuto"])] + [(w, COL["wheel"]) for w in wheels]
full = base + [(lid, COL["lid"]), (carapace, COL["carapace"]), (katana, COL["katana"]), (banner, COL["banner"])]
views = [("Front 3/4", full, 24, -40), ("Rear 3/4 (sashimono)", full, 20, 215),
         ("Top", full, 82, -90), ("Side", full, 4, -90)]
tiles = []
for t, parts, e, a in views:
    im = render(parts, e, a); ImageDraw.Draw(im).text((12, 10), t, fill=(30, 30, 30)); tiles.append(im)
out = Image.new("RGB", (tiles[0].width * 2, tiles[0].height * 2), (245, 245, 245))
for i, im in enumerate(tiles): out.paste(im, ((i % 2) * im.width, (i // 2) * im.height))
out.save("preview.png")
