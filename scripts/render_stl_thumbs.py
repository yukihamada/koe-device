#!/usr/bin/env python3
"""Render all STL files in docs/stl/ to PNG thumbnails using matplotlib.
Output: docs/stl/thumbs/<name>.png (512x512, transparent bg)
"""
import os
import sys
from pathlib import Path
import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.colors import LightSource

ROOT = Path(__file__).resolve().parent.parent
STL_DIR = ROOT / "docs" / "stl"
OUT_DIR = STL_DIR / "thumbs"
OUT_DIR.mkdir(exist_ok=True)

KOE_PURPLE = "#8B5CF6"
BG = (0.039, 0.039, 0.043, 1.0)  # #0a0a0b

def render(stl_path: Path, out_path: Path, size: int = 512):
    mesh = trimesh.load_mesh(str(stl_path))
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])

    mesh.apply_translation(-mesh.centroid)
    # normalize scale to fit in unit sphere
    scale = 1.0 / max(mesh.extents.max(), 1e-6)
    mesh.apply_scale(scale)

    verts = mesh.vertices
    faces = mesh.faces
    tris = verts[faces]

    fig = plt.figure(figsize=(size/100, size/100), dpi=100)
    fig.patch.set_alpha(0.0)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor((0, 0, 0, 0))
    ax.set_axis_off()

    # Shade faces by normal dot product with a key light direction
    normals = mesh.face_normals
    light_dir = np.array([0.5, -0.3, 1.0])
    light_dir /= np.linalg.norm(light_dir)
    shade = np.clip(normals @ light_dir, 0.08, 1.0)

    base = np.array([0.92, 0.92, 0.96])
    tint = np.array([0.55, 0.36, 0.96])  # Koe purple edge tint
    colors = np.zeros((len(faces), 4))
    for i, s in enumerate(shade):
        c = base * s + tint * (1 - s) * 0.15
        colors[i] = [c[0], c[1], c[2], 1.0]

    collection = Poly3DCollection(tris, facecolors=colors, edgecolors=(0, 0, 0, 0.0), linewidths=0)
    ax.add_collection3d(collection)

    lim = 0.55
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_zlim(-lim, lim)
    ax.set_box_aspect([1, 1, 1])
    ax.view_init(elev=22, azim=35)

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(out_path, dpi=100, transparent=True, bbox_inches=None, pad_inches=0)
    plt.close(fig)

def main():
    stls = sorted(STL_DIR.glob("*.stl"))
    print(f"Rendering {len(stls)} STL files → {OUT_DIR}")
    for stl in stls:
        out = OUT_DIR / (stl.stem + ".png")
        try:
            render(stl, out)
            print(f"  OK  {stl.name} → {out.name}")
        except Exception as e:
            print(f"  ERR {stl.name}: {e}")

if __name__ == "__main__":
    main()
