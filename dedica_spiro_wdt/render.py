#!/usr/bin/env python3
"""Preview renders + simulated needle pattern for Spiro51 (writes to ./out)."""
import math, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import generate as g

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def draw(ax, man, color, alpha=1.0):
    m = man.to_mesh()
    v = np.array(m.vert_properties)[:, :3]
    f = np.array(m.tri_verts)
    tris = v[f]
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    light = np.array([0.4, -0.6, 0.7]); light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.clip(n @ light, 0, 1)
    base = np.array(matplotlib.colors.to_rgb(color))
    cols = np.clip(base[None] * shade[:, None], 0, 1)
    pc = Poly3DCollection(tris, facecolors=np.c_[cols, np.full(len(cols), alpha)],
                          linewidths=0)
    ax.add_collection3d(pc)


def setup(ax, r=36, z=(-25, 40), elev=28, azim=-60):
    ax.set_xlim(-r, r); ax.set_ylim(-r, r); ax.set_zlim(*z)
    ax.set_box_aspect((2 * r, 2 * r, z[1] - z[0]))
    ax.view_init(elev=elev, azim=azim); ax.set_axis_off()


def needles_3d():
    from manifold3d import Manifold
    a = g.center_distance()
    parts = []
    for x, y, _ in g.needle_positions():
        n = Manifold.cylinder(31, 0.3, 0.3, 8).translate(
            (a + x, y, g.PLANET_Z0 + g.PLANET_T - 31))
        parts.append(n)
    return sum(parts[1:], parts[0])


def main():
    asm, parts = g.main()
    cut = g.box(80, 80, 80, cy=-40, z0=-40)       # remove front half
    fig = plt.figure(figsize=(16, 8), dpi=110)
    ax = fig.add_subplot(1, 2, 1, projection="3d")
    for name, col in [("base", "#2b2b2b"), ("carrier", "#c0392b"),
                      ("knob", "#c0392b")]:
        draw(ax, asm[name], col)
    setup(ax, z=(-5, 40)); ax.set_title("Assembled", fontsize=14)
    ax = fig.add_subplot(1, 2, 2, projection="3d")
    for name, col in [("base", "#2b2b2b"), ("planet", "#e67e22"),
                      ("carrier", "#c0392b"), ("knob", "#c0392b")]:
        draw(ax, asm[name] - cut, col)
    draw(ax, needles_3d() - cut, "#bbbbbb")
    setup(ax, z=(-22, 40), elev=12, azim=-80)
    ax.set_title("Cut-away (planet + needles inside)", fontsize=14)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "preview_assembly.png"))
    plt.close()

    fig = plt.figure(figsize=(18, 5), dpi=100)
    colors = {"base": "#2b2b2b", "planet": "#e67e22", "carrier": "#c0392b",
              "knob": "#c0392b", "stand": "#555555"}
    for i, (name, m) in enumerate(parts.items()):
        ax = fig.add_subplot(1, 5, i + 1, projection="3d")
        pm = g.print_orientation(name, m)
        draw(ax, pm, colors[name])
        setup(ax, r=34, z=(0, 34), elev=35, azim=-55)
        ax.set_title(f"{name} (print orientation)", fontsize=11)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "preview_parts.png"))
    plt.close()

    # needle pattern simulation
    a = g.center_distance()
    ratio = 1 - g.Z_RING / g.Z_PLANET
    fig, axs = plt.subplots(1, 4, figsize=(16, 4.4), dpi=100)
    for ax, turns in zip(axs, [1, 3, 6, 10]):
        t = np.linspace(0, 2 * math.pi * turns, 6000 * turns)
        ax.add_patch(plt.Circle((0, 0), 25.5, color="#3b2314"))
        for x, y, _ in g.needle_positions():
            ang = math.atan2(y, x); d = math.hypot(x, y)
            px = a * np.cos(t) + d * np.cos(t * ratio + ang)
            py = a * np.sin(t) + d * np.sin(t * ratio + ang)
            ax.plot(px, py, color="#f3e6d3", lw=1.1, alpha=0.85)
        ax.set_xlim(-27, 27); ax.set_ylim(-27, 27); ax.set_aspect("equal")
        ax.set_axis_off(); ax.set_title(f"{turns} turn{'s' * (turns > 1)}")
    fig.suptitle("Simulated needle paths in a 51 mm basket", fontsize=13)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "preview_pattern.png"))
    plt.close()


if __name__ == "__main__":
    main()
