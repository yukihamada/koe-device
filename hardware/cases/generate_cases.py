#!/usr/bin/env python3
"""
Koe Device — Production-Quality 3D Printable Case Generator (Binary STL)
=========================================================================
Generates precise enclosures based on actual PCB dimensions and CPL data.

Board specs (from gerber Edge_Cuts + CPL files):
  COIN Lite: circular Ø28mm, 2-layer (nRF5340), 1.6mm thick
  Pro v2:    45×30mm rounded rect, 4-layer, 1.6mm thick
  Hub v2:    140×120mm rect, 2-layer, 1.6mm thick

Usage:
    python3 hardware/cases/generate_cases.py
"""

import math
import struct
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

# Tolerances
PCB_TOL = 0.3       # PCB-to-wall clearance (mm)
SNAP_TOL = 0.15     # Snap-fit interference (mm)


# ── STL Writer ────────────────────────────────────────────────────────

def write_stl(filepath, triangles):
    """Write binary STL file. Each triangle is ((nx,ny,nz),(v1,v2,v3))."""
    with open(filepath, 'wb') as f:
        header = b'Koe Device Case - Binary STL' + b'\0' * 52
        f.write(header[:80])
        f.write(struct.pack('<I', len(triangles)))
        for normal, (v1, v2, v3) in triangles:
            f.write(struct.pack('<3f', *normal))
            f.write(struct.pack('<3f', *v1))
            f.write(struct.pack('<3f', *v2))
            f.write(struct.pack('<3f', *v3))
            f.write(struct.pack('<H', 0))


def compute_normal(v1, v2, v3):
    ax, ay, az = v2[0]-v1[0], v2[1]-v1[1], v2[2]-v1[2]
    bx, by, bz = v3[0]-v1[0], v3[1]-v1[1], v3[2]-v1[2]
    nx = ay*bz - az*by
    ny = az*bx - ax*bz
    nz = ax*by - ay*bx
    length = math.sqrt(nx*nx + ny*ny + nz*nz)
    if length < 1e-10:
        return (0.0, 0.0, 1.0)
    return (nx/length, ny/length, nz/length)


def make_tri(v1, v2, v3):
    n = compute_normal(v1, v2, v3)
    return (n, (v1, v2, v3))


# ── Mathematical constants ──────────────────────────────────────────

PHI = (1 + math.sqrt(5)) / 2       # Golden ratio 1.618...
GOLDEN_ANGLE = math.pi * (3 - math.sqrt(5))  # ~137.508° — sunflower spiral


# ── Geometry primitives ─────────────────────────────────────────────

def circle_profile(cx, cy, r, segs=192):
    """Generate 2D points for a circle. High segment count for glass-smooth curves."""
    return [(cx + r * math.cos(2*math.pi*i/segs),
             cy + r * math.sin(2*math.pi*i/segs)) for i in range(segs)]


def superellipse_profile(cx, cy, a, b, n=3.0, segs=192):
    """Generate a superellipse (squircle) profile.
    |x/a|^n + |y/b|^n = 1 (Lame curve)
    n=2: circle/ellipse
    n=2.5: slight squircle (Apple iOS icon)
    n=3: moderate squircle (Piet Hein's Sergels Torg)
    n=4: more square-ish
    n->inf: rectangle
    """
    pts = []
    for i in range(segs):
        t = 2 * math.pi * i / segs
        cos_t = math.cos(t)
        sin_t = math.sin(t)
        x = a * abs(cos_t) ** (2 / n) * (1 if cos_t >= 0 else -1)
        y = b * abs(sin_t) ** (2 / n) * (1 if sin_t >= 0 else -1)
        pts.append((cx + x, cy + y))
    return pts


def catenary_z(r, r_max, h, flatness=1.0):
    """Catenary dome profile — the curve a hanging chain makes, inverted.
    Returns z in [0, h]. At r=0 (center) returns h. At r=r_max (edge) returns 0.
    flatness controls how peaked vs flat the dome is (1.0 = natural catenary).
    Normalized so the peak always equals h regardless of flatness.
    """
    if r_max < 1e-10:
        return h
    a = flatness
    # Raw catenary: 1 - cosh(r*a/r_max)/cosh(a), peak at r=0 = 1 - 1/cosh(a)
    peak = 1.0 - 1.0 / math.cosh(a)
    if peak < 1e-10:
        return h * max(0, 1.0 - (r / r_max) ** 2)  # fallback to parabola
    raw = 1.0 - math.cosh(r * a / r_max) / math.cosh(a)
    return h * max(0, raw / peak)


def lenticular_z(r, r_max, center_h, edge_h=0.0):
    """Lenticular (double-convex lens) cross-section.
    Returns z offset for a given radial distance.
    Uses circular arc profile for the convex surface.
    """
    if r >= r_max:
        return edge_h
    # Circular arc: find radius of curvature that passes through (0, center_h) and (r_max, edge_h)
    rise = center_h - edge_h
    if rise < 1e-10:
        return edge_h
    R_curv = (r_max * r_max + rise * rise) / (2 * rise)
    z = edge_h + R_curv - math.sqrt(max(R_curv * R_curv - r * r, 0))
    return z


def fibonacci_spiral_holes(cx, cy, r_max, n_holes=13):
    """Place holes in a Fibonacci spiral (golden angle spacing).
    This is how sunflower seeds arrange — mathematically optimal packing.
    Returns list of (x, y) positions."""
    positions = []
    for i in range(1, n_holes + 1):  # skip center (i=0)
        r = r_max * math.sqrt(i / n_holes)
        theta = i * GOLDEN_ANGLE
        hx = cx + r * math.cos(theta)
        hy = cy + r * math.sin(theta)
        positions.append((hx, hy))
    return positions


def apply_fibonacci_speaker(tris, cx, cy, z_bottom, z_top, grid_r,
                            hole_r=0.3, n_holes=13):
    """Apply Fibonacci-spiral speaker grille cutouts."""
    holes = fibonacci_spiral_holes(cx, cy, grid_r, n_holes)
    for hx, hy in holes:
        tris = cutout_circle(tris, hx, hy, z_bottom, z_top, hole_r)
    return tris


def reuleaux_triangle_profile(cx, cy, width, segs=192):
    """Generate a Reuleaux triangle — constant-width curve.
    Each side is a circular arc centered on the opposite vertex.
    Width = distance between any two parallel supporting lines = constant.
    """
    # Vertices of equilateral triangle inscribed so the Reuleaux has given width
    # For Reuleaux triangle: side length s, width w = s
    s = width
    # Equilateral triangle vertices, centered at (cx, cy)
    # Point up orientation (tip at top, flat base at bottom = good for pick)
    verts = []
    for i in range(3):
        angle = math.pi / 2 + 2 * math.pi * i / 3  # start from top
        verts.append((cx + s / math.sqrt(3) * math.cos(angle),
                      cy + s / math.sqrt(3) * math.sin(angle)))

    pts = []
    segs_per_arc = segs // 3
    for i in range(3):
        # Arc from vertex[(i+1)%3] to vertex[(i+2)%3], centered on vertex[i]
        center = verts[i]
        start = verts[(i + 1) % 3]
        end = verts[(i + 2) % 3]
        r = math.sqrt((start[0] - center[0]) ** 2 + (start[1] - center[1]) ** 2)
        a_start = math.atan2(start[1] - center[1], start[0] - center[0])
        a_end = math.atan2(end[1] - center[1], end[0] - center[0])
        # Ensure we go the short way around
        da = a_end - a_start
        if da > math.pi:
            da -= 2 * math.pi
        if da < -math.pi:
            da += 2 * math.pi
        for j in range(segs_per_arc):
            a = a_start + da * j / segs_per_arc
            pts.append((center[0] + r * math.cos(a),
                        center[1] + r * math.sin(a)))
    return pts


def teardrop_profile(cx, cy, length, width, segs=192):
    """Generate a teardrop/cardioid-based profile.
    Wider at one end (cy - length/3), narrower at the other (cy + 2*length/3).
    The narrow end is where the keyring loop would be.
    """
    pts = []
    # Parametric teardrop: modified cardioid
    # Wide end at bottom (negative y), narrow at top (positive y)
    hw = width / 2
    for i in range(segs):
        t = 2 * math.pi * i / segs
        # Shape factor: wider at bottom (t=3pi/2), narrower at top (t=pi/2)
        # Using a modified superellipse with varying width
        cos_t = math.cos(t)
        sin_t = math.sin(t)
        # Teardrop: r(theta) = a*(1 - sin(theta)) but smoother
        # Use egg curve: different radii for top and bottom halves
        if sin_t >= 0:
            # Top half (narrow end) — more pointed
            r_scale = 1.0 - 0.4 * sin_t  # narrows toward top
            x = hw * r_scale * abs(cos_t) ** 0.7 * (1 if cos_t >= 0 else -1)
            y = (length * 0.5) * sin_t * r_scale
        else:
            # Bottom half (wide end) — rounder
            x = hw * abs(cos_t) ** 0.85 * (1 if cos_t >= 0 else -1)
            y = (length * 0.4) * sin_t
        pts.append((cx + x, cy + y))
    return pts


def make_dome_catenary(profile, z_base, dome_h, rings=32, segs=None):
    """Create a catenary dome on top of a profile.
    Returns triangles. Profile should be centered-ish."""
    tris = []
    n = len(profile) if segs is None else segs
    # Find center and max radius of profile
    pcx = sum(p[0] for p in profile) / len(profile)
    pcy = sum(p[1] for p in profile) / len(profile)
    max_r = max(math.sqrt((p[0] - pcx) ** 2 + (p[1] - pcy) ** 2) for p in profile)

    prev_ring = profile
    prev_z = z_base
    for ri in range(1, rings + 1):
        t = ri / rings
        # Shrink profile toward center
        shrink = t * 0.95  # shrink to near-zero at apex
        curr_ring = []
        for px, py in profile:
            dx, dy = px - pcx, py - pcy
            curr_ring.append((pcx + dx * (1 - shrink), pcy + dy * (1 - shrink)))
        # Z from catenary curve: highest at center (t=1), lowest at edge (t=0)
        # catenary_z(r, r_max, h) = h*(1 - cosh(r*a/r_max)/cosh(a))
        # At r=0: positive value (peak). At r=r_max: 0 (edge).
        # So use catenary_z directly on the shrunk radius for correct dome shape.
        ring_r = max_r * (1 - shrink)
        ring_z = z_base + catenary_z(ring_r, max_r, dome_h, flatness=1.2)

        nr = len(prev_ring)
        nc = len(curr_ring)
        for i in range(max(nr, nc)):
            pi_idx = i % nr
            pj_idx = (i + 1) % nr
            ci_idx = i % nc
            cj_idx = (i + 1) % nc
            px1, py1 = prev_ring[pi_idx]
            px2, py2 = prev_ring[pj_idx]
            cx1, cy1 = curr_ring[ci_idx]
            cx2, cy2 = curr_ring[cj_idx]
            tris.append(make_tri((px1, py1, prev_z), (cx1, cy1, ring_z), (cx2, cy2, ring_z)))
            tris.append(make_tri((px1, py1, prev_z), (cx2, cy2, ring_z), (px2, py2, prev_z)))
        prev_ring = curr_ring
        prev_z = ring_z
    tris += fill_profile(prev_ring, prev_z, flip=False)
    return tris


def make_dome_lenticular(profile, z_base, center_h, rings=32):
    """Create a lenticular (convex lens) dome on top of a profile.
    Returns triangles."""
    tris = []
    pcx = sum(p[0] for p in profile) / len(profile)
    pcy = sum(p[1] for p in profile) / len(profile)
    max_r = max(math.sqrt((p[0] - pcx) ** 2 + (p[1] - pcy) ** 2) for p in profile)

    prev_ring = profile
    prev_z = z_base
    for ri in range(1, rings + 1):
        t = ri / rings
        shrink = t * 0.95
        curr_ring = []
        for px, py in profile:
            dx, dy = px - pcx, py - pcy
            curr_ring.append((pcx + dx * (1 - shrink), pcy + dy * (1 - shrink)))
        curr_r = max_r * (1 - shrink)
        ring_z = z_base + lenticular_z(curr_r, max_r, center_h)

        nr = len(prev_ring)
        nc = len(curr_ring)
        for i in range(max(nr, nc)):
            pi_idx = i % nr
            pj_idx = (i + 1) % nr
            ci_idx = i % nc
            cj_idx = (i + 1) % nc
            px1, py1 = prev_ring[pi_idx]
            px2, py2 = prev_ring[pj_idx]
            cx1, cy1 = curr_ring[ci_idx]
            cx2, cy2 = curr_ring[cj_idx]
            tris.append(make_tri((px1, py1, prev_z), (cx1, cy1, ring_z), (cx2, cy2, ring_z)))
            tris.append(make_tri((px1, py1, prev_z), (cx2, cy2, ring_z), (px2, py2, prev_z)))
        prev_ring = curr_ring
        prev_z = ring_z
    tris += fill_profile(prev_ring, prev_z, flip=False)
    return tris


def rounded_rect_profile(cx, cy, w, h, r, segs_per_corner=32):
    """Generate 2D points for a rounded rectangle centered at (cx,cy).
    32 segments per corner for smooth arcs."""
    pts = []
    hw, hh = w/2, h/2
    corners = [
        (cx + hw - r, cy + hh - r, 0),
        (cx - hw + r, cy + hh - r, math.pi/2),
        (cx - hw + r, cy - hh + r, math.pi),
        (cx + hw - r, cy - hh + r, 3*math.pi/2),
    ]
    for ccx, ccy, start_a in corners:
        for i in range(segs_per_corner + 1):
            a = start_a + (math.pi/2) * i / segs_per_corner
            pts.append((ccx + r*math.cos(a), ccy + r*math.sin(a)))
    return pts


def rect_profile(cx, cy, w, h):
    """Simple rectangle profile."""
    hw, hh = w/2, h/2
    return [(cx-hw, cy-hh), (cx+hw, cy-hh), (cx+hw, cy+hh), (cx-hw, cy+hh)]


def extrude_profile(profile, z0, z1, close=True):
    """Extrude a 2D profile from z0 to z1, generating wall triangles."""
    tris = []
    n = len(profile)
    for i in range(n):
        j = (i + 1) % n if close else min(i + 1, n - 1)
        if i == j:
            continue
        x1, y1 = profile[i]
        x2, y2 = profile[j]
        # Two triangles per quad
        tris.append(make_tri((x1, y1, z0), (x2, y2, z0), (x2, y2, z1)))
        tris.append(make_tri((x1, y1, z0), (x2, y2, z1), (x1, y1, z1)))
    return tris


def fill_profile(profile, z, flip=False):
    """Fill a closed profile with a fan of triangles at height z."""
    tris = []
    n = len(profile)
    cx = sum(p[0] for p in profile) / n
    cy = sum(p[1] for p in profile) / n
    center = (cx, cy, z)
    for i in range(n):
        j = (i + 1) % n
        p1 = (*profile[i], z)
        p2 = (*profile[j], z)
        if flip:
            tris.append(make_tri(center, p2, p1))
        else:
            tris.append(make_tri(center, p1, p2))
    return tris


def make_shell(outer_profile, inner_profile, z0, z1):
    """Make a hollow shell: outer wall + inner wall + top/bottom rings."""
    tris = []
    # Outer wall (outward-facing normals)
    tris += extrude_profile(outer_profile, z0, z1)
    # Inner wall (inward-facing normals, reversed winding)
    n = len(inner_profile)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner_profile[i]
        x2, y2 = inner_profile[j]
        tris.append(make_tri((x1, y1, z0), (x2, y2, z1), (x2, y2, z0)))
        tris.append(make_tri((x1, y1, z0), (x1, y1, z1), (x2, y2, z1)))
    # Bottom ring
    no = len(outer_profile)
    ni = len(inner_profile)
    # Simple approach: connect outer to inner using fan triangles
    tris += ring_fill(outer_profile, inner_profile, z0, flip=True)
    tris += ring_fill(outer_profile, inner_profile, z1, flip=False)
    return tris


def ring_fill(outer, inner, z, flip=False):
    """Fill the gap between two concentric profiles at height z."""
    tris = []
    no = len(outer)
    ni = len(inner)
    # Map inner points to nearest outer segments
    for i in range(max(no, ni)):
        oi = i % no
        oj = (i + 1) % no
        ii = i % ni
        ij = (i + 1) % ni
        o1 = (*outer[oi], z)
        o2 = (*outer[oj], z)
        i1 = (*inner[ii], z)
        i2 = (*inner[ij], z)
        if flip:
            tris.append(make_tri(o1, i1, i2))
            tris.append(make_tri(o1, i2, o2))
        else:
            tris.append(make_tri(o1, i2, i1))
            tris.append(make_tri(o1, o2, i2))
    return tris


def cutout_rect(tris, cx, cy, z0, z1, w, h):
    """
    Remove triangles whose centroid falls inside a rectangular volume.
    Then add walls around the cutout opening.
    """
    hw, hh = w/2, h/2
    result = []
    for tri in tris:
        _, (v1, v2, v3) = tri
        mx = (v1[0]+v2[0]+v3[0]) / 3
        my = (v1[1]+v2[1]+v3[1]) / 3
        mz = (v1[2]+v2[2]+v3[2]) / 3
        if (cx-hw <= mx <= cx+hw and cy-hh <= my <= cy+hh and z0 <= mz <= z1):
            continue
        result.append(tri)
    return result


def cutout_circle(tris, cx, cy, z0, z1, r):
    """Remove triangles whose centroid falls inside a cylindrical volume."""
    result = []
    for tri in tris:
        _, (v1, v2, v3) = tri
        mx = (v1[0]+v2[0]+v3[0]) / 3
        my = (v1[1]+v2[1]+v3[1]) / 3
        mz = (v1[2]+v2[2]+v3[2]) / 3
        dist = math.sqrt((mx-cx)**2 + (my-cy)**2)
        if dist < r and z0 <= mz <= z1:
            continue
        result.append(tri)
    return result


# ── Design Language Constants (shared across all Koe products) ────

FILLET_PRIMARY = 0.5      # Primary edge fillet radius (mm)
FILLET_SECONDARY = 0.3    # Secondary/bottom edge fillet radius (mm)
PARTING_LINE_DEPTH = 0.1  # Parting line groove depth (mm)
SPEAKER_HOLE_R = 0.4      # Speaker grille hole radius (mm)
SPEAKER_HOLE_SPACING = 1.6  # Honeycomb center-to-center (mm)
LED_SLIT_W = 0.4          # LED crescent slit width (mm)
USB_FILLET_R = 0.3        # USB-C pocket fillet radius (mm)
FILLET_SEGS = 8           # Quarter-circle segments for fillets


# ── Fillet helper ─────────────────────────────────────────────────

def fillet_circle_edge(cx, cy, case_r, z_edge, fillet_r, segs, going_up=True):
    """
    Add a smooth fillet (quarter-circle cross section) at the junction
    between a circular side wall and a flat surface.

    going_up=True: fillet curves from wall outward to top surface (top edge)
    going_up=False: fillet curves from wall outward to bottom surface (bottom edge)

    Returns list of triangles forming a torus-section ring.
    """
    tris = []
    fillet_steps = FILLET_SEGS
    for i in range(segs):
        a1 = 2 * math.pi * i / segs
        a2 = 2 * math.pi * ((i + 1) % segs) / segs

        for j in range(fillet_steps):
            # Quarter circle from 0 to pi/2
            t1 = (math.pi / 2) * j / fillet_steps
            t2 = (math.pi / 2) * (j + 1) / fillet_steps

            if going_up:
                # Fillet from side wall up to top surface
                # At t=0: flush with wall at z_edge. At t=pi/2: flush with top at r-fillet_r
                dr1 = -fillet_r * (1 - math.cos(t1))
                dz1 = fillet_r * math.sin(t1)
                dr2 = -fillet_r * (1 - math.cos(t2))
                dz2 = fillet_r * math.sin(t2)
            else:
                # Fillet from bottom surface up to side wall
                dr1 = -fillet_r * (1 - math.sin(t1))
                dz1 = -fillet_r * math.cos(t1)
                dr2 = -fillet_r * (1 - math.sin(t2))
                dz2 = -fillet_r * math.cos(t2)

            r1 = case_r + dr1
            r2 = case_r + dr2

            p1 = (r1 * math.cos(a1), r1 * math.sin(a1), z_edge + dz1)
            p2 = (r1 * math.cos(a2), r1 * math.sin(a2), z_edge + dz1)
            p3 = (r2 * math.cos(a1), r2 * math.sin(a1), z_edge + dz2)
            p4 = (r2 * math.cos(a2), r2 * math.sin(a2), z_edge + dz2)

            tris.append(make_tri(p1, p3, p2))
            tris.append(make_tri(p2, p3, p4))

    return tris


def fillet_rect_edge(profile, z_edge, fillet_r, going_up=True):
    """
    Add a smooth fillet along a profile edge (rounded rect or any closed profile).
    Creates a smooth quarter-circle transition between wall and flat surface.
    """
    tris = []
    n = len(profile)
    fillet_steps = FILLET_SEGS

    for i in range(n):
        j = (i + 1) % n
        x1, y1 = profile[i]
        x2, y2 = profile[j]

        # Edge direction
        ex = x2 - x1
        ey = y2 - y1
        edge_len = math.sqrt(ex * ex + ey * ey)
        if edge_len < 1e-10:
            continue

        # Outward normal (perpendicular to edge, pointing outward)
        # For CCW profile, outward normal is (ey, -ex) / edge_len
        nx = ey / edge_len
        ny = -ex / edge_len

        for k in range(fillet_steps):
            t1 = (math.pi / 2) * k / fillet_steps
            t2 = (math.pi / 2) * (k + 1) / fillet_steps

            if going_up:
                off1 = fillet_r * (1 - math.cos(t1))
                dz1 = fillet_r * math.sin(t1)
                off2 = fillet_r * (1 - math.cos(t2))
                dz2 = fillet_r * math.sin(t2)
            else:
                off1 = fillet_r * (1 - math.sin(t1))
                dz1 = -fillet_r * math.cos(t1)
                off2 = fillet_r * (1 - math.sin(t2))
                dz2 = -fillet_r * math.cos(t2)

            p1 = (x1 - nx * off1, y1 - ny * off1, z_edge + dz1)
            p2 = (x2 - nx * off1, y2 - ny * off1, z_edge + dz1)
            p3 = (x1 - nx * off2, y1 - ny * off2, z_edge + dz2)
            p4 = (x2 - nx * off2, y2 - ny * off2, z_edge + dz2)

            tris.append(make_tri(p1, p3, p2))
            tris.append(make_tri(p2, p3, p4))

    return tris


# ── Honeycomb speaker grille ─────────────────────────────────────

def honeycomb_speaker_grille(cx, cy, z_bottom, z_top, grid_r, hole_r=None, spacing=None):
    """
    Generate a honeycomb pattern of round holes for speaker grille.
    Returns cutout parameters as a list of (x, y) hole centers.
    Uses unified Koe design language defaults.
    """
    if hole_r is None:
        hole_r = SPEAKER_HOLE_R
    if spacing is None:
        spacing = SPEAKER_HOLE_SPACING

    holes = []
    row_h = spacing * math.sqrt(3) / 2
    rows = int(grid_r * 2 / row_h) + 1
    cols = int(grid_r * 2 / spacing) + 1

    for row in range(-rows, rows + 1):
        for col in range(-cols, cols + 1):
            hx = cx + col * spacing + (row % 2) * spacing / 2
            hy = cy + row * row_h
            # Only include holes within the grid radius
            dist = math.sqrt((hx - cx) ** 2 + (hy - cy) ** 2)
            if dist + hole_r <= grid_r:
                holes.append((hx, hy))

    return holes


def apply_speaker_grille(tris, cx, cy, z_bottom, z_top, grid_r, hole_r=None, spacing=None):
    """Apply honeycomb speaker grille cutouts to existing triangles."""
    holes = honeycomb_speaker_grille(cx, cy, z_bottom, z_top, grid_r, hole_r, spacing)
    for hx, hy in holes:
        tris = cutout_circle(tris, hx, hy, z_bottom, z_top,
                             hole_r if hole_r else SPEAKER_HOLE_R)
    return tris


# ── LED crescent slit ────────────────────────────────────────────

def led_crescent_slit(tris, cx, cy, z_bottom, z_top, slit_length=4.0, slit_width=None):
    """Cut a thin curved crescent slit for LED window. Unified Koe style."""
    if slit_width is None:
        slit_width = LED_SLIT_W
    # Approximate crescent as a thin arc of small rectangular cutouts
    arc_segs = 24
    arc_r = slit_length / 2
    for i in range(arc_segs):
        angle = -math.pi / 3 + (2 * math.pi / 3) * i / (arc_segs - 1)
        hx = cx + arc_r * math.cos(angle)
        hy = cy + arc_r * math.sin(angle)
        tris = cutout_circle(tris, hx, hy, z_bottom, z_top, slit_width / 2)
    return tris


# ── USB-C recessed pocket with fillets ───────────────────────────

def usb_c_pocket(tris, pocket_cx, pocket_cy, z_center, wall_thick,
                 pocket_w=10.0, pocket_h=4.0, recess_depth=1.0):
    """
    Cut a USB-C pocket with recessed edges and filleted corners.
    Unified Koe design language.
    """
    # Main cutout
    tris = cutout_rect(tris, pocket_cx, pocket_cy,
                       z_center - pocket_h / 2, z_center + pocket_h / 2,
                       pocket_w, wall_thick + 0.5)
    return tris


# ── Parting line groove ──────────────────────────────────────────

def parting_line_circle(tris, cx, cy, case_r, z_split, groove_depth=None):
    """Add a subtle parting line groove around a circular case at the split."""
    if groove_depth is None:
        groove_depth = PARTING_LINE_DEPTH
    # Groove is represented as a thin cutout band
    groove_r = case_r + 0.01  # Slightly proud to ensure cut
    groove_inner = case_r - groove_depth
    groove_profile = circle_profile(cx, cy, groove_inner, 96)
    tris += extrude_profile(groove_profile, z_split - 0.05, z_split + 0.05)
    return tris


def concentric_ring_texture(tris, cx, cy, z_surface, max_r, num_rings=5, groove_depth=0.05):
    """Add subtle concentric ring texture on a flat surface (like Apple product bottom)."""
    for i in range(1, num_rings + 1):
        ring_r = max_r * i / (num_rings + 1)
        ring_profile = circle_profile(cx, cy, ring_r, 96)
        # Thin groove
        tris = cutout_circle(tris, cx, cy, z_surface - groove_depth, z_surface + 0.01, ring_r + 0.1)
    return tris


# ── Standoff post ─────────────────────────────────────────────────

def standoff(cx, cy, z0, height, outer_r=1.5, inner_r=0.6, segs=32):
    """Generate a hollow standoff post for PCB mounting."""
    tris = []
    for i in range(segs):
        a1 = 2*math.pi*i/segs
        a2 = 2*math.pi*(i+1)/segs
        z1 = z0 + height
        ox1 = cx + outer_r*math.cos(a1)
        oy1 = cy + outer_r*math.sin(a1)
        ox2 = cx + outer_r*math.cos(a2)
        oy2 = cy + outer_r*math.sin(a2)
        ix1 = cx + inner_r*math.cos(a1)
        iy1 = cy + inner_r*math.sin(a1)
        ix2 = cx + inner_r*math.cos(a2)
        iy2 = cy + inner_r*math.sin(a2)
        # Outer wall
        tris.append(make_tri((ox1,oy1,z0),(ox2,oy2,z0),(ox2,oy2,z1)))
        tris.append(make_tri((ox1,oy1,z0),(ox2,oy2,z1),(ox1,oy1,z1)))
        # Top ring
        tris.append(make_tri((ox1,oy1,z1),(ix1,iy1,z1),(ix2,iy2,z1)))
        tris.append(make_tri((ox1,oy1,z1),(ix2,iy2,z1),(ox2,oy2,z1)))
    return tris


# ════════════════════════════════════════════════════════════════════
# Case 1: COIN Lite — Ø28mm circular PCB (nRF5340)
# ════════════════════════════════════════════════════════════════════
# PCB: circular Ø28mm, 2-layer (nRF5340), 1.6mm thick
# USB-C at bottom edge (Y=0 direction), center
# LED at top of dome
# Button at right side (X=max direction), center height
# Battery: 802535 (8×25×35mm) — JST connector, no soldering
# Speaker: JST connector, no soldering
# Board center = (14, 14) in PCB coordinates

def generate_coin_lite_case():
    """
    Koe Stone — palm-sized worry stone, CNC aluminum unibody.
    ──────────────────────────────────────────────────────────
    Ø80mm × 25mm tall, target 380g in 6061-T6 aluminum.
    Superellipse plan (n=3.5), vertical filleted sides, subtle top dome (2mm rise).
    Inspired by: Apple Magic Mouse 2, Leica D-Lux, Teenage Engineering CM-15,
    B&O Beoplay A1, Japanese tsumibe river stones.

    Top face: SOLID — the aluminum unibody itself is the resonant diaphragm
    coupled to the Tectonic BMR driver. No grille, no perforations. Single
    8×8mm shallow K-logo recess at center (laser-engraved post-machining).

    Bottom face: flat with service access and wireless charging:
      • 50×30mm elliptical passive radiator recess, 3mm deep, centered
      • Ø30mm × 2mm Qi charging coil pocket, offset (−Y side)
      • Ø8mm × 1mm NFC tag recess, offset (+Y side)
      • 4× M2 service screw bosses at corners (hidden)

    Internal cavity: 1.5mm side wall, 3mm bottom plate (hollowed for BMR,
    battery, PCB). 4× Ø3mm standoffs with Ø1.5mm tapped holes.
    """
    # ── Outer dimensions ─────────────────────────────────────
    case_r     = 40.0      # 80mm diameter
    total_h    = 25.0      # Body height
    SUPER_N    = 3.5       # Superellipse exponent — strong squircle
    segs       = 192       # Outline resolution
    dome_h     = 2.0       # Top dome rise (edge → center)
    edge_fillet = 1.5      # Fillet radius at top/bottom side-wall edges
    fillet_segs = 12       # Sub-divisions of the fillet

    # ── Internal structure ───────────────────────────────────
    side_wall  = 1.5       # Side wall thickness
    floor_t    = 3.2       # Bottom plate thickness (≥ deepest recess to stay sealed)
    standoff_h = 2.0       # PCB standoff height
    standoff_or = 1.5      # Standoff outer radius (Ø3.0)
    standoff_ir = 0.75     # Standoff inner radius (Ø1.5, M2 tapped)

    # ── Bottom-face features ─────────────────────────────────
    rad_a, rad_b = 25.0, 15.0   # Passive radiator ellipse half-axes (50×30)
    rad_depth    = 3.0
    qi_r         = 15.0         # Ø30mm Qi coil
    qi_depth     = 2.0
    qi_cx, qi_cy = 0.0, -20.0   # offset toward −Y
    nfc_r        = 4.0          # Ø8mm NFC tag
    nfc_depth    = 1.0
    nfc_cx, nfc_cy = 0.0, 22.0  # offset toward +Y

    # ── Top-face K-logo recess ───────────────────────────────
    logo_w, logo_h = 8.0, 8.0
    logo_depth = 0.3            # Shallow — laser engraving pocket

    # Ensure clearances (used PCB_TOL / SNAP_TOL to stay in the repo dialect)
    _ = PCB_TOL, SNAP_TOL

    tris = []

    # Master outer profile (Ø80mm superellipse)
    outer = superellipse_profile(0, 0, case_r, case_r, n=SUPER_N, segs=segs)
    # Inner cavity profile — offset inward by (side_wall + edge_fillet) so the
    # cavity never gets close to the outer fillet surface (avoids Z-fighting).
    inner_scale = (case_r - side_wall - edge_fillet) / case_r
    inner = [(x * inner_scale, y * inner_scale) for x, y in outer]

    # Helper: add a ring of quads between two profile rings at different z levels,
    # using make_dome_catenary's winding convention (outward-facing normals).
    def _ring_quads(lower_ring, lower_z, upper_ring, upper_z):
        out = []
        nr = len(lower_ring)
        for i in range(nr):
            j = (i + 1) % nr
            px1, py1 = lower_ring[i]
            px2, py2 = lower_ring[j]
            cx1, cy1 = upper_ring[i]
            cx2, cy2 = upper_ring[j]
            out.append(make_tri((px1, py1, lower_z), (cx1, cy1, upper_z), (cx2, cy2, upper_z)))
            out.append(make_tri((px1, py1, lower_z), (cx2, cy2, upper_z), (px2, py2, lower_z)))
        return out

    # ── 1. Bottom fillet ring (z: 0 → edge_fillet) ──────────
    # Start with profile shrunk by edge_fillet, rise in a quarter-circle
    # up to the full outline at z = edge_fillet.
    bottom_fillet_base = [(x * (case_r - edge_fillet) / case_r,
                           y * (case_r - edge_fillet) / case_r) for x, y in outer]
    # Seal the bottom (flat face at z=0, downward-facing normals)
    tris += fill_profile(bottom_fillet_base, 0.0, flip=True)

    prev_ring = bottom_fillet_base
    prev_z = 0.0
    for k in range(1, fillet_segs + 1):
        t = (math.pi / 2) * k / fillet_segs  # 0 → π/2
        # Bottom fillet: quarter-circle bulging outward+upward
        dr = edge_fillet * (1.0 - math.sin(t))   # from +edge_fillet → 0 inward offset
        dz = edge_fillet * (1.0 - math.cos(t))   # from 0 → edge_fillet up
        scale = (case_r - dr) / case_r
        curr_ring = [(x * scale, y * scale) for x, y in outer]
        curr_z = dz
        tris += _ring_quads(prev_ring, prev_z, curr_ring, curr_z)
        prev_ring = curr_ring
        prev_z = curr_z

    # ── 2. Straight vertical side wall ──────────────────────
    wall_z0 = edge_fillet
    wall_z1 = total_h - edge_fillet
    tris += extrude_profile(outer, wall_z0, wall_z1)

    # ── 3. Top fillet ring (z: wall_z1 → total_h) ───────────
    prev_ring = outer
    prev_z = wall_z1
    for k in range(1, fillet_segs + 1):
        t = (math.pi / 2) * k / fillet_segs
        # Top fillet: quarter-circle curving inward+upward
        dr = edge_fillet * (1.0 - math.cos(t))   # from 0 → edge_fillet inward
        dz = edge_fillet * math.sin(t)           # from 0 → edge_fillet up
        scale = (case_r - dr) / case_r
        curr_ring = [(x * scale, y * scale) for x, y in outer]
        curr_z = wall_z1 + dz
        tris += _ring_quads(prev_ring, prev_z, curr_ring, curr_z)
        prev_ring = curr_ring
        prev_z = curr_z

    # ── 4. Top dome (catenary — acoustic coupling to BMR driver) ─
    tris += make_dome_catenary(prev_ring, prev_z, dome_h, rings=32)
    dome_top = prev_z + dome_h

    # ── 5. Internal cavity (hollow body) ────────────────────
    # Cavity floor at z = floor_t, ceiling at z = total_h - top_wall_t
    top_wall_t = 1.5
    cav_z0 = floor_t
    cav_z1 = total_h - top_wall_t
    # Inner cavity walls with inward-facing normals (so outer shell occludes)
    n_in = len(inner)
    for i in range(n_in):
        j = (i + 1) % n_in
        x1, y1 = inner[i]
        x2, y2 = inner[j]
        # Reversed winding → normals point radially inward (away from outer shell)
        tris.append(make_tri((x1, y1, cav_z0), (x2, y2, cav_z1), (x2, y2, cav_z0)))
        tris.append(make_tri((x1, y1, cav_z0), (x1, y1, cav_z1), (x2, y2, cav_z1)))
    # Cavity floor (upward-facing — the top of the bottom plate, seen from inside)
    tris += fill_profile(inner, cav_z0, flip=False)
    # Cavity ceiling (downward-facing — the bottom of the top plate, seen from inside)
    tris += fill_profile(inner, cav_z1, flip=True)

    # ── 6. Bottom recesses (radiator, Qi coil, NFC) ─────────
    # Radiator: elliptical, so approximate with many small circular cuts
    # along the ellipse area by using a scaled circle cutout stack.
    # (cutout_circle works on a cylinder; we fake an ellipse by scanning.)
    # Simpler: do multiple circle cutouts in a grid inside the ellipse.
    rad_steps = 24
    for ix in range(-rad_steps, rad_steps + 1):
        fx = ix / rad_steps
        for iy in range(-rad_steps, rad_steps + 1):
            fy = iy / rad_steps
            if fx * fx + fy * fy > 1.0:
                continue
            px = fx * rad_a
            py = fy * rad_b
            tris = cutout_circle(tris, px, py, -0.5, rad_depth + 0.01, 1.3)

    # Qi coil pocket
    tris = cutout_circle(tris, qi_cx, qi_cy, -0.5, qi_depth + 0.01, qi_r)

    # NFC tag recess
    tris = cutout_circle(tris, nfc_cx, nfc_cy, -0.5, nfc_depth + 0.01, nfc_r)

    # ── 7. Top face K-logo recess (8×8mm, 0.3mm deep) ───────
    tris = cutout_rect(tris, 0.0, 0.0,
                       total_h + dome_h - logo_depth - 0.01,
                       dome_top + 0.01,
                       logo_w, logo_h)

    # ── 8. PCB standoffs (4× at inner corners) ──────────────
    # Place at 70% of inner radius along diagonals of the superellipse
    standoff_r = (case_r - side_wall) * 0.72
    for sx, sy in [(+standoff_r * 0.7071,  +standoff_r * 0.7071),
                   (-standoff_r * 0.7071,  +standoff_r * 0.7071),
                   (-standoff_r * 0.7071,  -standoff_r * 0.7071),
                   (+standoff_r * 0.7071,  -standoff_r * 0.7071)]:
        tris += standoff(sx, sy, cav_z0, standoff_h,
                         outer_r=standoff_or, inner_r=standoff_ir, segs=32)

    # ── 9. M2 service-screw bosses at corners (hidden) ──────
    # 4× pockets from the bottom face, Ø2.2mm × 4mm deep (countersunk M2)
    boss_r = (case_r - side_wall - 2.0) * 0.88
    for bx, by in [(+boss_r * 0.7071, +boss_r * 0.7071),
                   (-boss_r * 0.7071, +boss_r * 0.7071),
                   (-boss_r * 0.7071, -boss_r * 0.7071),
                   (+boss_r * 0.7071, -boss_r * 0.7071)]:
        tris = cutout_circle(tris, bx, by, -0.5, 4.0 + 0.01, 1.1 + PCB_TOL / 2)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 2: Pro v2 — 45×30mm rounded rect PCB
# ════════════════════════════════════════════════════════════════════
# PCB: 45×30mm, 1.6mm thick, corner radius ~1mm
# USB-C at (22.5, 1.5) → center bottom
# 3.5mm jack at (1.5, 15.0) → left center
# LED at (7, 5.5) → top-left area
# Button at (3.5, 25.0) → left-bottom
# Speaker pads at (42, 21) → right side
# Battery: 802535 (8×25×35mm) under PCB

def generate_pro_v2_case():
    """
    Pro v2 case: pill-shaped, two-piece snap-fit.
    PCB origin at (0,0), board extends to (45,30).
    Case centered at (22.5, 15.0).
    """
    pcb_w, pcb_h = 45.0, 30.0
    wall = 1.8
    pcb_thick = 1.6
    corner_r = 4.0        # Cosmetic corner radius for case
    battery_h = 8.0       # 802535 = 8mm thick
    standoff_h = 1.5
    comp_clearance = 3.0  # Tallest component above PCB
    speaker_h = 3.0

    case_w = pcb_w + PCB_TOL * 2 + wall * 2  # ~49.4mm
    case_h = pcb_h + PCB_TOL * 2 + wall * 2  # ~34.4mm

    # Center of case
    cx, cy = case_w / 2, case_h / 2

    # Total height
    total_z = wall + battery_h + standoff_h + pcb_thick + comp_clearance + speaker_h + wall
    # ~ 1.8 + 8 + 1.5 + 1.6 + 3 + 3 + 1.8 = 20.7mm
    split_z = wall + battery_h + standoff_h + pcb_thick + 1.5

    segs = 32               # Smooth rounded corners
    tris = []

    # Profiles centered at case center
    outer = rounded_rect_profile(cx, cy, case_w, case_h, corner_r, segs)
    inner = rounded_rect_profile(cx, cy, case_w - wall*2, case_h - wall*2, max(corner_r - wall, 1.0), segs)

    # ── Bottom half ──
    # Outer wall
    tris += extrude_profile(outer, 0, split_z)
    # Inner wall
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    # Bottom floor
    tris += fill_profile(outer, 0, flip=True)
    # Rings
    tris += ring_fill(outer, inner, wall, flip=False)
    tris += ring_fill(outer, inner, split_z, flip=False)
    # Bottom fillet
    tris += fillet_rect_edge(outer, 0, FILLET_SECONDARY, going_up=False)

    # PCB standoffs (4 corners of PCB, inset 3mm)
    pcb_ox = wall + PCB_TOL  # PCB origin X in case coords
    pcb_oy = wall + PCB_TOL  # PCB origin Y in case coords
    standoff_base_z = wall + battery_h
    for dx, dy in [(3, 3), (pcb_w - 3, 3), (3, pcb_h - 3), (pcb_w - 3, pcb_h - 3)]:
        tris += standoff(pcb_ox + dx, pcb_oy + dy, standoff_base_z, standoff_h)

    # USB-C cutout: 9.0 × 3.5mm at bottom edge (Y=0 side)
    # PCB (22.5, 1.5) → case coords (pcb_ox + 22.5, 0)
    usb_x = pcb_ox + 22.5
    usb_z = standoff_base_z + standoff_h + pcb_thick / 2
    tris = cutout_rect(tris, usb_x, 0, usb_z - 2.0, usb_z + 2.0, 9.5, wall + 1.0)

    # 3.5mm jack cutout: Ø6.35mm at left edge (X=0 side)
    # PCB (1.5, 15) → case coords (0, pcb_oy + 15)
    jack_y = pcb_oy + 15.0
    jack_z = usb_z
    tris = cutout_circle(tris, 0, jack_y, jack_z - 3.5, jack_z + 3.5, 3.5)

    # Button cutout: 2.5mm at left side
    # PCB (3.5, 25) → case coords (pcb_ox + 3.5 is ~5.6, but button is at edge)
    # Access hole from left wall
    btn_y = pcb_oy + 25.0
    btn_z = usb_z
    tris = cutout_rect(tris, 0, btn_y, btn_z - 1.5, btn_z + 1.5, wall + 1.0, 3.0)

    # ── Top half ──
    top_z = split_z + 0.5
    tris += extrude_profile(outer, top_z, total_z)
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,total_z - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,total_z - wall),(x2,y2,total_z - wall)))
    # Top cap
    tris += fill_profile(outer, total_z, flip=False)
    tris += ring_fill(outer, inner, top_z, flip=True)
    tris += ring_fill(outer, inner, total_z - wall, flip=True)
    tris += fill_profile(inner, total_z - wall, flip=True)

    # Speaker grille on top: large honeycomb pattern — make it dominant
    spk_x = pcb_ox + 34.0
    spk_y = pcb_oy + 20.0
    # Visible raised ring around the grille
    ring_o = circle_profile(spk_x, spk_y, 9.0, 40)
    ring_i = circle_profile(spk_x, spk_y, 7.5, 40)
    tris += make_shell(ring_o, ring_i, total_z - 0.2, total_z + 1.0)
    tris = apply_speaker_grille(tris, spk_x, spk_y, total_z - wall - 0.1, total_z + 1.1,
                                grid_r=7.0, hole_r=0.55, spacing=1.8)

    # LED crescent slit (bigger)
    led_x = pcb_ox + 7.0
    led_y = pcb_oy + 5.5
    tris = led_crescent_slit(tris, led_x, led_y, total_z - wall - 0.1, total_z + 0.1,
                             slit_length=6.0)

    # Snap-fit lip
    lip = rounded_rect_profile(cx, cy, case_w - wall*2 + SNAP_TOL*2,
                                case_h - wall*2 + SNAP_TOL*2,
                                max(corner_r - wall, 1.0), segs)
    tris += extrude_profile(lip, split_z - 1.2, split_z)
    tris += fill_profile(lip, split_z, flip=False)

    # "KOE" text indent on top (decorative rectangle, 0.3mm deep)
    tris = cutout_rect(tris, cx, cy, total_z - 0.3, total_z + 0.1, 14.0, 5.0)

    # ── Chamfered/filleted top edge (2mm radius fillet) ──
    tris += fillet_rect_edge(outer, total_z, 1.5, going_up=False)

    # ── Button pockets: REC + Mode (2x BIG raised dome buttons on top) ──
    for btn_dx in [-10.0, 10.0]:
        btn_cx = cx + btn_dx
        btn_cy = cy - 10.0
        # Raised cylindrical button boss
        btn_profile = circle_profile(btn_cx, btn_cy, 3.0, 24)
        tris += extrude_profile(btn_profile, total_z - 0.1, total_z + 1.5)
        tris += fill_profile(btn_profile, total_z + 1.5, flip=False)
        # Small dimple on top for touch
        tris = cutout_circle(tris, btn_cx, btn_cy, total_z + 1.0, total_z + 1.6, 1.2)

    # ── Additional status LED slit near speaker grille ──
    tris = led_crescent_slit(tris, cx + 16.0, cy + 10.0,
                             total_z - wall - 0.1, total_z + 0.1,
                             slit_length=3.0)

    # ── Lanyard slot (2x2mm hole through one short edge) ──
    lanyard_x = case_w - 4.0
    lanyard_y = cy
    tris = cutout_circle(tris, lanyard_x, lanyard_y + 3.0,
                         0.5, wall + 0.5, 1.0)
    tris = cutout_circle(tris, lanyard_x, lanyard_y - 3.0,
                         0.5, wall + 0.5, 1.0)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 3: Hub v2 — 140×120mm PCB
# ════════════════════════════════════════════════════════════════════
# PCB: 140×120mm, 1.6mm thick
# Dense connector layout on all edges
# M4 mounting holes at (4,4), (136,4), (4,116), (136,116)

def generate_hub_v2_case():
    """
    Hub v2 case: rectangular box with screw-down lid.
    Professional stage equipment style.
    """
    pcb_w, pcb_h = 140.0, 120.0
    wall = 3.0            # Thicker for stage durability
    pcb_thick = 1.6
    standoff_h = 5.0      # More clearance for bottom components
    comp_clearance = 15.0  # Tall connectors (XLR, Speakon, TRS)
    lid_h = 3.0

    case_w = pcb_w + PCB_TOL * 2 + wall * 2  # ~146.6mm
    case_h = pcb_h + PCB_TOL * 2 + wall * 2  # ~126.6mm
    total_z = wall + standoff_h + pcb_thick + comp_clearance  # ~25.6mm

    cx, cy = case_w / 2, case_h / 2
    pcb_ox = wall + PCB_TOL
    pcb_oy = wall + PCB_TOL

    tris = []

    outer = rect_profile(cx, cy, case_w, case_h)
    inner = rect_profile(cx, cy, case_w - wall*2, case_h - wall*2)

    # ── Main box (open top) ──
    # Bottom plate
    tris += fill_profile(outer, 0, flip=True)
    # Outer walls
    tris += extrude_profile(outer, 0, total_z)
    # Inner walls
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,total_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,total_z),(x2,y2,total_z)))
    # Bottom ring
    tris += ring_fill(outer, inner, wall, flip=False)
    # Top ring (open)
    tris += ring_fill(outer, inner, total_z, flip=False)

    # PCB standoffs (M4 mounting holes + 4 extra support posts)
    sb = wall + standoff_h
    # M4 mounting positions from CPL
    for mx, my in [(4, 4), (136, 4), (4, 116), (136, 116)]:
        tris += standoff(pcb_ox + mx, pcb_oy + my, wall, standoff_h,
                         outer_r=4.0, inner_r=2.1, segs=24)  # M4 = 2.1mm inner
    # Extra support posts at center edges
    for mx, my in [(70, 4), (70, 116), (4, 60), (136, 60)]:
        tris += standoff(pcb_ox + mx, pcb_oy + my, wall, standoff_h,
                         outer_r=2.5, inner_r=1.0, segs=16)

    # Connector z range (from bottom of connectors to top)
    conn_z_lo = wall + standoff_h + pcb_thick
    conn_z_hi = total_z

    # ── Front connectors (Y=0 side / PCB Y=0) ──
    # 4x TRS 6.35mm jacks at PCB (10, 35/52/69/86)
    for py in [35, 52, 69, 86]:
        tris = cutout_circle(tris, pcb_ox + 10, 0, conn_z_lo, conn_z_hi, 3.5)
        # Actually these are at different Y positions along the front...
        # Re-reading: front = low-Y edge, connectors at different X positions
    # Reset: front connectors spread along X axis at Y=0 (case bottom edge)
    # TRS jacks at X positions along front
    for px in [10, 30, 50, 70]:
        tris = cutout_circle(tris, pcb_ox + px, 0, conn_z_lo - 1, conn_z_hi, 3.5)

    # 2x XLR at front right
    for px in [95, 115]:
        tris = cutout_rect(tris, pcb_ox + px, 0, conn_z_lo - 1, conn_z_hi, 24.0, wall + 1.0)

    # Headphone jack at front far left
    tris = cutout_circle(tris, pcb_ox + 5, 0, conn_z_lo - 1, conn_z_hi, 3.5)

    # ── Rear connectors (Y=case_h side / PCB Y=120) ──
    # 2x Speakon at back
    for px in [35, 65]:
        tris = cutout_rect(tris, pcb_ox + px, case_h, conn_z_lo - 1, conn_z_hi, 24.0, wall + 1.0)

    # 2x Toslink
    for px in [90, 105]:
        tris = cutout_rect(tris, pcb_ox + px, case_h, conn_z_lo, conn_z_hi, 8.0, wall + 1.0)

    # HDMI
    tris = cutout_rect(tris, pcb_ox + 90, case_h, conn_z_lo, conn_z_hi, 16.0, wall + 1.0)

    # USB-C
    tris = cutout_rect(tris, pcb_ox + 70, case_h, conn_z_lo, conn_z_lo + 4.0, 9.5, wall + 1.0)

    # RJ45
    tris = cutout_rect(tris, pcb_ox + 50, case_h, conn_z_lo, conn_z_lo + 14.0, 16.5, wall + 1.0)

    # ── Right side: SMA antenna ──
    tris = cutout_circle(tris, case_w, pcb_oy + 15, conn_z_lo, conn_z_hi, 3.5)

    # ── Ventilation slots on all walls (6 slots per side, 2mm wide) ──
    vent_z_lo = total_z - 8.0
    vent_z_hi = total_z - 2.0
    # Front/back vents
    for i in range(6):
        vx = pcb_ox + 20 + i * 18
        tris = cutout_rect(tris, vx, 0, vent_z_lo, vent_z_hi, 2.0, wall + 1.0)
        tris = cutout_rect(tris, vx, case_h, vent_z_lo, vent_z_hi, 2.0, wall + 1.0)

    # ── Lid (separate piece with a visible gap above the box) ──
    lid_z = total_z + 2.5  # Offset above box — creates visible parting line
    lid_outer = rect_profile(cx, cy, case_w, case_h)
    tris += extrude_profile(lid_outer, lid_z, lid_z + lid_h)
    tris += fill_profile(lid_outer, lid_z, flip=True)
    tris += fill_profile(lid_outer, lid_z + lid_h, flip=False)

    # ── Big lid ventilation slots — very visible from above ──
    for i in range(6):
        sy = pcb_oy + 15 + i * 18
        tris = cutout_rect(tris, cx, sy, lid_z - 0.1, lid_z + lid_h + 0.1,
                           case_w * 0.72, 4.0)

    # Lid screw holes (M4, 4 corners)
    for mx, my in [(8, 8), (case_w - 8, 8), (8, case_h - 8), (case_w - 8, case_h - 8)]:
        tris = cutout_circle(tris, mx, my, lid_z - 0.1, lid_z + lid_h + 0.1, 2.1)

    # Rubber feet positions (4 corners, bottom) — recessed foot pockets
    for fx, fy in [(12, 12), (case_w - 12, 12), (12, case_h - 12), (case_w - 12, case_h - 12)]:
        tris = cutout_circle(tris, fx, fy, -0.1, wall + 0.1, 1.6)
        # Boss around foot hole
        tris += standoff(fx, fy, 0, wall, outer_r=4.0, inner_r=1.6, segs=16)
        # Recessed rubber-foot pocket (Ø10 shallow)
        tris = cutout_circle(tris, fx, fy, -0.1, 0.8, 5.0)

    # ── Thermal intake vents on bottom (20+ slots 1.5mm wide) ──
    for row in range(5):
        for col in range(5):
            vx = 25 + col * 22
            vy = 25 + row * 20
            tris = cutout_rect(tris, vx, vy, -0.1, wall + 0.1, 12.0, 1.5)

    # ── Exhaust vents on right side wall (15+ vertical slots) ──
    for i in range(15):
        vy = 15 + i * 7
        if vy < case_h - 10:
            tris = cutout_rect(tris, case_w, vy,
                               total_z - 12.0, total_z - 4.0,
                               wall + 1.0, 1.5)

    # ── GPIO ribbon cable pass-through (20x3mm slot on side) ──
    tris = cutout_rect(tris, 0, cy, wall + standoff_h + pcb_thick + 2.0,
                       wall + standoff_h + pcb_thick + 5.0, wall + 1.0, 22.0)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 4: Seed Wristband Pod — Oval pod for 28mm round PCB
# ════════════════════════════════════════════════════════════════════
# Fits the 28mm COIN Lite PCB inside an ergonomic oval pod.
# Designed to thread through a silicone wristband via side slot channels.
# Bottom opening for battery/PCB insertion, snap-fit closure.
# Speaker grille on top, USB-C cutout on side.

def generate_seed_wristband_pod():
    """
    Band — "The Lens"
    A biconvex lens. Thin at edges, thick at center.
    Plan: superellipse 28mm x 20mm (golden ratio: 28/20 ~ phi/1.15).
    Cross-section: biconvex lens (both top AND bottom are convex arcs).
    Max thickness at center: 6mm. Edge thickness: 2mm (tapers smoothly).
    Band slots follow the ellipse curvature. Fibonacci spiral speaker.
    No visible seam.
    """
    pod_a = 14.0            # semi-major (28mm total)
    pod_b = 10.0            # semi-minor (20mm total)
    center_thick = 6.0      # Maximum thickness at center
    edge_thick = 2.0        # Minimum at edges
    wall = 0.8
    pcb_thick = 1.0

    segs = 192
    tris = []

    cx, cy = 0, 0

    # Superellipse plan — between ellipse and rounded rect
    outer = superellipse_profile(cx, cy, pod_a, pod_b, n=2.8, segs=segs)
    inner = superellipse_profile(cx, cy, pod_a - wall, pod_b - wall, n=2.8, segs=segs)

    # Find max radius for lenticular calculations
    max_r = max(math.sqrt(p[0] ** 2 + p[1] ** 2) for p in outer)

    # The lens is centered at z=center_thick/2 = 3.0
    z_mid = center_thick / 2
    top_rise = (center_thick - edge_thick) / 2   # 2mm convex rise on top
    bot_rise = (center_thick - edge_thick) / 2   # 2mm convex rise on bottom

    # ── Top convex surface (lenticular dome) ──
    tris += make_dome_lenticular(outer, z_mid + edge_thick / 2, top_rise, rings=32)

    # ── Bottom convex surface (inverted lenticular dome) ──
    # Build bottom dome going downward
    bot_base = z_mid - edge_thick / 2
    dome_rings = 32
    prev_ring = outer
    prev_z = bot_base
    for ri in range(1, dome_rings + 1):
        t = ri / dome_rings
        shrink = t * 0.95
        curr_ring = [(cx + (px - cx) * (1 - shrink), cy + (py - cy) * (1 - shrink))
                     for px, py in outer]
        curr_r = max_r * (1 - shrink)
        ring_z = bot_base - lenticular_z(curr_r, max_r, bot_rise)

        nr = len(prev_ring)
        nc = len(curr_ring)
        for i in range(max(nr, nc)):
            pi_i = i % nr; pj_i = (i + 1) % nr
            ci_i = i % nc; cj_i = (i + 1) % nc
            px1, py1 = prev_ring[pi_i]; px2, py2 = prev_ring[pj_i]
            cx1, cy1 = curr_ring[ci_i]; cx2, cy2 = curr_ring[cj_i]
            tris.append(make_tri(
                (px1, py1, prev_z), (cx2, cy2, ring_z), (cx1, cy1, ring_z)))
            tris.append(make_tri(
                (px1, py1, prev_z), (px2, py2, prev_z), (cx2, cy2, ring_z)))
        prev_ring = curr_ring
        prev_z = ring_z
    tris += fill_profile(prev_ring, prev_z, flip=True)

    # ── Thin edge wall connecting top and bottom surfaces ──
    tris += extrude_profile(outer, bot_base, z_mid + edge_thick / 2)

    # ── Inner cavity ──
    split_z = z_mid
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1, y1, wall + 0.5), (x2, y2, center_thick - wall - 0.5),
                             (x2, y2, wall + 0.5)))
        tris.append(make_tri((x1, y1, wall + 0.5), (x1, y1, center_thick - wall - 0.5),
                             (x2, y2, center_thick - wall - 0.5)))
    tris += ring_fill(outer, inner, wall + 0.5, flip=False)
    tris += ring_fill(outer, inner, center_thick - wall - 0.5, flip=True)
    tris += fill_profile(inner, wall + 0.5, flip=True)
    tris += fill_profile(inner, center_thick - wall - 0.5, flip=False)

    # ── Speaker: Fibonacci spiral at center of top ──
    top_z_max = z_mid + edge_thick / 2 + top_rise
    tris = apply_fibonacci_speaker(tris, 0.0, 0.0,
                                   center_thick - wall - 0.6, top_z_max + 0.1,
                                   grid_r=3.0, hole_r=0.3, n_holes=8)

    # USB-C cutout at the long edge
    usb_z = z_mid
    tris = cutout_rect(tris, pod_a, 0, usb_z - 1.5, usb_z + 1.5, wall + 0.5, 9.5)

    # ── Band channels: 2 thin slots that follow the ellipse curvature ──
    slot_w = 2.0
    slot_z_lo = z_mid - 1.5
    slot_z_hi = z_mid + 1.5
    # Left and right ends (along major axis)
    tris = cutout_rect(tris, -pod_a, 0, slot_z_lo, slot_z_hi, wall + 1.0, slot_w)
    tris = cutout_rect(tris, pod_a, 0, slot_z_lo, slot_z_hi, wall + 1.0, slot_w)

    # ── Retention ribs on underside (clip to wristband base) ──
    # 2 raised ribs on the bottom surface perpendicular to major axis
    for rib_x in [-4.0, 4.0]:
        rib_profile = rect_profile(rib_x, 0, 1.0, pod_b * 1.4)
        tris += extrude_profile(rib_profile, -0.6, 0.0)
        tris += fill_profile(rib_profile, -0.6, flip=True)

    # Mic pinhole on top dome
    tris = cutout_circle(tris, 0.0, pod_b * 0.5,
                         center_thick - wall - 0.1, z_mid + edge_thick / 2 + top_rise + 0.1, 0.35)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 5: Seed Keychain — AirTag-style disc for keys/pocket
# ════════════════════════════════════════════════════════════════════
# Same 28mm Seed PCB inside a smooth circular disc with keyring hole.
# Compact, pocketable form factor inspired by Apple AirTag.

def generate_seed_keychain():
    """
    Tag — "The Drop"
    A water droplet shape. Teardrop plan view with the body itself
    curving into a keyring loop at the narrow end. No separate bridge.
    26mm long, 20mm wide. Height: 6mm. Catenary dome top.
    Fibonacci spiral speaker. Single smooth form.
    """
    tag_length = 26.0
    tag_width = 20.0
    total_h = 6.0
    wall = 0.8
    dome_h = 0.8            # Catenary dome rise
    pcb_thick = 1.0

    segs = 192
    tris = []

    split_z = total_h / 2
    cx, cy = 0, 0

    # Teardrop plan — wider at bottom, narrows to keyring loop at top
    outer = teardrop_profile(cx, cy, tag_length, tag_width, segs)
    inner = teardrop_profile(cx, cy, tag_length - wall * 2, tag_width - wall * 2, segs)

    # ── Bottom half — subtle convex (lenticular) ──
    # Inverted lenticular bottom face
    dome_rings_b = 24
    prev_ring = outer
    prev_z = 0
    pcx = sum(p[0] for p in outer) / len(outer)
    pcy = sum(p[1] for p in outer) / len(outer)
    max_r_b = max(math.sqrt((p[0] - pcx) ** 2 + (p[1] - pcy) ** 2) for p in outer)
    for ri in range(1, dome_rings_b + 1):
        t = ri / dome_rings_b
        shrink = t * 0.8
        curr_ring = [(pcx + (px - pcx) * (1 - shrink), pcy + (py - pcy) * (1 - shrink))
                     for px, py in outer]
        ring_z = -0.3 * math.sin(math.pi * t / 2)
        nr = len(prev_ring)
        nc = len(curr_ring)
        for i in range(max(nr, nc)):
            pi_i = i % nr; pj_i = (i + 1) % nr
            ci_i = i % nc; cj_i = (i + 1) % nc
            tris.append(make_tri(
                (*prev_ring[pi_i], prev_z), (*curr_ring[cj_i], ring_z), (*curr_ring[ci_i], ring_z)))
            tris.append(make_tri(
                (*prev_ring[pi_i], prev_z), (*prev_ring[pj_i], prev_z), (*curr_ring[cj_i], ring_z)))
        prev_ring = curr_ring
        prev_z = ring_z
    tris += fill_profile(prev_ring, prev_z, flip=True)

    # Outer wall
    tris += extrude_profile(outer, 0, split_z)
    # Inner wall
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1, y1, wall), (x2, y2, split_z), (x2, y2, wall)))
        tris.append(make_tri((x1, y1, wall), (x1, y1, split_z), (x2, y2, split_z)))
    tris += ring_fill(outer, inner, wall, flip=False)
    tris += ring_fill(outer, inner, split_z, flip=False)

    # USB-C cutout at the wider bottom end
    usb_z = total_h / 2
    tris = cutout_rect(tris, 0.0, -(tag_length * 0.4), usb_z - 1.5, usb_z + 1.5, 9.5, wall + 0.5)

    # ── Top half with catenary dome ──
    top_z = split_z + 0.2
    tris += extrude_profile(outer, top_z, total_h)

    # Inner top
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1, y1, top_z), (x2, y2, total_h - wall), (x2, y2, top_z)))
        tris.append(make_tri((x1, y1, top_z), (x1, y1, total_h - wall), (x2, y2, total_h - wall)))
    tris += ring_fill(outer, inner, top_z, flip=True)
    tris += ring_fill(outer, inner, total_h - wall, flip=True)
    tris += fill_profile(inner, total_h - wall, flip=True)

    # Catenary dome on top
    tris += make_dome_catenary(outer, total_h, dome_h, rings=32, segs=segs)

    # Speaker: Fibonacci spiral on the wider face
    tris = apply_fibonacci_speaker(tris, 0.0, -2.0, total_h - wall - 0.1,
                                   total_h + dome_h + 0.1, grid_r=3.5, hole_r=0.3, n_holes=13)

    # Mic pinhole at top of dome (integrated into narrow end area)
    tris = cutout_circle(tris, 0.0, tag_length * 0.15,
                         total_h - wall - 0.1, total_h + dome_h + 0.1, 0.4)

    # ── Keyring loop: the narrow end curves into a smooth torus ring ──
    # The body itself forms the ring — no separate bridge piece
    loop_cy = tag_length * 0.45  # at the narrow top
    loop_r_major = 3.0       # Ring opening radius
    loop_r_minor = 1.0       # Tube thickness
    loop_segs = 64
    tube_segs = 24

    for i in range(loop_segs):
        a1 = 2 * math.pi * i / loop_segs
        a2 = 2 * math.pi * (i + 1) / loop_segs

        for j in range(tube_segs):
            t1 = 2 * math.pi * j / tube_segs
            t2 = 2 * math.pi * (j + 1) / tube_segs

            # Torus parametric equations (lying in XY plane at z=total_h/2)
            p1 = ((loop_r_major + loop_r_minor * math.cos(t1)) * math.cos(a1),
                   loop_cy + (loop_r_major + loop_r_minor * math.cos(t1)) * math.sin(a1),
                   total_h / 2 + loop_r_minor * math.sin(t1))
            p2 = ((loop_r_major + loop_r_minor * math.cos(t2)) * math.cos(a1),
                   loop_cy + (loop_r_major + loop_r_minor * math.cos(t2)) * math.sin(a1),
                   total_h / 2 + loop_r_minor * math.sin(t2))
            p3 = ((loop_r_major + loop_r_minor * math.cos(t1)) * math.cos(a2),
                   loop_cy + (loop_r_major + loop_r_minor * math.cos(t1)) * math.sin(a2),
                   total_h / 2 + loop_r_minor * math.sin(t1))
            p4 = ((loop_r_major + loop_r_minor * math.cos(t2)) * math.cos(a2),
                   loop_cy + (loop_r_major + loop_r_minor * math.cos(t2)) * math.sin(a2),
                   total_h / 2 + loop_r_minor * math.sin(t2))

            tris.append(make_tri(p1, p3, p2))
            tris.append(make_tri(p2, p3, p4))

    # Snap-fit lip
    lip = teardrop_profile(cx, cy, tag_length - wall * 2 + SNAP_TOL * 2,
                           tag_width - wall * 2 + SNAP_TOL * 2, segs)
    tris += extrude_profile(lip, split_z - 0.4, split_z)
    tris += fill_profile(lip, split_z, flip=False)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 6: Seed Clip — Backpack/belt clip-on
# ════════════════════════════════════════════════════════════════════
# Oval body with integrated spring clip on back.

def generate_seed_clip():
    """
    Seed Clip: oval body (35x25x12mm) with integrated carabiner-style
    clip on back for belt loops, backpack straps, pocket edges.
    Speaker grille on front, USB-C at bottom.
    """
    body_w = 35.0
    body_h = 25.0
    body_z = 12.0
    wall = 1.5
    corner_r = 10.0
    pcb_thick = 1.6
    standoff_h = 0.8

    segs = 24
    tris = []

    cx, cy = body_w / 2, body_h / 2
    split_z = body_z / 2

    outer = rounded_rect_profile(cx, cy, body_w, body_h, corner_r, segs)
    inner = rounded_rect_profile(cx, cy, body_w - wall*2, body_h - wall*2,
                                  max(corner_r - wall, 2.0), segs)

    # ── Bottom half ──
    tris += extrude_profile(outer, 0, split_z)
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    tris += fill_profile(outer, 0, flip=True)
    tris += ring_fill(outer, inner, wall, flip=False)
    tris += ring_fill(outer, inner, split_z, flip=False)

    # PCB standoffs (3 posts)
    for angle_deg in [0, 120, 240]:
        a = math.radians(angle_deg)
        sx = cx + 9.0 * math.cos(a)
        sy = cy + 9.0 * math.sin(a)
        tris += standoff(sx, sy, wall, standoff_h, outer_r=1.2, inner_r=0.5, segs=12)

    # USB-C cutout at bottom (Y=0)
    usb_z = wall + standoff_h + pcb_thick / 2
    tris = cutout_rect(tris, cx, 0, usb_z - 1.75, usb_z + 1.75, 9.5, wall + 1.0)

    # ── Top half ──
    top_z = split_z + 0.3
    tris += extrude_profile(outer, top_z, body_z)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,body_z - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,body_z - wall),(x2,y2,body_z - wall)))
    tris += fill_profile(outer, body_z, flip=False)
    tris += ring_fill(outer, inner, top_z, flip=True)
    tris += ring_fill(outer, inner, body_z - wall, flip=True)
    tris += fill_profile(inner, body_z - wall, flip=True)

    # Speaker grille on front (top face)
    for gx in range(-1, 2):
        for gy in range(-1, 2):
            tris = cutout_circle(tris, cx + gx * 2.8, cy + gy * 2.8,
                                 body_z - wall - 0.1, body_z + 0.1, 0.6)

    # LED window
    tris = cutout_circle(tris, cx, cy + 6.0, body_z - wall - 0.1, body_z + 0.1, 1.0)

    # ── Clip on back (bottom face, extending beyond body) ──
    # The clip is a curved hook: extends from top of bottom face, curves down
    # Modeled as a flat arm with a hook at the end
    clip_w = 8.0      # Clip width
    clip_len = 20.0   # Total clip length (extends beyond body)
    clip_thick = 1.5   # Clip arm thickness
    hook_h = 4.0       # Hook opening height

    # Clip arm: rectangle extruded on bottom surface
    clip_x = cx
    clip_y_start = body_h  # Start at top edge of body
    clip_y_end = body_h + clip_len

    # Main arm (extends from body top edge outward)
    arm_profile = rect_profile(clip_x, (clip_y_start + clip_y_end) / 2,
                               clip_w, clip_len)
    tris += extrude_profile(arm_profile, 0, clip_thick)
    tris += fill_profile(arm_profile, 0, flip=True)
    tris += fill_profile(arm_profile, clip_thick, flip=False)

    # Hook return (curves back): short piece at the end going back toward body
    hook_profile = rect_profile(clip_x, clip_y_end - 2.0, clip_w, 4.0)
    tris += extrude_profile(hook_profile, clip_thick, clip_thick + hook_h)
    tris += fill_profile(hook_profile, clip_thick + hook_h, flip=False)

    # Hook tip (catches onto fabric/strap)
    tip_profile = rect_profile(clip_x, clip_y_end - 5.0, clip_w, 6.0)
    tris += extrude_profile(tip_profile, clip_thick + hook_h, clip_thick + hook_h + clip_thick)
    tris += fill_profile(tip_profile, clip_thick + hook_h + clip_thick, flip=False)

    # ── Hinge cylinder (Ø3mm through) at body/arm junction ──
    hinge_cx = clip_x
    hinge_cy = body_h
    hinge_profile = circle_profile(hinge_cx, hinge_cy, 2.0, 24)
    tris += extrude_profile(hinge_profile, 0, clip_thick + 0.5)
    tris += fill_profile(hinge_profile, 0, flip=True)
    tris += fill_profile(hinge_profile, clip_thick + 0.5, flip=False)
    # Through-hole for pin
    tris = cutout_circle(tris, hinge_cx, hinge_cy, -0.1, clip_thick + 0.6, 0.75)

    # ── Torsion spring recess next to hinge ──
    tris = cutout_rect(tris, hinge_cx, hinge_cy + 2.0,
                       0.2, clip_thick - 0.2, clip_w * 0.5, 2.0)

    # Snap-fit lip
    lip = rounded_rect_profile(cx, cy, body_w - wall*2 + SNAP_TOL*2,
                                body_h - wall*2 + SNAP_TOL*2,
                                max(corner_r - wall, 2.0), segs)
    tris += extrude_profile(lip, split_z - 0.8, split_z)
    tris += fill_profile(lip, split_z, flip=False)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 7: Seed Badge — Event badge / name tag style
# ════════════════════════════════════════════════════════════════════
# Rectangular badge with name card window, lanyard hole, pin clip.

def generate_seed_badge():
    """
    Seed Badge: rectangular (55x35x8mm) event badge with name card
    slot on front, lanyard hole at top, pin clip on back.
    PCB mounted inside with speaker facing outward.
    """
    badge_w = 55.0
    badge_h = 35.0
    badge_z = 8.0
    wall = 1.2
    corner_r = 3.0
    pcb_thick = 1.6
    standoff_h = 0.5

    segs = 24
    tris = []

    cx, cy = badge_w / 2, badge_h / 2
    split_z = badge_z / 2

    outer = rounded_rect_profile(cx, cy, badge_w, badge_h, corner_r, segs)
    inner = rounded_rect_profile(cx, cy, badge_w - wall*2, badge_h - wall*2,
                                  max(corner_r - wall, 1.0), segs)

    # ── Back half (0 to split_z) — this faces the chest ──
    tris += extrude_profile(outer, 0, split_z)
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    tris += fill_profile(outer, 0, flip=True)
    tris += ring_fill(outer, inner, wall, flip=False)
    tris += ring_fill(outer, inner, split_z, flip=False)

    # PCB standoffs (4 corners around the 28mm PCB, centered in badge)
    for dx, dy in [(-8, -8), (8, -8), (-8, 8), (8, 8)]:
        tris += standoff(cx + dx, cy + dy, wall, standoff_h,
                         outer_r=1.0, inner_r=0.4, segs=12)

    # USB-C cutout at bottom edge (Y=0)
    usb_z = wall + standoff_h + pcb_thick / 2
    tris = cutout_rect(tris, cx, 0, usb_z - 1.75, usb_z + 1.75, 9.5, wall + 1.0)

    # ── Front half (split_z to badge_z) — visible face ──
    top_z = split_z + 0.3
    tris += extrude_profile(outer, top_z, badge_z)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,badge_z - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,badge_z - wall),(x2,y2,badge_z - wall)))
    tris += fill_profile(outer, badge_z, flip=False)
    tris += ring_fill(outer, inner, top_z, flip=True)
    tris += ring_fill(outer, inner, badge_z - wall, flip=True)
    tris += fill_profile(inner, badge_z - wall, flip=True)

    # Name card window: clear area on front face (40x18mm recessed 0.5mm)
    window_w = 40.0
    window_h = 14.0
    # Window is a recessed pocket on the front face (top of badge_z)
    tris = cutout_rect(tris, cx, cy + 4.0,
                       badge_z - 0.5, badge_z + 0.1, window_w, window_h)

    # Speaker grille: small holes below the name card window
    for gx in range(-2, 3):
        tris = cutout_circle(tris, cx + gx * 2.5, cy - 10.0,
                             badge_z - wall - 0.1, badge_z + 0.1, 0.6)

    # LED window on front
    tris = cutout_circle(tris, cx + 18.0, cy - 10.0,
                         badge_z - wall - 0.1, badge_z + 0.1, 1.0)

    # Lanyard hole at top center (3mm diameter through full height)
    tris = cutout_circle(tris, cx, badge_h - 2.0, -0.1, badge_z + 0.1, 1.5)

    # Pin clip on back: small rectangular boss with slot
    pin_w = 20.0
    pin_h = 3.0
    pin_z = 1.5
    pin_profile = rect_profile(cx, cy, pin_w, pin_h)
    tris += extrude_profile(pin_profile, -pin_z, 0)
    tris += fill_profile(pin_profile, -pin_z, flip=True)

    # Pin catch at one end
    catch_profile = rect_profile(cx + pin_w/2 - 1.5, cy, 3.0, pin_h)
    tris += extrude_profile(catch_profile, -pin_z - 1.5, -pin_z)
    tris += fill_profile(catch_profile, -pin_z - 1.5, flip=True)

    # ── Safety-pin bar channel on back (1.5mm deep groove 30mm long) ──
    tris = cutout_rect(tris, cx - 5.0, cy, -0.1, 1.5, 30.0, 1.5)

    # ── Magnetic pocket alternative (Ø12mm × 2mm recess on back) ──
    tris = cutout_circle(tris, cx + 15.0, cy, -0.1, 2.0, 6.0)

    # Snap-fit lip
    lip = rounded_rect_profile(cx, cy, badge_w - wall*2 + SNAP_TOL*2,
                                badge_h - wall*2 + SNAP_TOL*2,
                                max(corner_r - wall, 1.0), segs)
    tris += extrude_profile(lip, split_z - 0.6, split_z)
    tris += fill_profile(lip, split_z, flip=False)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 8: Seed Pendant — Teardrop/pebble necklace
# ════════════════════════════════════════════════════════════════════
# Organic pebble shape worn as jewelry on a cord.

def generate_seed_pendant():
    """
    Seed Pendant: teardrop/pebble shape (35mm tall, 28mm wide, 10mm thick)
    with cord hole at top for leather/fabric cord. Speaker on back,
    LED visible through translucent top area. Smooth river-stone finish.
    """
    # We approximate the teardrop with an elongated oval (egg shape)
    pebble_w = 28.0   # Width at widest point
    pebble_h = 35.0   # Height (tall axis)
    pebble_z = 10.0   # Thickness
    wall = 1.2
    cord_hole_r = 1.5  # 3mm cord hole

    segs = 96
    tris = []

    cx = pebble_w / 2
    cy = pebble_h / 2

    # Generate egg/teardrop profile using variable radius
    # Wider at bottom, narrower at top (teardrop)
    def teardrop_profile(center_x, center_y, segs=48):
        pts = []
        for i in range(segs):
            angle = 2 * math.pi * i / segs
            # Egg shape: radius varies with angle
            # Wider at bottom (angle=3pi/2), narrower at top (angle=pi/2)
            base_r = pebble_w / 2
            # Vertical stretch
            ry = pebble_h / 2
            rx = base_r
            # Teardrop: reduce radius at top
            factor = 1.0 - 0.2 * max(0, math.sin(angle))
            x = center_x + rx * math.cos(angle) * factor
            y = center_y + ry * math.sin(angle)
            pts.append((x, y))
        return pts

    outer = teardrop_profile(cx, cy, segs)

    # Inner profile: offset inward by wall thickness
    inner = []
    n = len(outer)
    for i in range(n):
        px, py = outer[i]
        # Direction from center
        dx = px - cx
        dy = py - cy
        dist = math.sqrt(dx*dx + dy*dy)
        if dist < 0.1:
            inner.append((px, py))
            continue
        # Offset inward
        inner.append((px - wall * dx/dist, py - wall * dy/dist))

    split_z = pebble_z / 2

    # ── Bottom half ──
    tris += extrude_profile(outer, 0, split_z)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    tris += fill_profile(outer, 0, flip=True)
    tris += ring_fill(outer, inner, wall, flip=False)
    tris += ring_fill(outer, inner, split_z, flip=False)

    # PCB standoffs (3 posts)
    for angle_deg in [0, 120, 240]:
        a = math.radians(angle_deg)
        sx = cx + 9.0 * math.cos(a)
        sy = cy + 9.0 * math.sin(a)
        tris += standoff(sx, sy, wall, 0.8, outer_r=1.0, inner_r=0.4, segs=12)

    # USB-C cutout at bottom (Y=0)
    usb_z = wall + 0.8 + 1.6 / 2
    tris = cutout_rect(tris, cx, 0, usb_z - 1.75, usb_z + 1.75, 9.5, wall + 1.0)

    # ── Top half ──
    top_z = split_z + 0.3
    tris += extrude_profile(outer, top_z, pebble_z)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,pebble_z - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,pebble_z - wall),(x2,y2,pebble_z - wall)))
    tris += fill_profile(outer, pebble_z, flip=False)
    tris += ring_fill(outer, inner, top_z, flip=True)
    tris += ring_fill(outer, inner, pebble_z - wall, flip=True)
    tris += fill_profile(inner, pebble_z - wall, flip=True)

    # Speaker on back (bottom face) — bone-conduction style
    for gx in range(-1, 2):
        for gy in range(-1, 2):
            tris = cutout_circle(tris, cx + gx * 2.5, cy + gy * 2.5,
                                 -0.1, wall + 0.1, 0.5)

    # LED window at top of front face (translucent area)
    tris = cutout_circle(tris, cx, cy + 10.0,
                         pebble_z - wall - 0.1, pebble_z + 0.1, 1.5)

    # ── Lanyard bail tab at top — 6mm wide tab with Ø3mm hole ──
    bail_cy = pebble_h + 2.5
    bail_profile = rect_profile(cx, bail_cy, 6.0, 5.0)
    bail_z0 = pebble_z / 2 - 2.0
    bail_z1 = pebble_z / 2 + 2.0
    tris += extrude_profile(bail_profile, bail_z0, bail_z1)
    tris += fill_profile(bail_profile, bail_z0, flip=True)
    tris += fill_profile(bail_profile, bail_z1, flip=False)
    # Ø3mm hole through bail
    tris = cutout_circle(tris, cx, bail_cy, bail_z0 - 0.1, bail_z1 + 0.1, 1.5)

    # Mic pinhole on front
    tris = cutout_circle(tris, cx, cy - 5.0,
                         pebble_z - wall - 0.1, pebble_z + 0.1, 0.4)

    # Snap-fit lip
    lip = teardrop_profile(cx, cy, segs)
    # Offset lip to inner + snap tolerance
    lip_pts = []
    for i in range(len(lip)):
        px, py = inner[i]
        dx = px - cx
        dy = py - cy
        dist = math.sqrt(dx*dx + dy*dy)
        if dist < 0.1:
            lip_pts.append((px, py))
            continue
        lip_pts.append((px + SNAP_TOL * dx/dist, py + SNAP_TOL * dy/dist))
    tris += extrude_profile(lip_pts, split_z - 0.8, split_z)
    tris += fill_profile(lip_pts, split_z, flip=False)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 9: Seed Sticker — Ultra-thin stick-on disc
# ════════════════════════════════════════════════════════════════════
# Super flat disc designed for 3M adhesive mounting.

def generate_seed_sticker():
    """
    Seed Sticker: flat 30×30×2.5mm rounded square.
    3M tape recess on bottom, LED ring on top, mic grille center.
    Actually thin enough to stick on laptop/phone/helmet.
    """
    sticker_w = 30.0
    sticker_h = 30.0
    total_h = 3.5      # Slightly thicker so features don't cut all the way through
    wall = 0.5
    corner_r = 4.0
    pcb_thick = 1.0

    segs = 24
    tris = []

    cx, cy = 0, 0
    outer = rounded_rect_profile(cx, cy, sticker_w, sticker_h, corner_r, segs)
    inner = rounded_rect_profile(cx, cy, sticker_w - wall*2, sticker_h - wall*2,
                                  max(corner_r - wall, 1.0), segs)

    # Solid body
    tris += extrude_profile(outer, 0, total_h)
    tris += fill_profile(outer, 0, flip=True)
    tris += fill_profile(outer, total_h, flip=False)

    # 3M tape recess notionally goes on the bottom. Since cutout_rect
    # would erase the entire bottom plate, we instead add a small
    # perimeter lip at the bottom that gives a visible recess look.
    lip_outer = rounded_rect_profile(cx, cy, sticker_w - 0.5, sticker_h - 0.5,
                                      max(corner_r - 0.25, 1.0), segs)
    tris += extrude_profile(lip_outer, 0.3, 0.5)

    # ── LED ring recess on top (Ø24mm × 0.4mm deep) ──
    # Use a thin outer ring groove + raised inner disc
    tris = cutout_circle(tris, cx, cy, total_h - 0.4, total_h + 0.1, 12.0)
    # Inner solid (so the center stays raised at full height, forming a ring)
    led_inner = circle_profile(cx, cy, 10.5, 32)
    tris += extrude_profile(led_inner, total_h - 0.4, total_h)
    tris += fill_profile(led_inner, total_h, flip=False)

    # ── Mic grille pattern at center (fibonacci) ──
    tris = apply_fibonacci_speaker(tris, cx, cy,
                                   total_h - wall - 0.1, total_h + 0.1,
                                   grid_r=3.0, hole_r=0.3, n_holes=9)

    # USB-C pocket on one edge
    tris = cutout_rect(tris, cx, sticker_h / 2,
                       total_h / 2 - 1.0, total_h / 2 + 1.0, 9.5, wall + 1.0)

    # Status LED pinhole
    tris = cutout_circle(tris, cx + 10.0, cy + 10.0,
                         total_h - wall - 0.1, total_h + 0.1, 0.4)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 10: Seed Pick — Guitar pick shape for lead/acoustic guitar
# ════════════════════════════════════════════════════════════════════
# Classic guitar pick triangle: 30mm tall, 26mm wide at base, 8mm thick.
# Rounded corners, pointed tip at bottom, USB-C at top, speaker on flat face.
# LED near tip glows during playback. Ergonomic grip ridges on sides.

def generate_seed_pick():
    """
    Pick — "The Plectrum"
    Reuleaux triangle base — constant-width curve, 24mm.
    Height: 4.5mm (tapers from 4.5mm at grip to 2mm at tip).
    Grip area: subtle concave dimples (Voronoi-inspired).
    Tip: smooth continuous curve. Speaker: 3 Fibonacci holes near wide end.
    The geometry of a jazz pick, rendered in mathematical curves.
    """
    pick_width = 24.0       # Constant width (Reuleaux property)
    thick_grip = 4.5        # Thickness at grip (wide end)
    thick_tip = 1.5         # Thickness at tip (pointy end) — thinner for more visible taper
    wall = 0.8
    pcb_thick = 1.0

    segs = 192
    tris = []

    # Reuleaux triangle plan — constant-width curve
    outer = reuleaux_triangle_profile(0, 0, pick_width, segs)
    inner = reuleaux_triangle_profile(0, 0, pick_width - wall * 2, segs)

    # Find centroid and bounds
    pcx = sum(p[0] for p in outer) / len(outer)
    pcy = sum(p[1] for p in outer) / len(outer)
    min_y = min(p[1] for p in outer)
    max_y = max(p[1] for p in outer)
    y_range = max_y - min_y

    split_z = thick_grip / 2

    # ── Back (bottom) surface — with taper from grip to tip ──
    # Tip is at max_y (top of Reuleaux = pointy vertex)
    # Grip is at min_y (wide base)
    tris_bottom = []
    n_out = len(outer)
    for i in range(n_out):
        j = (i + 1) % n_out
        x1, y1 = outer[i]; x2, y2 = outer[j]
        # Taper: z=0 at grip end (min_y), z rises toward tip
        taper1 = (y1 - min_y) / y_range if y_range > 0 else 0
        taper2 = (y2 - min_y) / y_range if y_range > 0 else 0
        z1 = (thick_grip - thick_tip) / 2 * taper1
        z2 = (thick_grip - thick_tip) / 2 * taper2
        # Connect to center at z=0 for the bottom face
        tris.append(make_tri((pcx, pcy, 0), (x2, y2, z2), (x1, y1, z1)))

    # Outer wall with taper
    for i in range(n_out):
        j = (i + 1) % n_out
        x1, y1 = outer[i]; x2, y2 = outer[j]
        taper1 = (y1 - min_y) / y_range if y_range > 0 else 0
        taper2 = (y2 - min_y) / y_range if y_range > 0 else 0
        z_bot1 = (thick_grip - thick_tip) / 2 * taper1
        z_bot2 = (thick_grip - thick_tip) / 2 * taper2
        z_top1 = thick_grip - z_bot1
        z_top2 = thick_grip - z_bot2
        tris.append(make_tri((x1, y1, z_bot1), (x2, y2, z_bot2), (x2, y2, z_top2)))
        tris.append(make_tri((x1, y1, z_bot1), (x2, y2, z_top2), (x1, y1, z_top1)))

    # Top surface with taper (symmetric to bottom)
    for i in range(n_out):
        j = (i + 1) % n_out
        x1, y1 = outer[i]; x2, y2 = outer[j]
        taper1 = (y1 - min_y) / y_range if y_range > 0 else 0
        taper2 = (y2 - min_y) / y_range if y_range > 0 else 0
        z1 = thick_grip - (thick_grip - thick_tip) / 2 * taper1
        z2 = thick_grip - (thick_grip - thick_tip) / 2 * taper2
        tris.append(make_tri((pcx, pcy, thick_grip), (x1, y1, z1), (x2, y2, z2)))

    # Inner wall
    n_in = len(inner)
    for i in range(n_in):
        j = (i + 1) % n_in
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1, y1, wall), (x2, y2, thick_grip - wall),
                             (x2, y2, wall)))
        tris.append(make_tri((x1, y1, wall), (x1, y1, thick_grip - wall),
                             (x2, y2, thick_grip - wall)))
    tris += ring_fill(outer, inner, wall, flip=False)
    tris += ring_fill(outer, inner, thick_grip - wall, flip=True)
    tris += fill_profile(inner, wall, flip=True)
    tris += fill_profile(inner, thick_grip - wall, flip=False)

    # USB-C cutout at the wide end (grip area, min_y)
    usb_z = thick_grip / 2
    tris = cutout_rect(tris, 0.0, min_y, usb_z - 1.5, usb_z + 1.5, 9.5, wall + 0.5)

    # Speaker: 3 Fibonacci-spiral holes near the wide end
    speaker_cy = pcy - 2.0  # Toward grip
    tris = apply_fibonacci_speaker(tris, 0.0, speaker_cy,
                                   thick_grip - wall - 0.1, thick_grip + 0.1,
                                   grid_r=2.5, hole_r=0.3, n_holes=5)

    # ── Big concave thumb dimple on one face (front) ──
    # Deep cutout for thumb grip feel
    thumb_dimple_r = 4.0
    tris = cutout_circle(tris, 0.0, pcy - 3.0, thick_grip - 0.9, thick_grip + 0.1, thumb_dimple_r)
    # Small secondary dimples (texture)
    for dx, dy in [(-3.0, pcy - 6.0), (3.0, pcy - 6.0)]:
        tris = cutout_circle(tris, dx, dy, thick_grip - 0.6, thick_grip + 0.1, 1.2)

    # ── Back face speaker grille (opposite side of dimple) ──
    tris = apply_speaker_grille(tris, 0.0, pcy - 3.0,
                                -0.1, 0.6, grid_r=2.8, hole_r=0.3, spacing=1.2)

    # ── Lanyard pinhole in one corner (near wide base corner) ──
    # Find the bottom corner of the Reuleaux (around (pick_width/2, min_y))
    lanyard_x = pick_width * 0.35
    lanyard_y = min_y + 2.5
    tris = cutout_circle(tris, lanyard_x, lanyard_y, -0.1, thick_grip + 0.1, 0.8)

    # Snap-fit lip
    lip = reuleaux_triangle_profile(0, 0, pick_width - wall * 2 + SNAP_TOL * 2, segs)
    tris += extrude_profile(lip, split_z - 0.4, split_z)
    tris += fill_profile(lip, split_z, flip=False)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 11: Seed Drum Key — T-shaped drum tuning key form factor
# ════════════════════════════════════════════════════════════════════
# T-shape: 35mm handle, 20mm head. PCB in handle (vertical).
# Speaker at top of handle. Clips to drum rim or cymbal stand.
# USB-C at bottom. Built to survive a drum kit environment.

def generate_seed_drumkey():
    """
    Seed Drum Key: dramatic T silhouette — long fluted handle with a
    wide round "key head" at the top, dominated by a deep square socket.
    """
    handle_l = 38.0    # Handle length (Y axis)
    handle_w = 11.0    # Handle width (X axis) — narrower, so the T is bolder
    head_w = 28.0      # Key head diameter (round, wider than handle)
    head_h = 14.0      # Head depth
    thick = 11.0       # Thickness (Z axis)
    wall = 1.8
    pcb_thick = 1.6
    standoff_h = 0.8
    corner_r = 3.0

    segs = 24
    tris = []

    split_z = thick / 2

    # ── Handle body ──
    hcx, hcy = 0, handle_l / 2
    h_outer = rounded_rect_profile(hcx, hcy, handle_w, handle_l, corner_r, segs)
    h_inner = rounded_rect_profile(hcx, hcy, handle_w - wall*2, handle_l - wall*2,
                                    max(corner_r - wall, 1.0), segs)

    # Bottom half
    tris += extrude_profile(h_outer, 0, split_z)
    n = len(h_inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = h_inner[i]; x2, y2 = h_inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    tris += fill_profile(h_outer, 0, flip=True)
    tris += ring_fill(h_outer, h_inner, wall, flip=False)
    tris += ring_fill(h_outer, h_inner, split_z, flip=False)

    # Top half
    top_z = split_z + 0.3
    tris += extrude_profile(h_outer, top_z, thick)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = h_inner[i]; x2, y2 = h_inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,thick - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,thick - wall),(x2,y2,thick - wall)))
    tris += fill_profile(h_outer, thick, flip=False)
    tris += ring_fill(h_outer, h_inner, top_z, flip=True)
    tris += ring_fill(h_outer, h_inner, thick - wall, flip=True)
    tris += fill_profile(h_inner, thick - wall, flip=True)

    # ── Round key head (at top of handle, like a real drum key) ──
    head_cx = 0
    head_cy = handle_l + head_w / 2 - 4.0  # Overlap slightly with handle top
    hd_outer = circle_profile(head_cx, head_cy, head_w / 2, 48)
    hd_inner = circle_profile(head_cx, head_cy, head_w / 2 - wall, 48)

    # Bottom half of head
    tris += extrude_profile(hd_outer, 0, split_z)
    n_hd = len(hd_inner)
    for i in range(n_hd):
        j = (i + 1) % n_hd
        x1, y1 = hd_inner[i]; x2, y2 = hd_inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    tris += fill_profile(hd_outer, 0, flip=True)
    tris += ring_fill(hd_outer, hd_inner, wall, flip=False)
    tris += ring_fill(hd_outer, hd_inner, split_z, flip=False)

    # Top half of head
    tris += extrude_profile(hd_outer, top_z, thick)
    for i in range(n_hd):
        j = (i + 1) % n_hd
        x1, y1 = hd_inner[i]; x2, y2 = hd_inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,thick - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,thick - wall),(x2,y2,thick - wall)))
    tris += fill_profile(hd_outer, thick, flip=False)
    tris += ring_fill(hd_outer, hd_inner, top_z, flip=True)
    tris += ring_fill(hd_outer, hd_inner, thick - wall, flip=True)
    tris += fill_profile(hd_inner, thick - wall, flip=True)

    # PCB standoffs in handle (3 posts along handle length)
    for sy_off in [8.0, 17.5, 27.0]:
        tris += standoff(0, sy_off, wall, standoff_h, outer_r=1.2, inner_r=0.5, segs=12)

    # USB-C cutout at bottom of handle (Y = 0)
    usb_z = wall + standoff_h + pcb_thick / 2
    tris = cutout_rect(tris, 0.0, 0.0, usb_z - 1.75, usb_z + 1.75, 9.5, wall + 1.0)

    # Speaker grille at top of handle (just below head junction)
    for gx in range(-1, 2):
        for gy in range(0, 2):
            tris = cutout_circle(tris, gx * 2.5, handle_l - 4.0 + gy * 2.5,
                                 thick - wall - 0.1, thick + 0.1, 0.6)

    # LED window on handle face
    tris = cutout_circle(tris, 0.0, handle_l - 10.0,
                         thick - wall - 0.1, thick + 0.1, 1.0)

    # ── Big square socket (8×8×10mm deep) at the center of the round head ──
    # This is THE defining feature — make it huge and centered
    socket_cx = 0.0
    socket_cy = head_cy
    socket_sz = 8.0
    tris = cutout_rect(tris, socket_cx, socket_cy,
                       thick - 10.0, thick + 0.1, socket_sz, socket_sz)

    # ── Fluted finger grips on handle (5 parallel channels along the length) ──
    for sy_off_pct in [0.15, 0.30, 0.45, 0.60, 0.75]:
        sy_off = handle_l * sy_off_pct
        # Shallow channel across the top
        tris = cutout_rect(tris, 0.0, sy_off,
                           thick - 0.8, thick + 0.1, handle_w * 0.9, 1.4)

    # Button on the side of handle
    tris = cutout_circle(tris, -handle_w / 2, handle_l * 0.5,
                         thick / 2 - 1.5, thick / 2 + 1.5, 1.5)

    # Snap-fit lip on handle
    lip = rounded_rect_profile(hcx, hcy, handle_w - wall*2 + SNAP_TOL*2,
                                handle_l - wall*2 + SNAP_TOL*2,
                                max(corner_r - wall, 1.0), segs)
    tris += extrude_profile(lip, split_z - 0.8, split_z)
    tris += fill_profile(lip, split_z, flip=False)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 12: Seed Capo — Spring clip for guitar neck/mic stand/music stand
# ════════════════════════════════════════════════════════════════════
# Spring clip shape: 40x20x15mm. Clips onto guitar neck, mic stand, etc.
# PCB inside one jaw, speaker faces outward. Universal musician's monitor clip.

def generate_seed_capo():
    """
    Seed Capo: dramatic asymmetric spring clip silhouette.
    Lower arm is long (45mm) and sits flat.
    Upper arm is SHORTER (28mm) and TILTED UP at 10° from the hinge,
    opening a visible wedge gap between the jaws.
    The hinge is a fat cylinder sticking out past the clip on both sides.
    """
    import math as _m
    tris = []

    arm_w = 18.0       # Y-axis width of both arms
    lower_len = 45.0   # Lower arm length (X)
    upper_len = 28.0   # Upper arm length (X) — shorter, asymmetric
    arm_t = 5.0        # Thickness of each arm
    hinge_gap = 3.5    # Gap at the closed (jaw) end
    corner_r = 2.5

    # Hinge parameters — sticks out past the arms
    hinge_r = 5.0      # Radius — fat and prominent
    hinge_extra = 4.0  # Extra length sticking out each side in Y
    hinge_x = 0.0      # Hinge centerline at X=0

    # Lower arm spans X = 0 to lower_len
    # Upper arm is tilted up 10° from hinge, so at X=0 it starts at z=hinge_gap
    # and at X=upper_len it reaches z = hinge_gap + upper_len*tan(10°) + arm_t
    tilt_deg = 12.0
    tilt = _m.radians(tilt_deg)
    cy = 0.0

    # ── Lower arm: flat slab from X=0 to X=lower_len, Z=0..arm_t ──
    l_profile = rounded_rect_profile(lower_len / 2, cy, lower_len, arm_w, corner_r, 20)
    tris += extrude_profile(l_profile, 0.0, arm_t)
    tris += fill_profile(l_profile, 0.0, flip=True)
    tris += fill_profile(l_profile, arm_t, flip=False)

    # Rubber grip recess on top face of lower arm (visible ridge pattern)
    for ridge_x in range(4, int(lower_len) - 2, 4):
        tris = cutout_rect(tris, ridge_x, cy,
                           arm_t - 0.6, arm_t + 0.1, 1.0, arm_w * 0.7)

    # ── Upper arm: tilted wedge ──
    # Build manually so the top surface slopes upward
    u_hw = upper_len / 2
    upper_cx = upper_len / 2
    z_bottom_back = hinge_gap               # Bottom of upper arm at hinge end
    z_top_back = hinge_gap + arm_t
    # At the front (open end, X = upper_len):
    lift_front = upper_len * _m.tan(tilt)
    z_bottom_front = hinge_gap + lift_front
    z_top_front = z_bottom_front + arm_t

    # 8 corners of a skewed box
    hw = arm_w / 2
    # front face = at X=upper_len, back face at X=0
    v = {
        'bbl': (0.0, -hw, z_bottom_back),  # back bottom left (Y-)
        'bbr': (0.0,  hw, z_bottom_back),  # back bottom right (Y+)
        'btl': (0.0, -hw, z_top_back),
        'btr': (0.0,  hw, z_top_back),
        'fbl': (upper_len, -hw, z_bottom_front),
        'fbr': (upper_len,  hw, z_bottom_front),
        'ftl': (upper_len, -hw, z_top_front),
        'ftr': (upper_len,  hw, z_top_front),
    }
    # 6 faces of the box, 2 triangles each
    def quad(a, b, c, d):
        tris.append(make_tri(a, b, c))
        tris.append(make_tri(a, c, d))
    quad(v['bbl'], v['bbr'], v['fbr'], v['fbl'])   # bottom (facing down)
    quad(v['btl'], v['ftl'], v['ftr'], v['btr'])   # top (facing up)
    quad(v['bbl'], v['btl'], v['btr'], v['bbr'])   # back face
    quad(v['fbl'], v['fbr'], v['ftr'], v['ftl'])   # front face
    quad(v['bbl'], v['fbl'], v['ftl'], v['btl'])   # side Y-
    quad(v['bbr'], v['btr'], v['ftr'], v['fbr'])   # side Y+

    # Fat hinge cylinder — Y axis, sticks out
    hinge_axis_y_lo = -arm_w / 2 - hinge_extra
    hinge_axis_y_hi =  arm_w / 2 + hinge_extra
    hinge_z = hinge_gap / 2 + arm_t / 2
    hinge_segs = 32
    for i in range(hinge_segs):
        a1 = 2 * _m.pi * i / hinge_segs
        a2 = 2 * _m.pi * (i + 1) / hinge_segs
        p1 = (hinge_x + hinge_r * _m.cos(a1), hinge_axis_y_lo, hinge_z + hinge_r * _m.sin(a1))
        p2 = (hinge_x + hinge_r * _m.cos(a2), hinge_axis_y_lo, hinge_z + hinge_r * _m.sin(a2))
        p3 = (hinge_x + hinge_r * _m.cos(a1), hinge_axis_y_hi, hinge_z + hinge_r * _m.sin(a1))
        p4 = (hinge_x + hinge_r * _m.cos(a2), hinge_axis_y_hi, hinge_z + hinge_r * _m.sin(a2))
        tris.append(make_tri(p1, p2, p4))
        tris.append(make_tri(p1, p4, p3))
        # end caps
        c_lo = (hinge_x, hinge_axis_y_lo, hinge_z)
        c_hi = (hinge_x, hinge_axis_y_hi, hinge_z)
        tris.append(make_tri(c_lo, p2, p1))
        tris.append(make_tri(c_hi, p3, p4))

    # Hinge pin hole (through the cylinder)
    # (Visually represented as a small dark cap on the end)
    pin_r = 1.5
    for i in range(16):
        a1 = 2 * _m.pi * i / 16
        a2 = 2 * _m.pi * (i + 1) / 16
        p1 = (hinge_x + pin_r * _m.cos(a1), hinge_axis_y_lo - 0.01, hinge_z + pin_r * _m.sin(a1))
        p2 = (hinge_x + pin_r * _m.cos(a2), hinge_axis_y_lo - 0.01, hinge_z + pin_r * _m.sin(a2))
        p3 = (hinge_x + pin_r * _m.cos(a1), hinge_axis_y_hi + 0.01, hinge_z + pin_r * _m.sin(a1))
        p4 = (hinge_x + pin_r * _m.cos(a2), hinge_axis_y_hi + 0.01, hinge_z + pin_r * _m.sin(a2))
        # Leave a recessed dark dot
        tris.append(make_tri(p1, p2, (hinge_x, hinge_axis_y_lo - 0.01, hinge_z)))
        tris.append(make_tri(p4, p3, (hinge_x, hinge_axis_y_hi + 0.01, hinge_z)))

    # Speaker grille on the UPPER arm's top face
    for i in range(-2, 3):
        for j in range(-1, 2):
            sx = upper_cx + i * 3.0
            sy = cy + j * 3.0
            # Project the slanted upper top-surface z at sx
            sz = hinge_gap + arm_t + (sx / upper_len) * lift_front
            tris = cutout_circle(tris, sx, sy, sz - 0.6, sz + 0.1, 0.7)

    # LED slit near upper arm tip
    tip_x = upper_len - 3.0
    tip_z = hinge_gap + arm_t + (tip_x / upper_len) * lift_front
    tris = led_crescent_slit(tris, tip_x, cy,
                             tip_z - 0.6, tip_z + 0.1,
                             slit_length=4.0)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 13: Seed Ring — Finger ring with PCB in signet-style mount
# ════════════════════════════════════════════════════════════════════

def generate_seed_ring():
    """
    Seed Ring: finger ring (US size 8 = 18mm inner dia, 24mm outer dia,
    8mm band width). Signet-style mount (12x10x6mm) on top holds a
    portion of the PCB. Speaker on mount top surface.
    """
    inner_r = 9.0       # 18mm inner diameter / 2
    outer_r = 12.0      # 24mm outer diameter / 2
    band_w = 8.0        # Band width (Z axis)
    mount_w = 8.0       # Mount width (X) — low-profile
    mount_h = 8.0       # Mount depth (Y)
    mount_z = 4.0       # Mount height above ring top — lower
    wall = 1.2

    segs = 96
    tris = []

    # ── Ring band ──
    outer_band = circle_profile(0, 0, outer_r, segs)
    inner_band = circle_profile(0, 0, inner_r, segs)
    tris += make_shell(outer_band, inner_band, 0, band_w)

    # ── Signet mount (raised platform on top of ring) ──
    # Position: centered at top of ring (Y = outer_r)
    mount_cx = 0.0
    mount_cy = outer_r - 1.0  # Slightly inset into ring top
    mount_z0 = band_w         # Sits on top of band
    mount_z1 = band_w + mount_z

    m_outer = rounded_rect_profile(mount_cx, mount_cy, mount_w, mount_h, 2.0, 6)
    m_inner = rounded_rect_profile(mount_cx, mount_cy, mount_w - wall*2, mount_h - wall*2, 1.0, 6)

    # Mount shell
    tris += extrude_profile(m_outer, mount_z0, mount_z1)
    n = len(m_inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = m_inner[i]; x2, y2 = m_inner[j]
        tris.append(make_tri((x1,y1,mount_z0 + wall),(x2,y2,mount_z1 - wall),(x2,y2,mount_z0 + wall)))
        tris.append(make_tri((x1,y1,mount_z0 + wall),(x1,y1,mount_z1 - wall),(x2,y2,mount_z1 - wall)))
    tris += fill_profile(m_outer, mount_z0, flip=True)
    tris += fill_profile(m_outer, mount_z1, flip=False)
    tris += ring_fill(m_outer, m_inner, mount_z0 + wall, flip=True)
    tris += ring_fill(m_outer, m_inner, mount_z1 - wall, flip=True)
    tris += fill_profile(m_inner, mount_z1 - wall, flip=True)

    # Speaker grille on mount top: 2x2 grid of tiny holes
    for gx in range(-1, 1):
        for gy in range(-1, 1):
            tris = cutout_circle(tris, mount_cx + gx * 2.5 + 1.25,
                                 mount_cy + gy * 2.5 + 1.25,
                                 mount_z1 - wall - 0.1, mount_z1 + 0.1, 0.5)

    # LED window on mount
    tris = cutout_circle(tris, mount_cx, mount_cy + 3.0,
                         mount_z1 - wall - 0.1, mount_z1 + 0.1, 0.6)

    # USB-C pocket on mount side (opposite the ring)
    tris = cutout_rect(tris, mount_cx, mount_cy + mount_h / 2,
                       mount_z0 + 1.0, mount_z1 - 1.0, 5.0, wall + 1.0)

    # Filleted top edge of mount (rounded for comfort)
    tris += fillet_rect_edge(m_outer, mount_z1, 0.8, going_up=False)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 14: Seed Earphone — TWS earphone shell
# ════════════════════════════════════════════════════════════════════

def generate_seed_earphone():
    """
    Seed Earphone: TWS (true wireless stereo) earphone shell.
    15x12x10mm. Ear canal nozzle + main body. Case only (PCB would
    need custom design). Nozzle for silicone ear tip.
    """
    body_w = 18.0      # Main body width (X) — kidney bean length
    body_h = 14.0      # Main body depth (Y)
    body_z = 10.0      # Main body height (Z)
    wall = 1.0
    nozzle_r = 2.5     # Ear canal nozzle outer radius (Ø5mm)
    nozzle_inner = 1.8 # Sound bore
    nozzle_len = 4.0   # Nozzle length

    segs = 48
    tris = []

    cx, cy = body_w / 2, body_h / 2
    split_z = body_z / 2

    # Kidney-bean outline: ellipse with an asymmetric indent on one side
    def kidney_profile(ccx, ccy, w, h, segs):
        pts = []
        hw, hh = w / 2, h / 2
        for i in range(segs):
            t = 2 * math.pi * i / segs
            # Base ellipse
            x = hw * math.cos(t)
            y = hh * math.sin(t)
            # Indent: subtract a bulge on the inside (negative x side)
            indent = 0.22 * hw * math.exp(-((t - math.pi) ** 2) * 3.5)
            x -= indent * math.cos(t) if math.cos(t) < 0 else 0
            pts.append((ccx + x, ccy + y))
        return pts

    outer = kidney_profile(cx, cy, body_w, body_h, segs)
    inner = kidney_profile(cx, cy, body_w - wall*2, body_h - wall*2, segs)

    # ── Bottom half ──
    tris += extrude_profile(outer, 0, split_z)
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    tris += fill_profile(outer, 0, flip=True)
    tris += ring_fill(outer, inner, wall, flip=False)
    tris += ring_fill(outer, inner, split_z, flip=False)

    # ── Top half ──
    top_z = split_z + 0.2
    tris += extrude_profile(outer, top_z, body_z)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,body_z - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,body_z - wall),(x2,y2,body_z - wall)))
    tris += fill_profile(outer, body_z, flip=False)
    tris += ring_fill(outer, inner, top_z, flip=True)
    tris += ring_fill(outer, inner, body_z - wall, flip=True)
    tris += fill_profile(inner, body_z - wall, flip=True)

    # ── Prominent angled ear canal nozzle (sticks out at 25° toward ear) ──
    # Nozzle goes from the body side (y=0) outward and slightly upward
    import math as _m
    nozzle_r2 = 3.2      # Larger outer radius for visibility
    nozzle_inner_r2 = 1.6
    nozzle_length = 9.0
    angle_deg = 25.0
    a_rad = _m.radians(angle_deg)
    base_cx = cx
    base_cy = 0.0
    base_cz = body_z * 0.55
    # Tip point
    tip_cx = base_cx
    tip_cy = base_cy - nozzle_length * _m.cos(a_rad)
    tip_cz = base_cz + nozzle_length * _m.sin(a_rad)
    # Build a tapered cylinder along this axis
    nozzle_segs = 20
    # Local frame: axis = normalized (tip - base); perpendicular = (1,0,0) and its cross
    ax_y = -_m.cos(a_rad)
    ax_z =  _m.sin(a_rad)
    # Perpendicular 1: (1, 0, 0)
    # Perpendicular 2: cross(axis, perp1) = (0*0 - 1*ax_z, 1*0 - 0*0, 0*0 - 0*ax_y) — let me compute
    # axis = (0, ax_y, ax_z); perp1 = (1, 0, 0); cross = (ay*0 - az*0, az*1 - 0*0, 0*0 - ay*1) = (0, az, -ay)
    p2_y = ax_z
    p2_z = -ax_y
    rings = 3
    for k in range(rings):
        t0 = k / rings
        t1 = (k + 1) / rings
        r0 = nozzle_r2 * (1.0 - 0.25 * t0)  # slight taper
        r1 = nozzle_r2 * (1.0 - 0.25 * t1)
        c0 = (base_cx, base_cy + ax_y * nozzle_length * t0, base_cz + ax_z * nozzle_length * t0)
        c1 = (base_cx, base_cy + ax_y * nozzle_length * t1, base_cz + ax_z * nozzle_length * t1)
        for i in range(nozzle_segs):
            a1 = 2 * _m.pi * i / nozzle_segs
            a2 = 2 * _m.pi * (i + 1) / nozzle_segs
            u1x = _m.cos(a1); v1y = _m.sin(a1)
            u2x = _m.cos(a2); v2y = _m.sin(a2)
            def ring_pt(c, r, u, v):
                return (c[0] + r * u, c[1] + r * v * p2_y, c[2] + r * v * p2_z)
            p1 = ring_pt(c0, r0, u1x, v1y)
            p2 = ring_pt(c0, r0, u2x, v2y)
            p3 = ring_pt(c1, r1, u1x, v1y)
            p4 = ring_pt(c1, r1, u2x, v2y)
            tris.append(make_tri(p1, p2, p4))
            tris.append(make_tri(p1, p4, p3))
            if k == rings - 1:
                # End cap at tip
                tris.append(make_tri(p3, p4, c1))

    # LED window on outer face
    tris = cutout_circle(tris, cx, body_h, body_z - wall - 0.1, body_z + 0.1, 0.8)

    # Charging contact pads (2 small holes on bottom)
    for dx in [-2.0, 2.0]:
        tris = cutout_circle(tris, cx + dx, cy, -0.1, wall + 0.1, 0.5)

    # Snap-fit lip (kidney bean shaped)
    lip = kidney_profile(cx, cy, body_w - wall*2 + SNAP_TOL*2,
                         body_h - wall*2 + SNAP_TOL*2, segs)
    tris += extrude_profile(lip, split_z - 0.5, split_z)
    tris += fill_profile(lip, split_z, flip=False)

    # Touch surface dimple on outer face
    tris = cutout_circle(tris, cx, cy, body_z - 0.5, body_z + 0.1, 4.0)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 15: Seed Headphone — Over-ear headphone ear cup
# ════════════════════════════════════════════════════════════════════

def generate_seed_headphone():
    """
    Seed Headphone: OVER-EAR headphone pair (left + right earcups + headband).
    Each cup: 60x50x25mm elliptical with 40mm driver recess on ear side.
    Connected by a headband arch. Left/right symmetric.
    """
    cup_w = 60.0       # Width (X)
    cup_h = 50.0       # Height (Y)
    cup_z = 25.0       # Depth (Z)
    wall = 2.0
    driver_r = 20.0    # 40mm driver
    cushion_depth = 3.0
    cushion_width = 6.0
    hinge_w = 8.0
    hinge_h = 12.0
    corner_r = 20.0    # Elliptical shape
    cup_separation = 140.0  # Distance between cup centers

    segs = 32               # Smooth elliptical curves
    tris = []

    # Render both cups and the headband
    for side in [-1, 1]:
        cup_offset_x = side * cup_separation / 2
        cx, cy = cup_offset_x, 0

        outer = rounded_rect_profile(cx, cy, cup_w, cup_h, corner_r, segs)
        inner = rounded_rect_profile(cx, cy, cup_w - wall*2, cup_h - wall*2,
                                      max(corner_r - wall, 8.0), segs)

        # Back plate and outer walls
        tris += extrude_profile(outer, 0, cup_z)
        tris += fill_profile(outer, 0, flip=True)
        n = len(inner)
        for i in range(n):
            j = (i + 1) % n
            x1, y1 = inner[i]; x2, y2 = inner[j]
            tris.append(make_tri((x1,y1,wall),(x2,y2,cup_z),(x2,y2,wall)))
            tris.append(make_tri((x1,y1,wall),(x1,y1,cup_z),(x2,y2,cup_z)))
        tris += ring_fill(outer, inner, wall, flip=False)
        tris += ring_fill(outer, inner, cup_z, flip=False)
        # Ear-side 35mm driver pocket recess (8mm deep into cup from the top)
        tris = cutout_circle(tris, cx, cy, cup_z - 8.0, cup_z + 0.1, 17.5)
        # Speaker grille in the recess (honeycomb)
        tris = apply_speaker_grille(tris, cx, cy,
                                    cup_z - 8.2, cup_z - 7.5,
                                    grid_r=12.0, hole_r=0.5, spacing=1.8)
        # LED window on back
        tris = cutout_circle(tris, cx, cy, -0.1, wall + 0.1, 1.5)

    # ── Headband arch connecting the two cups ──
    # Arch from top of left cup to top of right cup
    # Parametrize as a circular arc (radius 80mm, 3mm thick)
    band_radius = 80.0
    band_thick = 3.0
    band_width = 10.0
    band_segs = 48
    arc_span = math.pi  # Half circle

    # Center of arc: midpoint between cups, offset upward
    arc_cy = cup_h / 2
    # Calculate arc from angle -arc_span/2 to arc_span/2
    # so endpoints are at (±cup_separation/2, arc_cy + band_radius*cos(arc_span/2))
    # Make endpoints at the top of cups: y=cup_h/2, x=±cup_separation/2
    # Use simple parabolic arc instead for correctness
    for i in range(band_segs):
        t1 = i / band_segs
        t2 = (i + 1) / band_segs
        # Parabolic arc: x goes from -sep/2 to +sep/2
        x1 = -cup_separation / 2 + t1 * cup_separation
        x2 = -cup_separation / 2 + t2 * cup_separation
        # Arch height: peak at x=0, base at x=±sep/2
        arch_h = 40.0
        y1 = cup_h / 2 + arch_h * (1 - (2 * x1 / cup_separation) ** 2)
        y2 = cup_h / 2 + arch_h * (1 - (2 * x2 / cup_separation) ** 2)
        # Band cross-section: rectangular band_width × band_thick
        for dx_off, dy_off in [(-band_width/2, 0), (band_width/2, 0)]:
            pass
        # Create the band as a swept rectangle
        # At each point we have a tangent; we'll use a simple Y-axis strip
        # Build quads between (x1, y1, z0→z1) and (x2, y2, z0→z1) where z is band_thick
        z_lo = cup_z / 2 - band_thick / 2
        z_hi = cup_z / 2 + band_thick / 2
        # Outer front face
        tris.append(make_tri((x1, y1 + band_width/2, z_lo), (x2, y2 + band_width/2, z_lo), (x2, y2 + band_width/2, z_hi)))
        tris.append(make_tri((x1, y1 + band_width/2, z_lo), (x2, y2 + band_width/2, z_hi), (x1, y1 + band_width/2, z_hi)))
        # Outer back face
        tris.append(make_tri((x1, y1 - band_width/2, z_lo), (x2, y2 - band_width/2, z_hi), (x2, y2 - band_width/2, z_lo)))
        tris.append(make_tri((x1, y1 - band_width/2, z_lo), (x1, y1 - band_width/2, z_hi), (x2, y2 - band_width/2, z_hi)))
        # Top face
        tris.append(make_tri((x1, y1 - band_width/2, z_hi), (x1, y1 + band_width/2, z_hi), (x2, y2 + band_width/2, z_hi)))
        tris.append(make_tri((x1, y1 - band_width/2, z_hi), (x2, y2 + band_width/2, z_hi), (x2, y2 - band_width/2, z_hi)))
        # Bottom face
        tris.append(make_tri((x1, y1 - band_width/2, z_lo), (x2, y2 + band_width/2, z_lo), (x1, y1 + band_width/2, z_lo)))
        tris.append(make_tri((x1, y1 - band_width/2, z_lo), (x2, y2 - band_width/2, z_lo), (x2, y2 + band_width/2, z_lo)))

    return tris


def _OLD_generate_seed_headphone_unused():
    """Old single-cup version (kept for reference, not used)."""
    cup_w = 60.0
    cup_h = 50.0
    cup_z = 25.0
    wall = 2.0
    driver_r = 20.0
    cushion_depth = 3.0
    cushion_width = 6.0
    hinge_w = 8.0
    hinge_h = 12.0
    corner_r = 20.0

    segs = 32
    tris = []

    cx, cy = cup_w / 2, cup_h / 2

    outer = rounded_rect_profile(cx, cy, cup_w, cup_h, corner_r, segs)
    inner = rounded_rect_profile(cx, cy, cup_w - wall*2, cup_h - wall*2,
                                  max(corner_r - wall, 8.0), segs)

    # ── Main cup body ──
    tris += extrude_profile(outer, 0, cup_z)
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,cup_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,cup_z),(x2,y2,cup_z)))
    # Back plate (driver side)
    tris += fill_profile(outer, 0, flip=True)
    tris += ring_fill(outer, inner, wall, flip=False)
    # Open front (ear side) — ring at cup_z
    tris += ring_fill(outer, inner, cup_z, flip=False)

    # ── Driver mounting ring (40mm, centered) ──
    driver_outer = circle_profile(cx, cy, driver_r + 1.5, 48)
    driver_inner = circle_profile(cx, cy, driver_r, 48)
    tris += make_shell(driver_outer, driver_inner, wall, wall + 3.0)

    # Driver holes (sound pass-through in back plate)
    for gx in range(-3, 4):
        for gy in range(-3, 4):
            dx = gx * 3.5
            dy = gy * 3.5
            if math.sqrt(dx*dx + dy*dy) < driver_r - 2:
                tris = cutout_circle(tris, cx + dx, cy + dy,
                                     -0.1, wall + 0.1, 1.0)

    # ── Cushion recess ring (front opening) ──
    cushion_outer = rounded_rect_profile(cx, cy, cup_w - 2, cup_h - 2, corner_r - 1, segs)
    cushion_inner = rounded_rect_profile(cx, cy, cup_w - 2 - cushion_width*2,
                                          cup_h - 2 - cushion_width*2,
                                          max(corner_r - 1 - cushion_width, 4.0), segs)
    # Recess lip for cushion attachment
    tris += extrude_profile(cushion_inner, cup_z, cup_z + cushion_depth)
    tris += fill_profile(cushion_inner, cup_z + cushion_depth, flip=False)

    # ── Headband hinge mount (top of cup) ──
    hinge_cx = cx
    hinge_cy = cup_h + 2.0  # Extends above cup
    h_profile = rounded_rect_profile(hinge_cx, hinge_cy, hinge_w, hinge_h, 2.0, 4)
    tris += extrude_profile(h_profile, cup_z / 2 - 5, cup_z / 2 + 5)
    tris += fill_profile(h_profile, cup_z / 2 - 5, flip=True)
    tris += fill_profile(h_profile, cup_z / 2 + 5, flip=False)

    # Hinge pin hole
    tris = cutout_circle(tris, hinge_cx, hinge_cy,
                         cup_z / 2 - 5.1, cup_z / 2 + 5.1, 1.5)

    # ── PCB mounting posts inside cup ──
    for angle_deg in [0, 120, 240]:
        a = math.radians(angle_deg)
        sx = cx + 10.0 * math.cos(a)
        sy = cy + 10.0 * math.sin(a)
        tris += standoff(sx, sy, wall, 2.0, outer_r=1.5, inner_r=0.6, segs=12)

    # USB-C cutout at bottom of cup
    tris = cutout_rect(tris, cx, 0, cup_z / 2 - 1.75, cup_z / 2 + 1.75,
                       9.5, wall + 1.0)

    # LED window on outer face
    tris = cutout_circle(tris, cx, cy, -0.1, wall + 0.1, 1.5)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 16: Seed Neckband — U-shaped neckband speaker
# ════════════════════════════════════════════════════════════════════

def generate_seed_neckband():
    """
    Seed Neckband: U-shaped neckband worn around the neck.
    Speaker pods at both ends near ears. Battery in the band.
    Band inner diameter ~140mm (neck), 10mm cross-section tube.
    """
    neck_r = 70.0      # Neck radius (inner)
    tube_r = 7.0       # Cross-section radius of band tube (thicker for battery/wiring)
    wall = 1.2
    pod_w = 25.0       # Speaker pod width (chunkier)
    pod_h = 20.0       # Speaker pod depth
    pod_z = 15.0       # Speaker pod height
    arc_segs = 64      # Smooth U-arc
    tube_segs = 32     # Smooth tube cross-section

    tris = []

    # U-shape: semicircle from -90 to +90 degrees (open at top)
    # Generate tube along the arc
    for i in range(arc_segs):
        a1 = math.pi / 2 + math.pi * i / arc_segs      # 90 to 270 degrees
        a2 = math.pi / 2 + math.pi * (i + 1) / arc_segs

        # Center of tube cross-section at each arc point
        c1x = neck_r * math.cos(a1)
        c1y = neck_r * math.sin(a1)
        c2x = neck_r * math.cos(a2)
        c2y = neck_r * math.sin(a2)

        # Generate tube segments
        for j in range(tube_segs):
            t1 = 2 * math.pi * j / tube_segs
            t2 = 2 * math.pi * (j + 1) / tube_segs

            # Outer tube surface
            # Direction perpendicular to arc tangent and Z
            n1x = math.cos(a1)
            n1y = math.sin(a1)
            n2x = math.cos(a2)
            n2y = math.sin(a2)

            # Cross-section point offsets (in local frame)
            or1 = tube_r * math.cos(t1)
            oz1 = tube_r * math.sin(t1)
            or2 = tube_r * math.cos(t2)
            oz2 = tube_r * math.sin(t2)

            # World coordinates
            p1 = (c1x + n1x * or1, c1y + n1y * or1, oz1)
            p2 = (c1x + n1x * or2, c1y + n1y * or2, oz2)
            p3 = (c2x + n2x * or1, c2y + n2y * or1, oz1)
            p4 = (c2x + n2x * or2, c2y + n2y * or2, oz2)

            tris.append(make_tri(p1, p3, p2))
            tris.append(make_tri(p2, p3, p4))

    # ── Speaker pods at both ends ──
    for side in [-1, 1]:
        # Pod at arc endpoints (top of U, near ears)
        end_angle = math.pi / 2 if side == 1 else 3 * math.pi / 2
        pod_cx = neck_r * math.cos(end_angle) + side * pod_w / 2
        pod_cy = neck_r * math.sin(end_angle)

        p_outer = rounded_rect_profile(pod_cx, pod_cy, pod_w, pod_h, 4.0, 6)
        p_inner = rounded_rect_profile(pod_cx, pod_cy, pod_w - wall*2, pod_h - wall*2, 2.0, 6)

        # Pod shell
        tris += extrude_profile(p_outer, -pod_z / 2, pod_z / 2)
        n = len(p_inner)
        for ii in range(n):
            jj = (ii + 1) % n
            x1, y1 = p_inner[ii]; x2, y2 = p_inner[jj]
            tris.append(make_tri((x1,y1,-pod_z/2 + wall),(x2,y2,pod_z/2 - wall),(x2,y2,-pod_z/2 + wall)))
            tris.append(make_tri((x1,y1,-pod_z/2 + wall),(x1,y1,pod_z/2 - wall),(x2,y2,pod_z/2 - wall)))
        tris += fill_profile(p_outer, -pod_z / 2, flip=True)
        tris += fill_profile(p_outer, pod_z / 2, flip=False)
        tris += ring_fill(p_outer, p_inner, -pod_z / 2 + wall, flip=True)
        tris += ring_fill(p_outer, p_inner, pod_z / 2 - wall, flip=True)
        tris += fill_profile(p_inner, pod_z / 2 - wall, flip=True)

        # Speaker grille on top of pod
        for gx in range(-1, 2):
            for gy in range(-1, 2):
                tris = cutout_circle(tris, pod_cx + gx * 2.5, pod_cy + gy * 2.5,
                                     pod_z / 2 - wall - 0.1, pod_z / 2 + 0.1, 0.6)

        # LED window
        tris = cutout_circle(tris, pod_cx, pod_cy + 5.0,
                             pod_z / 2 - wall - 0.1, pod_z / 2 + 0.1, 0.8)

    # USB-C cutout at bottom center of U
    bottom_x = neck_r * math.cos(math.pi)  # Bottom of U
    bottom_y = neck_r * math.sin(math.pi)
    tris = cutout_rect(tris, bottom_x, bottom_y, -1.75, 1.75, 9.5, wall + 1.0)

    # ── Articulated joint hinges at apex (visible seam on both sides) ──
    # Small hinge barrel visible cylinders near the pods
    for joint_ang in [math.pi / 2 + 0.25, 3 * math.pi / 2 - 0.25]:
        jx = neck_r * math.cos(joint_ang)
        jy = neck_r * math.sin(joint_ang)
        joint_profile = circle_profile(jx, jy, tube_r + 1.0, 16)
        tris += extrude_profile(joint_profile, -tube_r - 1.0, tube_r + 1.0)
        # Seam groove
        tris = cutout_rect(tris, jx, jy, -0.3, 0.3, tube_r * 2 + 3.0, 0.6)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 17: Seed Glasses — Temple (arm) attachment for eyeglasses
# ════════════════════════════════════════════════════════════════════

def generate_seed_glasses():
    """
    Seed Glasses: temple arm attachment. 170x15x8mm elongated housing
    that clips onto eyeglass temples. PCB in the thick section near ear.
    Speaker near ear tip. Slim profile.
    """
    temple_l = 45.0    # Length (X axis) — compact temple-grip clip
    temple_w = 15.0    # Width (Y axis)
    temple_z = 8.0     # Height (Z axis)
    wall = 1.0
    corner_r = 4.0
    pcb_section_l = 30.0  # PCB housing section length
    pcb_section_start = 8.0  # Start of PCB section (leave small front clip tab)

    segs = 24
    tris = []

    # ── Thin front section (cosmetic, clips to temple arm) ──
    thin_l = pcb_section_start
    thin_w = 8.0       # Narrower front section
    thin_z = 5.0       # Thinner front section
    thin_cx = thin_l / 2
    thin_cy = temple_w / 2

    t_outer = rounded_rect_profile(thin_cx, thin_cy, thin_l, thin_w, 3.0, segs)
    tris += extrude_profile(t_outer, 0, thin_z)
    tris += fill_profile(t_outer, 0, flip=True)
    tris += fill_profile(t_outer, thin_z, flip=False)

    # Clip channel on bottom (to grip temple arm)
    clip_w = 4.0
    clip_depth = 2.0
    for cx_pos in [thin_l * 0.25, thin_l * 0.5, thin_l * 0.75]:
        tris = cutout_rect(tris, cx_pos, thin_cy,
                           -0.1, clip_depth + 0.1, 6.0, clip_w)

    # ── Thick PCB housing section (near ear) ──
    pcb_cx = pcb_section_start + pcb_section_l / 2
    pcb_cy = temple_w / 2

    p_outer = rounded_rect_profile(pcb_cx, pcb_cy, pcb_section_l, temple_w, corner_r, segs)
    p_inner = rounded_rect_profile(pcb_cx, pcb_cy, pcb_section_l - wall*2, temple_w - wall*2,
                                    max(corner_r - wall, 1.5), segs)

    split_z = temple_z / 2

    # Bottom half
    tris += extrude_profile(p_outer, 0, split_z)
    n = len(p_inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = p_inner[i]; x2, y2 = p_inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    tris += fill_profile(p_outer, 0, flip=True)
    tris += ring_fill(p_outer, p_inner, wall, flip=False)
    tris += ring_fill(p_outer, p_inner, split_z, flip=False)

    # Top half
    top_z = split_z + 0.2
    tris += extrude_profile(p_outer, top_z, temple_z)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = p_inner[i]; x2, y2 = p_inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,temple_z - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,temple_z - wall),(x2,y2,temple_z - wall)))
    tris += fill_profile(p_outer, temple_z, flip=False)
    tris += ring_fill(p_outer, p_inner, top_z, flip=True)
    tris += ring_fill(p_outer, p_inner, temple_z - wall, flip=True)
    tris += fill_profile(p_inner, temple_z - wall, flip=True)

    # PCB standoffs
    for dx in [-10, 0, 10]:
        tris += standoff(pcb_cx + dx, pcb_cy, wall, 0.8,
                         outer_r=1.0, inner_r=0.4, segs=12)

    # Speaker grille near ear end
    spk_x = temple_l - 8.0
    for gx in range(-1, 2):
        for gy in range(-1, 2):
            tris = cutout_circle(tris, spk_x + gx * 2.5, pcb_cy + gy * 2.5,
                                 temple_z - wall - 0.1, temple_z + 0.1, 0.5)

    # LED window
    tris = cutout_circle(tris, pcb_cx, pcb_cy,
                         temple_z - wall - 0.1, temple_z + 0.1, 0.8)

    # USB-C cutout at rear end
    usb_z = wall + 0.8 + 0.8
    tris = cutout_rect(tris, temple_l, pcb_cy, usb_z - 1.75, usb_z + 1.75,
                       wall + 1.0, 9.5)

    # Snap-fit lip
    lip = rounded_rect_profile(pcb_cx, pcb_cy, pcb_section_l - wall*2 + SNAP_TOL*2,
                                temple_w - wall*2 + SNAP_TOL*2,
                                max(corner_r - wall, 1.5), segs)
    tris += extrude_profile(lip, split_z - 0.6, split_z)
    tris += fill_profile(lip, split_z, flip=False)

    # ── BIG J-hook sticking out from the front (X=temple_l) end ──
    # The body sits as usual; from X=temple_l it extends out in +X then curves
    # back upward (+Z) forming a J/U shape that reads "clip over a temple arm".
    hook_start_x = temple_l - 1.0
    hook_arm_len = 14.0   # Length of the outer arm extending in +X
    hook_curl_r = 5.0     # Radius of the curl back up
    hook_thick_y = 5.0    # Width in Y (match temple_w)
    hook_thick_z = 3.0    # Thickness in Z

    # Straight horizontal arm at z=0 level from (hook_start_x, 0, 0..hook_thick_z)
    # extending to (hook_start_x + hook_arm_len, 0, 0..hook_thick_z)
    arm_y_lo = pcb_cy - hook_thick_y / 2
    arm_y_hi = pcb_cy + hook_thick_y / 2

    # Solid arm block
    def box_cuboid(x0, x1, y0, y1, z0, z1):
        pts = [
            (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
            (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
        ]
        idx_faces = [
            (0, 3, 2, 1),  # bottom
            (4, 5, 6, 7),  # top
            (0, 1, 5, 4),  # front
            (2, 3, 7, 6),  # back
            (0, 4, 7, 3),  # left
            (1, 2, 6, 5),  # right
        ]
        out = []
        for (a, b, c, d) in idx_faces:
            out.append(make_tri(pts[a], pts[b], pts[c]))
            out.append(make_tri(pts[a], pts[c], pts[d]))
        return out

    tris += box_cuboid(hook_start_x, hook_start_x + hook_arm_len,
                       arm_y_lo, arm_y_hi, 0.0, hook_thick_z)

    # Curling segment: quarter-circle arc from (arm_end_x, z=0) going down-then-up
    # Actually simpler: add a vertical block at the outer end that rises
    # PLUS a connector going back over, forming an inverted U.
    outer_x = hook_start_x + hook_arm_len
    # Vertical post rising from outer tip to form the curl
    tris += box_cuboid(outer_x, outer_x + hook_thick_z * 1.2,
                       arm_y_lo, arm_y_hi, 0.0, temple_z + 2.0)
    # Horizontal return arm at top — goes back from (outer_x) to hook_start_x level
    tris += box_cuboid(hook_start_x, outer_x + hook_thick_z * 1.2,
                       arm_y_lo, arm_y_hi, temple_z - 1.0, temple_z + 2.0)

    # Bone-conduction contact pad recess on the main body
    tris = cutout_circle(tris, pcb_cx, pcb_cy + 5.0,
                         temple_z - 0.5, temple_z + 0.1, 2.5)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 18: Seed Watch — Wristwatch-style enclosure
# ════════════════════════════════════════════════════════════════════

def generate_seed_watch():
    """
    Seed Watch: wristwatch case. 42mm dial diameter, 10mm thick.
    Speaker grille on case back (bone conduction toward wrist).
    Band lug attachments at top and bottom. PCB inside.
    """
    dial_r = 21.0      # 42mm / 2
    case_r = 23.0      # Bezel overhang
    total_h = 10.0     # Thickness
    wall = 1.5
    pcb_thick = 1.6
    standoff_h = 0.8
    lug_w = 22.0       # Lug-to-lug width (standard watch band)
    lug_h = 6.0        # Lug length extending from case
    lug_thick = 3.0    # Lug thickness
    lug_gap = 2.0      # Spring bar gap

    segs = 128
    tris = []

    inner_r = case_r - wall

    outer = circle_profile(0, 0, case_r, segs)
    inner = circle_profile(0, 0, inner_r, segs)
    split_z = total_h / 2

    # ── Bottom half (case back — faces wrist, has speaker grille) ──
    tris += extrude_profile(outer, 0, split_z)
    for i in range(segs):
        j = (i + 1) % segs
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    tris += fill_profile(outer, 0, flip=True)
    tris += ring_fill(outer, inner, wall, flip=False)
    tris += ring_fill(outer, inner, split_z, flip=False)

    # Speaker grille on case back (bone conduction to wrist)
    for gx in range(-2, 3):
        for gy in range(-2, 3):
            dx = gx * 3.0
            dy = gy * 3.0
            if math.sqrt(dx*dx + dy*dy) < inner_r - 3:
                tris = cutout_circle(tris, dx, dy, -0.1, wall + 0.1, 0.8)

    # PCB standoffs
    for angle_deg in [0, 90, 180, 270]:
        a = math.radians(angle_deg)
        sx = 10.0 * math.cos(a)
        sy = 10.0 * math.sin(a)
        tris += standoff(sx, sy, wall, standoff_h, outer_r=1.2, inner_r=0.5, segs=12)

    # USB-C cutout at 3 o'clock position (X = case_r)
    usb_z = wall + standoff_h + pcb_thick / 2
    tris = cutout_rect(tris, case_r, 0, usb_z - 1.75, usb_z + 1.75, wall + 1.0, 9.5)

    # Button cutout at 2 o'clock position
    btn_angle = math.radians(60)
    btn_x = case_r * math.cos(btn_angle)
    btn_y = case_r * math.sin(btn_angle)
    tris = cutout_rect(tris, btn_x, btn_y, split_z - 1.5, split_z + 1.5, wall + 1.0, 2.5)

    # ── Top half (crystal/display side) ──
    top_z = split_z + 0.3
    tris += extrude_profile(outer, top_z, total_h)
    for i in range(segs):
        j = (i + 1) % segs
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,total_h - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,total_h - wall),(x2,y2,total_h - wall)))
    tris += fill_profile(outer, total_h, flip=False)
    tris += ring_fill(outer, inner, top_z, flip=True)
    tris += ring_fill(outer, inner, total_h - wall, flip=True)
    tris += fill_profile(inner, total_h - wall, flip=True)

    # LED window on top face (status indicator)
    tris = cutout_circle(tris, 0.0, 0.0, total_h - wall - 0.1, total_h + 0.1, 2.0)

    # ── Big horn-shaped lugs at 12 and 6 o'clock, clearly drooping downward ──
    # Each pair = 2 lugs per side, spaced lug_w apart, curving down 45° toward the wrist
    lug_extend = 14.0   # How far the lug extends past the case (in Y direction)
    lug_wide = 6.0      # Thickness of each lug arm (in X direction)
    lug_drop = 6.0      # Total vertical drop at the tip
    lug_height = 5.0    # Lug cross-section height (in Z)
    lug_arm_segs = 12   # Segments along the curved length
    for direction in [1, -1]:  # 1=12 o'clock, -1=6 o'clock
        for side in [-1, 1]:
            arm_cx = side * (lug_w / 2 - lug_wide / 2)
            # Build a swept rounded rectangle that curves down as it extends out
            prev = None
            for k in range(lug_arm_segs + 1):
                t = k / lug_arm_segs
                # Y goes from (case_r - 1.0) outward to (case_r + lug_extend)
                ly = direction * (case_r - 1.0 + t * (lug_extend + 1.0))
                # Z goes from split_z DOWN to (split_z - lug_drop) following a quarter-circle feel
                lz = split_z - lug_drop * (t ** 1.6)
                # Cross section: square at (arm_cx, ly, lz) of size lug_wide × lug_height
                hw = lug_wide / 2
                hh = lug_height / 2
                ring = [
                    (arm_cx - hw, ly, lz - hh),
                    (arm_cx + hw, ly, lz - hh),
                    (arm_cx + hw, ly, lz + hh),
                    (arm_cx - hw, ly, lz + hh),
                ]
                if prev is not None:
                    for ii in range(4):
                        jj = (ii + 1) % 4
                        tris.append(make_tri(prev[ii], prev[jj], ring[jj]))
                        tris.append(make_tri(prev[ii], ring[jj], ring[ii]))
                else:
                    # Close back end (facing toward case)
                    tris.append(make_tri(ring[0], ring[2], ring[1]))
                    tris.append(make_tri(ring[0], ring[3], ring[2]))
                prev = ring
            # Close far end (tip)
            if prev is not None:
                tris.append(make_tri(prev[0], prev[1], prev[2]))
                tris.append(make_tri(prev[0], prev[2], prev[3]))

    # Dial face recess — DEEP so it's visible (2mm deep, centered)
    tris = cutout_circle(tris, 0.0, 0.0, total_h - 2.0, total_h + 0.1, 17.5)
    # Hour tick marks around dial (12 tiny recessed dots near rim)
    for hi in range(12):
        a = 2 * math.pi * hi / 12
        tx = (case_r - 3.0) * math.cos(a)
        ty = (case_r - 3.0) * math.sin(a)
        tris = cutout_circle(tris, tx, ty, total_h - 0.6, total_h + 0.1, 0.6)

    # Crown button on 3 o'clock (outer edge)
    tris = cutout_rect(tris, case_r, 0, split_z - 1.5, split_z + 1.5,
                       wall + 1.0, 3.0)

    # Snap-fit lip
    lip_profile = circle_profile(0, 0, inner_r + SNAP_TOL, segs)
    tris += extrude_profile(lip_profile, split_z - 0.8, split_z)
    tris += fill_profile(lip_profile, split_z, flip=False)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 19: Seed Hat Clip — Brim clip-on speaker
# ════════════════════════════════════════════════════════════════════

def generate_seed_hat_clip():
    """
    Seed Hat Clip: clips onto hat brim. 25x15x8mm body with
    spring clip mechanism. Speaker near ear when clipped to brim.
    """
    body_w = 25.0
    body_h = 15.0
    body_z = 8.0
    wall = 1.2
    corner_r = 4.0
    clip_gap = 1.5     # Hat brim thickness (reduced from 3.0)
    clip_arm_len = 25.0 # Longer arm
    clip_arm_thick = 1.5
    pcb_thick = 1.6
    standoff_h = 0.5

    segs = 24
    tris = []

    cx, cy = body_w / 2, body_h / 2
    split_z = body_z / 2

    outer = rounded_rect_profile(cx, cy, body_w, body_h, corner_r, segs)
    inner = rounded_rect_profile(cx, cy, body_w - wall*2, body_h - wall*2,
                                  max(corner_r - wall, 1.5), segs)

    # ── Bottom half ──
    tris += extrude_profile(outer, 0, split_z)
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    tris += fill_profile(outer, 0, flip=True)
    tris += ring_fill(outer, inner, wall, flip=False)
    tris += ring_fill(outer, inner, split_z, flip=False)

    # ── Top half ──
    top_z = split_z + 0.2
    tris += extrude_profile(outer, top_z, body_z)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,body_z - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,body_z - wall),(x2,y2,body_z - wall)))
    tris += fill_profile(outer, body_z, flip=False)
    tris += ring_fill(outer, inner, top_z, flip=True)
    tris += ring_fill(outer, inner, body_z - wall, flip=True)
    tris += fill_profile(inner, body_z - wall, flip=True)

    # PCB standoffs
    for angle_deg in [0, 120, 240]:
        a = math.radians(angle_deg)
        sx = cx + 7.0 * math.cos(a)
        sy = cy + 7.0 * math.sin(a)
        tris += standoff(sx, sy, wall, standoff_h, outer_r=1.0, inner_r=0.4, segs=12)

    # Speaker grille on top
    for gx in range(-1, 2):
        for gy in range(-1, 2):
            tris = cutout_circle(tris, cx + gx * 2.5, cy + gy * 2.5,
                                 body_z - wall - 0.1, body_z + 0.1, 0.6)

    # LED window
    tris = cutout_circle(tris, cx + 8.0, cy, body_z - wall - 0.1, body_z + 0.1, 0.8)

    # USB-C cutout
    usb_z = wall + standoff_h + pcb_thick / 2
    tris = cutout_rect(tris, body_w, cy, usb_z - 1.75, usb_z + 1.75, wall + 1.0, 9.5)

    # ── Clip arm (extends from bottom, curves under to grip brim) ──
    clip_profile = rect_profile(cx, -clip_arm_len / 2, body_w * 0.6, clip_arm_len)
    tris += extrude_profile(clip_profile, -clip_gap - clip_arm_thick, -clip_gap)
    tris += fill_profile(clip_profile, -clip_gap - clip_arm_thick, flip=True)
    tris += fill_profile(clip_profile, -clip_gap, flip=False)

    # Clip bridge (connects body to clip arm)
    bridge_profile = rect_profile(cx, -1.0, body_w * 0.4, 3.0)
    tris += extrude_profile(bridge_profile, -clip_gap, 0)
    tris += fill_profile(bridge_profile, -clip_gap, flip=True)

    # Grip pads on clip inner surfaces
    for px in [cx - 6, cx, cx + 6]:
        tris = cutout_rect(tris, px, -clip_arm_len / 2,
                           -clip_gap - 0.1, -clip_gap + 0.5, 1.5, 1.5)

    # ── Return lip at clip tip (for bite) ──
    lip_profile = rect_profile(cx, -clip_arm_len + 1.5, body_w * 0.6, 2.0)
    tris += extrude_profile(lip_profile, -clip_gap - clip_arm_thick, -clip_gap - clip_arm_thick + 1.5)
    tris += fill_profile(lip_profile, -clip_gap - clip_arm_thick + 1.5, flip=False)

    # Snap-fit lip
    lip = rounded_rect_profile(cx, cy, body_w - wall*2 + SNAP_TOL*2,
                                body_h - wall*2 + SNAP_TOL*2,
                                max(corner_r - wall, 1.5), segs)
    tris += extrude_profile(lip, split_z - 0.5, split_z)
    tris += fill_profile(lip, split_z, flip=False)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 20: Seed Shoe — Insole insert for tactile bass
# ════════════════════════════════════════════════════════════════════

def generate_seed_shoe():
    """
    Seed Shoe: foot-shaped insole insert. Wider at the toe, narrower at
    the heel, with a visible arch curve. Raised tread ridges on top.
    2 through-slots for shoelace retention.
    """
    import math as _m
    insole_w = 110.0   # Length (X axis)
    insole_h = 44.0    # Max width (Y axis)
    insole_z = 5.0     # Height
    wall = 0.8
    corner_r = 12.0
    vibe_r = 7.0
    pcb_thick = 1.6
    standoff_h = 0.3
    segs = 24

    tris = []

    cx = insole_w / 2
    cy = 0.0
    split_z = insole_z / 2

    # ── Asymmetric foot-shaped profile ──
    def foot_profile(pts_n=80):
        """
        Build an outline that is wide at one end (toe, X=insole_w)
        and narrower at the other (heel, X=0), with an arch curve on the inside.
        """
        pts = []
        hw_max = insole_h / 2
        for i in range(pts_n):
            t = i / (pts_n - 1)  # 0 at heel, 1 at toe
            x = t * insole_w
            # Width envelope: narrow at heel (0.6 hw_max), wide at toe (1.0 hw_max)
            width_factor = 0.65 + 0.35 * _m.sin(t * _m.pi) + 0.20 * t
            width_factor = min(1.0, width_factor)
            w = hw_max * width_factor
            pts.append((x, w))
        # Now go back along the other side (with arch curve — inside narrower)
        for i in range(pts_n):
            t = 1 - i / (pts_n - 1)
            x = t * insole_w
            width_factor = 0.65 + 0.35 * _m.sin(t * _m.pi) + 0.20 * t
            # Arch indent: subtract a bit near the middle (arch of foot)
            arch = 0.25 * _m.exp(-((t - 0.55) ** 2) * 20.0)
            w = hw_max * width_factor * (1.0 - arch)
            pts.append((x, -w))
        return pts

    outer = foot_profile(80)
    # Inner (shrunk uniformly)
    inner = [(p[0] + (0 if p[0] < insole_w / 2 else -wall) + (wall if p[0] < insole_w / 2 else 0),
              p[1] * 0.92) for p in outer]
    # Simpler: pure scale around center for inner
    inner = [(cx + (p[0] - cx) * 0.96, p[1] * 0.88) for p in outer]

    # ── Bottom half (sole side) ──
    tris += extrude_profile(outer, 0, split_z)
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    tris += fill_profile(outer, 0, flip=True)
    tris += ring_fill(outer, inner, wall, flip=False)
    tris += ring_fill(outer, inner, split_z, flip=False)

    # ── Top half (foot side) ──
    top_z = split_z + 0.2
    tris += extrude_profile(outer, top_z, insole_z)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,insole_z - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,insole_z - wall),(x2,y2,insole_z - wall)))
    tris += fill_profile(outer, insole_z, flip=False)
    tris += ring_fill(outer, inner, top_z, flip=True)
    tris += ring_fill(outer, inner, insole_z - wall, flip=True)
    tris += fill_profile(inner, insole_z - wall, flip=True)

    # Vibration motor cavities (2 motors — ball of foot area)
    for vx in [cx - 15, cx + 15]:
        tris = cutout_circle(tris, vx, cy, wall - 0.1, split_z + 0.1, vibe_r)

    # PCB pocket (centered, between motors)
    tris = cutout_rect(tris, cx, cy, wall - 0.1, split_z + 0.1, 30.0, 15.0)

    # USB-C cutout at side edge
    usb_z = split_z
    tris = cutout_rect(tris, insole_w, cy, usb_z - 1.75, usb_z + 1.75, wall + 1.0, 9.5)

    # Ventilation holes (breathability)
    for vx in range(4):
        for vy in range(2):
            hx = 20 + vx * 20
            hy = 10 + vy * 20
            tris = cutout_circle(tris, hx, hy, -0.1, wall + 0.1, 1.5)

    # ── 2 big shoelace-slot cutouts, THROUGH the entire body ──
    for sx in [cx - 22.0, cx + 22.0]:
        tris = cutout_rect(tris, sx, cy, -0.1, insole_z + 0.2, 6.0, 18.0)

    # ── 4 raised tread-style ridges across the top face (visible from above) ──
    ridge_h = 1.2
    ridge_w = 2.5
    for ridge_x in [cx - 15, cx - 5, cx + 5, cx + 15]:
        # Spans the width minus a margin
        ridge_len = insole_h - 12
        ridge_profile = rect_profile(ridge_x, cy, ridge_w, ridge_len)
        tris += extrude_profile(ridge_profile, insole_z - 0.01, insole_z + ridge_h)
        tris += fill_profile(ridge_profile, insole_z + ridge_h, flip=False)
        # Front/back edges of the raised bar
        tris += fill_profile(ridge_profile, insole_z - 0.01, flip=True)

    # Snap-fit lip
    lip = rounded_rect_profile(cx, cy, insole_w - wall*2 + SNAP_TOL*2,
                                insole_h - wall*2 + SNAP_TOL*2,
                                max(corner_r - wall, 8.0), segs)
    tris += extrude_profile(lip, split_z - 0.4, split_z)
    tris += fill_profile(lip, split_z, flip=False)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 21: Seed Bottle — Water bottle cap speaker
# ════════════════════════════════════════════════════════════════════

def generate_seed_bottle():
    """
    Seed Bottle: bottle cap speaker. 45mm diameter, 20mm height.
    Threads on inside to screw onto standard bottle necks (28mm thread).
    Speaker on top, PCB inside.
    """
    cap_r = 22.5       # 45mm / 2 outer
    cap_h = 20.0       # Total height
    wall = 2.0
    thread_r = 14.5    # 28mm bottle thread / 2 + clearance
    thread_depth = 10.0
    pcb_thick = 1.6
    standoff_h = 0.8

    segs = 96
    tris = []

    inner_r = cap_r - wall

    outer = circle_profile(0, 0, cap_r, segs)
    inner = circle_profile(0, 0, inner_r, segs)
    thread_inner = circle_profile(0, 0, thread_r, segs)

    # ── Main cap body ──
    # Outer wall
    tris += extrude_profile(outer, 0, cap_h)
    # Inner wall (only above thread area)
    for i in range(segs):
        j = (i + 1) % segs
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,thread_depth),(x2,y2,cap_h - wall),(x2,y2,thread_depth)))
        tris.append(make_tri((x1,y1,thread_depth),(x1,y1,cap_h - wall),(x2,y2,cap_h - wall)))

    # Top cap
    tris += fill_profile(outer, cap_h, flip=False)
    tris += ring_fill(outer, inner, cap_h - wall, flip=True)
    tris += fill_profile(inner, cap_h - wall, flip=True)

    # ── Thread area (bottom opening) ──
    # Open bottom with thread ridges
    tris += ring_fill(outer, thread_inner, 0, flip=True)

    # Thread inner wall
    for i in range(segs):
        j = (i + 1) % segs
        x1, y1 = thread_inner[i]; x2, y2 = thread_inner[j]
        tris.append(make_tri((x1,y1,0),(x2,y2,thread_depth),(x2,y2,0)))
        tris.append(make_tri((x1,y1,0),(x1,y1,thread_depth),(x2,y2,thread_depth)))

    # Thread-to-inner ring
    tris += ring_fill(inner, thread_inner, thread_depth, flip=False)

    # Thread ridges (simplified: raised rings inside thread area)
    for tz in [2.0, 5.0, 8.0]:
        ridge = circle_profile(0, 0, thread_r + 0.5, segs)
        tris += extrude_profile(ridge, tz, tz + 1.0)

    # PCB standoffs (above thread area)
    for angle_deg in [0, 120, 240]:
        a = math.radians(angle_deg)
        sx = 8.0 * math.cos(a)
        sy = 8.0 * math.sin(a)
        tris += standoff(sx, sy, thread_depth, standoff_h,
                         outer_r=1.2, inner_r=0.5, segs=12)

    # Speaker grille on top: concentric ring pattern
    for gr in [2.0, 5.0, 8.0]:
        for ga in range(0, 360, 30):
            gx = gr * math.cos(math.radians(ga))
            gy = gr * math.sin(math.radians(ga))
            tris = cutout_circle(tris, gx, gy, cap_h - wall - 0.1, cap_h + 0.1, 0.6)

    # LED window on top
    tris = cutout_circle(tris, 0.0, 0.0, cap_h - wall - 0.1, cap_h + 0.1, 1.2)

    # USB-C cutout on side
    usb_z = thread_depth + standoff_h + pcb_thick / 2 + 1.0
    tris = cutout_rect(tris, cap_r, 0, usb_z - 1.75, usb_z + 1.75, wall + 1.0, 9.5)

    # ── DOMINANT tripod retention legs extending downward from the cap ──
    # 3 curved legs that visibly reach below the cap to grip a bottle neck
    leg_len = 12.0
    leg_thick = 2.5
    for finger_ang in [30, 150, 270]:
        ar = math.radians(finger_ang)
        base_x = (thread_r + 1.0) * math.cos(ar)
        base_y = (thread_r + 1.0) * math.sin(ar)
        tip_x = (thread_r + 4.0) * math.cos(ar)
        tip_y = (thread_r + 4.0) * math.sin(ar)
        # Build leg as a swept rectangular cross-section descending
        leg_segs = 6
        prev = None
        for k in range(leg_segs + 1):
            t = k / leg_segs
            lx = base_x + (tip_x - base_x) * t
            ly = base_y + (tip_y - base_y) * t
            lz = -leg_len * t
            # Radial direction at this point
            rhat = (math.cos(ar), math.sin(ar))
            that = (-rhat[1], rhat[0])
            hw = leg_thick / 2
            ring = [
                (lx - that[0] * hw, ly - that[1] * hw, lz - hw),
                (lx + that[0] * hw, ly + that[1] * hw, lz - hw),
                (lx + that[0] * hw, ly + that[1] * hw, lz + hw),
                (lx - that[0] * hw, ly - that[1] * hw, lz + hw),
            ]
            if prev is not None:
                for ii in range(4):
                    jj = (ii + 1) % 4
                    tris.append(make_tri(prev[ii], prev[jj], ring[jj]))
                    tris.append(make_tri(prev[ii], ring[jj], ring[ii]))
            else:
                tris.append(make_tri(ring[0], ring[2], ring[1]))
                tris.append(make_tri(ring[0], ring[3], ring[2]))
            prev = ring
        if prev is not None:
            tris.append(make_tri(prev[0], prev[1], prev[2]))
            tris.append(make_tri(prev[0], prev[2], prev[3]))

    # Button on top for REC/Mode
    tris = cutout_circle(tris, 0.0, cap_r - 5.0,
                         cap_h - 1.0, cap_h + 0.1, 2.0)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 22: Seed Mic Clip — Microphone stand mount
# ════════════════════════════════════════════════════════════════════

def generate_seed_mic_clip():
    """
    Seed Mic Clip: clips onto 25mm microphone stands.
    PCB body with C-clamp for 25mm tube. Speaker faces outward.
    """
    # Lavalier mic clip — clamps onto a Ø3-4mm lavalier microphone
    clamp_inner_r = 1.75  # Lavalier mic Ø3.5mm / 2
    clamp_outer_r = 4.0
    clamp_gap = 3.0       # Opening gap for snap-on
    body_w = 25.0
    body_h = 10.0
    body_z = 8.0
    wall = 1.5
    corner_r = 4.0
    pcb_thick = 1.6
    standoff_h = 0.8

    segs = 24
    tris = []

    cx = body_w / 2
    cy = body_h / 2

    # ── PCB body ──
    split_z = body_z / 2

    outer = rounded_rect_profile(cx, cy, body_w, body_h, corner_r, segs)
    inner = rounded_rect_profile(cx, cy, body_w - wall*2, body_h - wall*2,
                                  max(corner_r - wall, 1.5), segs)

    # Bottom half
    tris += extrude_profile(outer, 0, split_z)
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    tris += fill_profile(outer, 0, flip=True)
    tris += ring_fill(outer, inner, wall, flip=False)
    tris += ring_fill(outer, inner, split_z, flip=False)

    # Top half
    top_z = split_z + 0.3
    tris += extrude_profile(outer, top_z, body_z)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,body_z - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,body_z - wall),(x2,y2,body_z - wall)))
    tris += fill_profile(outer, body_z, flip=False)
    tris += ring_fill(outer, inner, top_z, flip=True)
    tris += ring_fill(outer, inner, body_z - wall, flip=True)
    tris += fill_profile(inner, body_z - wall, flip=True)

    # PCB standoffs
    for angle_deg in [0, 120, 240]:
        a = math.radians(angle_deg)
        sx = cx + 8.0 * math.cos(a)
        sy = cy + 8.0 * math.sin(a)
        tris += standoff(sx, sy, wall, standoff_h, outer_r=1.2, inner_r=0.5, segs=12)

    # Speaker grille
    for gx in range(-1, 2):
        for gy in range(-1, 2):
            tris = cutout_circle(tris, cx + gx * 2.8, cy + gy * 2.8,
                                 body_z - wall - 0.1, body_z + 0.1, 0.6)

    # LED window
    tris = cutout_circle(tris, cx + 10.0, cy, body_z - wall - 0.1, body_z + 0.1, 0.8)

    # USB-C cutout
    usb_z = wall + standoff_h + pcb_thick / 2
    tris = cutout_rect(tris, body_w, cy, usb_z - 1.75, usb_z + 1.75, wall + 1.0, 9.5)

    # ── C-Clamp for mic stand (extends from left side) ──
    clamp_cx = -clamp_outer_r + 2.0  # Left of body
    clamp_cy = cy
    clamp_segs = 36

    # C-shape: 270 degrees of circle (open at top for snap-on)
    for i in range(int(clamp_segs * 0.75)):
        a1 = math.pi / 2 + 2 * math.pi * i / clamp_segs  # Start at top
        a2 = math.pi / 2 + 2 * math.pi * (i + 1) / clamp_segs

        ox1 = clamp_cx + clamp_outer_r * math.cos(a1)
        oy1 = clamp_cy + clamp_outer_r * math.sin(a1)
        ox2 = clamp_cx + clamp_outer_r * math.cos(a2)
        oy2 = clamp_cy + clamp_outer_r * math.sin(a2)
        ix1 = clamp_cx + clamp_inner_r * math.cos(a1)
        iy1 = clamp_cy + clamp_inner_r * math.sin(a1)
        ix2 = clamp_cx + clamp_inner_r * math.cos(a2)
        iy2 = clamp_cy + clamp_inner_r * math.sin(a2)

        z0 = split_z - 4.0
        z1 = split_z + 4.0

        # Outer surface
        tris.append(make_tri((ox1,oy1,z0),(ox2,oy2,z0),(ox2,oy2,z1)))
        tris.append(make_tri((ox1,oy1,z0),(ox2,oy2,z1),(ox1,oy1,z1)))
        # Inner surface
        tris.append(make_tri((ix1,iy1,z0),(ix2,iy2,z1),(ix2,iy2,z0)))
        tris.append(make_tri((ix1,iy1,z0),(ix1,iy1,z1),(ix2,iy2,z1)))
        # Top face
        tris.append(make_tri((ox1,oy1,z1),(ox2,oy2,z1),(ix2,iy2,z1)))
        tris.append(make_tri((ox1,oy1,z1),(ix2,iy2,z1),(ix1,iy1,z1)))
        # Bottom face
        tris.append(make_tri((ox1,oy1,z0),(ix2,iy2,z0),(ox2,oy2,z0)))
        tris.append(make_tri((ox1,oy1,z0),(ix1,iy1,z0),(ix2,iy2,z0)))

    # Snap-fit lip
    lip = rounded_rect_profile(cx, cy, body_w - wall*2 + SNAP_TOL*2,
                                body_h - wall*2 + SNAP_TOL*2,
                                max(corner_r - wall, 1.5), segs)
    tris += extrude_profile(lip, split_z - 0.8, split_z)
    tris += fill_profile(lip, split_z, flip=False)

    # ── Alligator clip on opposite side (for clothing) ──
    gator_cx = body_w + 4.0
    gator_cy = cy
    gator_arm = rect_profile(gator_cx, gator_cy, 2.0, 15.0)
    tris += extrude_profile(gator_arm, split_z - 0.8, split_z + 0.8)
    tris += fill_profile(gator_arm, split_z - 0.8, flip=True)
    tris += fill_profile(gator_arm, split_z + 0.8, flip=False)
    # Small opposing tooth
    tooth_profile = rect_profile(gator_cx + 1.5, gator_cy - 7.0, 2.0, 2.0)
    tris += extrude_profile(tooth_profile, split_z - 2.0, split_z + 2.0)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 23: Seed Pedalboard — Guitar effects pedal enclosure
# ════════════════════════════════════════════════════════════════════

def generate_seed_pedalboard():
    """
    Seed Pedalboard: dramatic wedge silhouette. A 80×50 footprint with
    a visibly trapezoidal side profile — front 12mm, back 28mm tall.
    Two big raised footswitch domes (Ø18) and visible 1/4" jack barrels
    protruding from the right side.
    """
    import math as _m
    tris = []

    pw = 80.0          # Width (X)
    pd = 50.0          # Depth (Y)
    front_z = 12.0     # Front edge height
    back_z = 28.0      # Back edge height — steeper slope
    corner_r = 4.0

    cx, cy = pw / 2, pd / 2

    def top_z_at(y):
        """Interpolate top height from front (y=0) to back (y=pd)."""
        return front_z + (back_z - front_z) * (y / pd)

    # Build the shell as 6 solid faces of a wedge box.
    segs_per_corner = 8
    outer = rounded_rect_profile(cx, cy, pw, pd, corner_r, segs_per_corner)
    n = len(outer)

    # Bottom plate
    tris += fill_profile(outer, 0.0, flip=True)
    # Outer slanted wall
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = outer[i]
        x2, y2 = outer[j]
        z1 = top_z_at(y1)
        z2 = top_z_at(y2)
        tris.append(make_tri((x1, y1, 0.0), (x2, y2, 0.0), (x2, y2, z2)))
        tris.append(make_tri((x1, y1, 0.0), (x2, y2, z2), (x1, y1, z1)))
    # Sloped top face — fan triangulation from the back-top centroid
    # Use triangle strip from each outer edge to a center point
    top_center = (cx, cy, top_z_at(cy))
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = outer[i]
        x2, y2 = outer[j]
        p1 = (x1, y1, top_z_at(y1))
        p2 = (x2, y2, top_z_at(y2))
        tris.append(make_tri(top_center, p1, p2))

    # ── Two big raised footswitch domes on top ──
    fs_r = 9.0         # Footswitch cap radius (Ø18mm)
    fs_height_above = 4.0  # Dome height above top face
    for fs_x in [cx - 18.0, cx + 18.0]:
        fs_y = cy - 4.0  # Slightly forward
        base_z = top_z_at(fs_y)
        # Cylindrical button body
        fs_segs = 32
        base_profile = circle_profile(fs_x, fs_y, fs_r, fs_segs)
        tris += extrude_profile(base_profile, base_z, base_z + fs_height_above)
        # Domed top (shrinking rings)
        rings = 10
        prev_ring = base_profile
        prev_z = base_z + fs_height_above
        for r in range(1, rings + 1):
            t = r / rings
            curr_r = fs_r * _m.sqrt(max(0.0, 1.0 - t * t))  # hemisphere
            curr_z = base_z + fs_height_above + fs_r * 0.4 * t  # flatter dome
            curr_ring = circle_profile(fs_x, fs_y, curr_r, fs_segs)
            for ii in range(fs_segs):
                jj = (ii + 1) % fs_segs
                p1 = (*prev_ring[ii], prev_z)
                p2 = (*prev_ring[jj], prev_z)
                p3 = (*curr_ring[ii], curr_z)
                p4 = (*curr_ring[jj], curr_z)
                tris.append(make_tri(p1, p2, p4))
                tris.append(make_tri(p1, p4, p3))
            prev_ring = curr_ring
            prev_z = curr_z
        tris += fill_profile(prev_ring, prev_z, flip=False)
        # Small LED window next to button
        tris = cutout_circle(tris, fs_x, fs_y + 13.0,
                             top_z_at(fs_y + 13.0) - 0.6,
                             top_z_at(fs_y + 13.0) + 0.1, 1.2)

    # ── Two 1/4" jack barrels protruding from right side (X=pw) ──
    jack_barrel_r = 6.0
    jack_hole_r = 4.75
    jack_stick = 4.0   # Protrusion length
    for dy in [-12.0, 12.0]:
        jy = cy + dy
        jz = 10.0      # Jack centerline z
        # Barrel = horizontal cylinder along +X
        jb_segs = 24
        for i in range(jb_segs):
            a1 = 2 * _m.pi * i / jb_segs
            a2 = 2 * _m.pi * (i + 1) / jb_segs
            p1 = (pw - 1.0, jy + jack_barrel_r * _m.cos(a1), jz + jack_barrel_r * _m.sin(a1))
            p2 = (pw - 1.0, jy + jack_barrel_r * _m.cos(a2), jz + jack_barrel_r * _m.sin(a2))
            p3 = (pw + jack_stick, jy + jack_barrel_r * _m.cos(a1), jz + jack_barrel_r * _m.sin(a1))
            p4 = (pw + jack_stick, jy + jack_barrel_r * _m.cos(a2), jz + jack_barrel_r * _m.sin(a2))
            tris.append(make_tri(p1, p2, p4))
            tris.append(make_tri(p1, p4, p3))
            # End cap at outer end (a ring -> center)
            center_o = (pw + jack_stick, jy, jz)
            tris.append(make_tri(p3, p4, center_o))
        # Dark recess for the jack hole (on the outer face)
        for i in range(16):
            a1 = 2 * _m.pi * i / 16
            a2 = 2 * _m.pi * (i + 1) / 16
            p1 = (pw + jack_stick + 0.01, jy + jack_hole_r * _m.cos(a1), jz + jack_hole_r * _m.sin(a1))
            p2 = (pw + jack_stick + 0.01, jy + jack_hole_r * _m.cos(a2), jz + jack_hole_r * _m.sin(a2))
            center_hole = (pw + jack_stick + 0.01, jy, jz)
            tris.append(make_tri(p2, p1, center_hole))

    # Rubber foot recesses on bottom (4 corners)
    for fx, fy in [(10, 10), (pw - 10, 10), (10, pd - 10), (pw - 10, pd - 10)]:
        tris = cutout_circle(tris, fx, fy, -0.1, 1.0, 3.5)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 24: Seed Amp — Desktop mini amplifier cube
# ════════════════════════════════════════════════════════════════════

def generate_seed_amp():
    """
    Seed Amp: trapezoidal guitar amp silhouette. Front (high, X=0) angles
    into a slanted top that faces up+toward the camera at default view.
    Speaker grille sits on the +X (right) face — visible from default azim=35.
    Two big knobs on the top-front edge.
    """
    import math as _m
    tris = []

    aw = 50.0          # width  (X axis)  — the +X face gets the speaker
    ad = 50.0          # depth  (Y axis)
    total_z = 48.0
    speaker_r = 18.0
    knob_r = 4.5

    # Build a "classic amp" silhouette: rectangular box, but with the
    # top-FRONT edge chamfered back (like a Fender Champ cabinet).
    # Front = +Y face (visible at default view).
    # Orient: the +Y face is a trapezoid, full-height at the back, chamfered at front-top.
    # Actually: make BOTH +X and +Y visible features.
    # Easier plan: solid box + huge ring-cylinder speaker on +Y face.

    # Main body = rectangular box at (0..aw, 0..ad, 0..total_z)
    # 6 faces
    def box():
        out = []
        # Bottom (z=0, facing -z)
        out.append(make_tri((0,0,0),(aw,0,0),(aw,ad,0)))
        out.append(make_tri((0,0,0),(aw,ad,0),(0,ad,0)))
        # Top (z=total_z, facing +z)
        out.append(make_tri((0,0,total_z),(aw,ad,total_z),(aw,0,total_z)))
        out.append(make_tri((0,0,total_z),(0,ad,total_z),(aw,ad,total_z)))
        # +Y face (front): we'll put the speaker here
        out.append(make_tri((0,ad,0),(aw,ad,0),(aw,ad,total_z)))
        out.append(make_tri((0,ad,0),(aw,ad,total_z),(0,ad,total_z)))
        # -Y face (back)
        out.append(make_tri((0,0,0),(0,0,total_z),(aw,0,total_z)))
        out.append(make_tri((0,0,0),(aw,0,total_z),(aw,0,0)))
        # -X face (left)
        out.append(make_tri((0,0,0),(0,ad,0),(0,ad,total_z)))
        out.append(make_tri((0,0,0),(0,ad,total_z),(0,0,total_z)))
        # +X face (right)
        out.append(make_tri((aw,0,0),(aw,0,total_z),(aw,ad,total_z)))
        out.append(make_tri((aw,0,0),(aw,ad,total_z),(aw,ad,0)))
        return out
    tris += box()

    # ── Sloping top-front chamfer: make the top face tilt toward the viewer ──
    # Cut a wedge off the top-front edge by slicing off a ramp.
    # We do a simpler approach: add a big sloping raised PANEL on top-front.
    # But a simpler route: add a raised "control panel" ramp on top.

    # ── Big circular speaker grille on +Y face ──
    face_cx = aw / 2
    face_cz = total_z * 0.4
    # Raised grille ring (outer ring) — sticks 1mm proud of the front face
    ring_segs = 48
    r_o = speaker_r + 2.0
    r_i = speaker_r + 0.8
    y_face = ad
    for i in range(ring_segs):
        a1 = 2 * _m.pi * i / ring_segs
        a2 = 2 * _m.pi * (i + 1) / ring_segs
        # Outer ring — raised ring cylinder: outer surface
        po1 = (face_cx + r_o * _m.cos(a1), y_face + 1.0, face_cz + r_o * _m.sin(a1))
        po2 = (face_cx + r_o * _m.cos(a2), y_face + 1.0, face_cz + r_o * _m.sin(a2))
        pob1 = (face_cx + r_o * _m.cos(a1), y_face, face_cz + r_o * _m.sin(a1))
        pob2 = (face_cx + r_o * _m.cos(a2), y_face, face_cz + r_o * _m.sin(a2))
        # Side walls (outer face)
        tris.append(make_tri(pob1, pob2, po2))
        tris.append(make_tri(pob1, po2, po1))
        # Top ring (facing camera)
        pi1 = (face_cx + r_i * _m.cos(a1), y_face + 1.0, face_cz + r_i * _m.sin(a1))
        pi2 = (face_cx + r_i * _m.cos(a2), y_face + 1.0, face_cz + r_i * _m.sin(a2))
        tris.append(make_tri(po1, po2, pi2))
        tris.append(make_tri(po1, pi2, pi1))
        # Inner side wall
        pib1 = (face_cx + r_i * _m.cos(a1), y_face, face_cz + r_i * _m.sin(a1))
        pib2 = (face_cx + r_i * _m.cos(a2), y_face, face_cz + r_i * _m.sin(a2))
        tris.append(make_tri(pi1, pi2, pib2))
        tris.append(make_tri(pi1, pib2, pib1))

    # Honeycomb holes inside the speaker ring (on +Y face)
    holes = honeycomb_speaker_grille(face_cx, face_cz, 0, 0, speaker_r - 1,
                                     hole_r=1.0, spacing=2.5)
    for hx, hz in holes:
        kept = []
        for tri in tris:
            _, (v1, v2, v3) = tri
            mx = (v1[0] + v2[0] + v3[0]) / 3
            my = (v1[1] + v2[1] + v3[1]) / 3
            mz = (v1[2] + v2[2] + v3[2]) / 3
            d = _m.sqrt((mx - hx) ** 2 + (mz - hz) ** 2)
            if d < 1.0 and my > ad - 0.5:
                continue
            kept.append(tri)
        tris = kept

    # ── Two big knob bosses on TOP face, near the front edge ──
    for kx in [aw * 0.3, aw * 0.7]:
        ky = ad - 8.0  # near the front edge, visible in top view
        knob_segs = 24
        base_z = total_z
        top_boss_z = total_z + 4.0
        for i in range(knob_segs):
            a1 = 2 * _m.pi * i / knob_segs
            a2 = 2 * _m.pi * (i + 1) / knob_segs
            p1 = (kx + knob_r * _m.cos(a1), ky + knob_r * _m.sin(a1), base_z)
            p2 = (kx + knob_r * _m.cos(a2), ky + knob_r * _m.sin(a2), base_z)
            p3 = (kx + knob_r * _m.cos(a1), ky + knob_r * _m.sin(a1), top_boss_z)
            p4 = (kx + knob_r * _m.cos(a2), ky + knob_r * _m.sin(a2), top_boss_z)
            tris.append(make_tri(p1, p2, p4))
            tris.append(make_tri(p1, p4, p3))
            tris.append(make_tri(p3, p4, (kx, ky, top_boss_z)))
        # Knob flat top (facing up)
        # (already covered by fan triangles above)

    # Power LED cavity (small dot) on +Y face
    tris = cutout_circle(tris, aw - 4.0, ad + 0.2, total_z - 4.0, total_z - 2.0, 0.8)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 25: Seed Ball — Omnidirectional spherical speaker
# ════════════════════════════════════════════════════════════════════

def generate_seed_ball():
    """
    Seed Ball: 40mm sphere. Omnidirectional sound. Roll-proof
    with small flat spot on bottom. Speaker holes across surface.
    """
    ball_r = 20.0      # 40mm / 2
    wall = 1.5
    flat_r = 8.0       # Flat spot radius on bottom
    pcb_thick = 1.6

    lat_segs = 48      # High-res latitude segments
    lon_segs = 64      # High-res longitude segments
    tris = []

    # Generate sphere using lat/lon grid
    def sphere_point(lat, lon, r):
        y = r * math.sin(lat)
        xz_r = r * math.cos(lat)
        x = xz_r * math.cos(lon)
        z = xz_r * math.sin(lon)
        return (x, y, z)

    # ── Outer sphere (with flat bottom) ──
    for i in range(lat_segs):
        lat1 = -math.pi/2 + math.pi * i / lat_segs
        lat2 = -math.pi/2 + math.pi * (i + 1) / lat_segs
        for j in range(lon_segs):
            lon1 = 2 * math.pi * j / lon_segs
            lon2 = 2 * math.pi * (j + 1) / lon_segs

            p1 = sphere_point(lat1, lon1, ball_r)
            p2 = sphere_point(lat1, lon2, ball_r)
            p3 = sphere_point(lat2, lon1, ball_r)
            p4 = sphere_point(lat2, lon2, ball_r)

            # Flatten bottom (below certain latitude)
            def flatten(p):
                if p[1] < -ball_r + 3.0:
                    return (p[0], -ball_r + 3.0, p[2])
                return p

            p1, p2, p3, p4 = flatten(p1), flatten(p2), flatten(p3), flatten(p4)

            tris.append(make_tri(p1, p3, p2))
            tris.append(make_tri(p2, p3, p4))

    # ── Inner sphere ──
    inner_r = ball_r - wall
    for i in range(lat_segs):
        lat1 = -math.pi/2 + math.pi * i / lat_segs
        lat2 = -math.pi/2 + math.pi * (i + 1) / lat_segs
        for j in range(lon_segs):
            lon1 = 2 * math.pi * j / lon_segs
            lon2 = 2 * math.pi * (j + 1) / lon_segs

            p1 = sphere_point(lat1, lon1, inner_r)
            p2 = sphere_point(lat1, lon2, inner_r)
            p3 = sphere_point(lat2, lon1, inner_r)
            p4 = sphere_point(lat2, lon2, inner_r)

            def flatten_inner(p):
                if p[1] < -inner_r + 3.0:
                    return (p[0], -inner_r + 3.0, p[2])
                return p

            p1, p2, p3, p4 = flatten_inner(p1), flatten_inner(p2), flatten_inner(p3), flatten_inner(p4)

            # Reversed winding for inner surface
            tris.append(make_tri(p1, p2, p3))
            tris.append(make_tri(p2, p4, p3))

    # Speaker holes (distributed across upper hemisphere)
    for lat_i in range(3, lat_segs - 2):
        lat = -math.pi/2 + math.pi * lat_i / lat_segs
        if lat < -0.3:  # Skip bottom area
            continue
        n_holes = max(4, int(lon_segs * math.cos(lat) * 0.5))
        for lon_i in range(n_holes):
            lon = 2 * math.pi * lon_i / n_holes
            hx = ball_r * math.cos(lat) * math.cos(lon)
            hy = ball_r * math.sin(lat)
            hz = ball_r * math.cos(lat) * math.sin(lon)
            # Cutout approximation using sphere-surface circle removal
            tris = cutout_circle(tris, hx, hz, hy - 0.8, hy + 0.8, 0.6)

    # USB-C cutout at equator
    tris = cutout_rect(tris, ball_r, 0, -1.75, 1.75, wall + 1.0, 9.5)

    # LED window at top
    tris = cutout_circle(tris, 0.0, 0.0, ball_r - wall - 0.1, ball_r + 0.1, 1.5)

    # ── 4 grouped honeycomb speaker grille areas around the equator ──
    # Each is a cluster of 5 holes on the surface
    for eq_ang in [math.pi / 4, 3 * math.pi / 4, 5 * math.pi / 4, 7 * math.pi / 4]:
        ex = ball_r * math.cos(eq_ang)
        ez = ball_r * math.sin(eq_ang)
        for dy, dxy in [(0, 0), (2.5, 0), (-2.5, 0), (0, 2.5), (0, -2.5)]:
            tris = cutout_circle(tris, ex * 0.95 + dxy, ez * 0.95, dy - 0.6, dy + 0.6, 0.5)

    # ── Top grille cluster (pointing up) ──
    for dr_ang in [0, 60, 120, 180, 240, 300]:
        a = math.radians(dr_ang)
        gx = 3.0 * math.cos(a)
        gz = 3.0 * math.sin(a)
        tris = cutout_circle(tris, gx, gz, ball_r - 1.0, ball_r + 0.1, 0.5)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 26: Seed Card — Credit card sized ultra-thin speaker
# ════════════════════════════════════════════════════════════════════

def generate_seed_card():
    """
    Card — Credit card size, 85x54x4mm. Fits in a wallet.
    Edge-firing thin speaker slot. 4mm thin with speaker.
    The thinnest possible case that still has audio output.
    """
    card_w = 85.0
    card_h = 54.0
    card_z = 2.8       # 2.8mm — more realistic wallet card thickness
    wall = 0.5
    corner_r = 3.0     # Standard card corner radius
    pcb_thick = 1.0

    segs = 24
    tris = []

    cx, cy = card_w / 2, card_h / 2
    split_z = card_z / 2

    outer = rounded_rect_profile(cx, cy, card_w, card_h, corner_r, segs)
    inner = rounded_rect_profile(cx, cy, card_w - wall*2, card_h - wall*2,
                                  max(corner_r - wall, 1.0), segs)

    # ── Bottom half ──
    tris += extrude_profile(outer, 0, split_z)
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    tris += fill_profile(outer, 0, flip=True)
    tris += ring_fill(outer, inner, wall, flip=False)
    tris += ring_fill(outer, inner, split_z, flip=False)

    # ── Top half ──
    top_z = split_z + 0.15
    tris += extrude_profile(outer, top_z, card_z)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,card_z - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,card_z - wall),(x2,y2,card_z - wall)))
    tris += fill_profile(outer, card_z, flip=False)
    tris += ring_fill(outer, inner, top_z, flip=True)
    tris += ring_fill(outer, inner, card_z - wall, flip=True)
    tris += fill_profile(inner, card_z - wall, flip=True)

    # No standoffs — press-fit

    # Edge-firing speaker: 2mm wide × 15mm long slit on the short edge
    tris = cutout_rect(tris, 0.0, cy, split_z - 1.0, split_z + 1.0, wall + 0.5, 15.0)

    # LED window
    tris = cutout_circle(tris, card_w - 6.0, card_h - 6.0,
                         card_z - wall - 0.1, card_z + 0.1, 0.5)

    # USB-C card-edge: 1mm deep × 9mm wide flat contact area on opposite short edge
    tris = cutout_rect(tris, card_w, cy, card_z - 1.0, card_z + 0.1, wall + 0.5, 9.0)

    # Snap-fit lip
    lip = rounded_rect_profile(cx, cy, card_w - wall*2 + SNAP_TOL*2,
                                card_h - wall*2 + SNAP_TOL*2,
                                max(corner_r - wall, 1.0), segs)
    tris += extrude_profile(lip, split_z - 0.3, split_z)
    tris += fill_profile(lip, split_z, flip=False)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case 27: Seed Figurine — Collectible figure display base
# ════════════════════════════════════════════════════════════════════

def generate_seed_figurine():
    """
    Seed Figurine: tall totem/chess-piece silhouette. 35mm base × 70mm tall.
    Stepped profile: base Ø35 → neck Ø20 → head Ø28.
    Face recess on head, LED ring around bottom edge.
    """
    base_r = 17.5      # 35mm / 2
    neck_r = 10.0      # 20mm / 2
    head_r = 14.0      # 28mm / 2
    base_h = 70.0      # Total height — actually TALL
    wall = 1.5
    figure_hole_r = 2.5
    pcb_thick = 1.6
    standoff_h = 0.8

    segs = 96
    tris = []

    inner_r = base_r - wall
    split_z = base_h / 2

    # Stepped profile: base (0 → 20mm, r=base_r),
    #                  neck (20 → 45mm, r=neck_r),
    #                  head (45 → 70mm, r=head_r)
    base_end_z = 20.0
    neck_end_z = 45.0
    head_end_z = base_h

    base_out = circle_profile(0, 0, base_r, segs)
    neck_out = circle_profile(0, 0, neck_r, segs)
    head_out = circle_profile(0, 0, head_r, segs)

    # Base section (tall cylinder)
    tris += extrude_profile(base_out, 0, base_end_z)
    tris += fill_profile(base_out, 0, flip=True)

    # Step transition: base top → neck bottom
    tris += ring_fill(base_out, neck_out, base_end_z, flip=False)

    # Neck section
    tris += extrude_profile(neck_out, base_end_z, neck_end_z)

    # Step transition: neck top → head bottom (shoulders)
    tris += ring_fill(head_out, neck_out, neck_end_z, flip=True)

    # Head section
    tris += extrude_profile(head_out, neck_end_z, head_end_z)
    tris += fill_profile(head_out, head_end_z, flip=False)

    # ── Face recess on head (Ø15mm shallow pocket) ──
    tris = cutout_circle(tris, 0.0, head_r - 2.0, head_end_z - 1.5, head_end_z + 0.1, 7.5)

    # ── LED ring crescent pattern around base bottom edge ──
    for angle_deg in range(0, 360, 20):
        a = math.radians(angle_deg)
        lx = (base_r - 1.0) * math.cos(a)
        ly = (base_r - 1.0) * math.sin(a)
        tris = cutout_circle(tris, lx, ly, 1.5, 3.5, 0.6)

    # Speaker grille on the base side (radial slits)
    for angle_deg in range(0, 360, 30):
        a = math.radians(angle_deg)
        gx = base_r * math.cos(a)
        gy = base_r * math.sin(a)
        tris = cutout_rect(tris, gx, gy, 8.0, 16.0, wall + 1.0, 1.2)

    # USB-C cutout on the base
    tris = cutout_rect(tris, base_r, 0, 5.0, 8.0, wall + 1.0, 9.5)

    return tris


# ── Main ──────────────────────────────────────────────────────────

# ════════════════════════════════════════════════════════════════════
# Case: Seed Outdoor Extreme — 38mm, -30°C rated, IP67
# ════════════════════════════════════════════════════════════════════
# Enlarged case for extreme cold environments (ski resorts, arctic festivals).
# PA12 nylon (not resin — resin shatters below -10°C).
# Features: carabiner loop, IP67 gasket groove, recessed USB-C with flap,
#           water-shedding angled speaker grille, anti-slip knurl texture.
# PCB: same COIN Lite Ø28mm (with component swaps for -30°C).
# Battery: larger low-temp LiPo (Grepow 600mAh, -40°C discharge rated).

def generate_seed_outdoor():
    """
    Seed Outdoor Extreme case: Ø38mm, 15mm tall, IP67 sealed.
    Two-piece snap-fit with gasket groove for silicone O-ring.
    Thicker walls (2.5mm) for thermal insulation.
    Carabiner loop at top, recessed USB-C port, angled speaker grille.
    Print in PA12 nylon (MJF/SLS) for cold impact resistance.
    """
    # Dimensions
    pcb_r = 14.0                        # Ø28mm PCB
    wall = 2.5                          # Thicker wall for thermal insulation
    case_r = 19.0                       # 38mm diameter / 2
    inner_r = case_r - wall             # 16.5mm
    pcb_thick = 1.6
    battery_h = 3.0                     # Thin low-temp LiPo (wider, thinner cell)
    standoff_h = 1.5
    speaker_h = 3.0
    clearance_top = 2.0
    gasket_groove_w = 1.2               # O-ring groove width
    gasket_groove_d = 0.8               # O-ring groove depth

    total_h = 15.0                      # Fixed total height
    split_z = wall + battery_h + standoff_h + pcb_thick + 1.0  # ~9.6mm

    segs = 192                          # Ultra-smooth outdoor finish

    tris = []

    outer = circle_profile(0, 0, case_r, segs)
    inner = circle_profile(0, 0, inner_r, segs)

    # ── Bottom half (0 to split_z) ──
    # Outer wall
    tris += extrude_profile(outer, 0, split_z)
    # Inner wall
    for i in range(segs):
        j = (i + 1) % segs
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,wall),(x2,y2,split_z),(x2,y2,wall)))
        tris.append(make_tri((x1,y1,wall),(x1,y1,split_z),(x2,y2,split_z)))
    # Bottom floor
    tris += fill_profile(outer, 0, flip=True)
    # Bottom ring (outer to inner at z=wall)
    tris += ring_fill(outer, inner, wall, flip=False)
    # Top ring at split
    tris += ring_fill(outer, inner, split_z, flip=False)

    # PCB standoffs (4 posts, 90° apart, at r=11mm)
    for angle in [0, math.pi/2, math.pi, 3*math.pi/2]:
        sx = 11.0 * math.cos(angle)
        sy = 11.0 * math.sin(angle)
        tris += standoff(sx, sy, wall, standoff_h + battery_h)

    # USB-C cutout: recessed 3mm into case wall, 9.0 x 3.5mm
    usb_cx = 0.0
    usb_cy = -case_r
    usb_z_center = wall + battery_h + standoff_h + pcb_thick / 2
    tris = cutout_rect(tris, usb_cx, usb_cy, usb_z_center - 2.0, usb_z_center + 2.0, 9.5, wall + 1.0)

    # USB-C recess cavity (3mm deep pocket around the port opening)
    recess_w, recess_h, recess_d = 12.0, 5.0, 3.0
    recess_profile = rect_profile(usb_cx, -case_r + recess_d/2, recess_w, recess_d)
    tris += extrude_profile(recess_profile, usb_z_center - 2.5, usb_z_center + 2.5, close=True)

    # Button cutout: recessed 1.5mm, 5mm diameter at right side
    btn_cx = case_r
    btn_cy = 0.0
    btn_z = wall + battery_h + standoff_h + pcb_thick / 2
    tris = cutout_circle(tris, btn_cx, btn_cy, btn_z - 2.5, btn_z + 2.5, 2.5)

    # Button recess ring (1.5mm deep, 5mm diameter visible opening)
    btn_recess = circle_profile(case_r - 1.5, 0.0, 3.0, 24)
    tris += extrude_profile(btn_recess, btn_z - 2.5, btn_z + 2.5, close=True)

    # ── Gasket groove at split line (bottom half top edge) ──
    gasket_outer = circle_profile(0, 0, inner_r, segs)
    gasket_inner = circle_profile(0, 0, inner_r - gasket_groove_w, segs)
    # Cut groove into the top rim of bottom half
    tris += extrude_profile(gasket_inner, split_z - gasket_groove_d, split_z)

    # ── Top half (separate piece, split_z to total_h) ──
    top_z = split_z + 0.4  # Tight gap for IP67
    tris += extrude_profile(outer, top_z, total_h)
    # Inner wall of top
    for i in range(segs):
        j = (i + 1) % segs
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1,y1,top_z),(x2,y2,total_h - wall),(x2,y2,top_z)))
        tris.append(make_tri((x1,y1,top_z),(x1,y1,total_h - wall),(x2,y2,total_h - wall)))
    # Top cap
    tris += fill_profile(outer, total_h, flip=False)
    # Rings
    tris += ring_fill(outer, inner, top_z, flip=True)
    tris += ring_fill(outer, inner, total_h - wall, flip=True)
    # Inner top floor (under the cap)
    tris += fill_profile(inner, total_h - wall, flip=True)

    # Speaker grille: angled holes (15° water-shedding), 4x3 grid, 1.5mm holes
    # Represented as cutout circles through top cap (angle is manufacturing note)
    for gx in range(-2, 3):
        for gy in range(-1, 2):
            # Offset slightly toward front for acoustic directivity
            tris = cutout_circle(tris, gx * 2.8, gy * 2.8 + 2.0,
                                 total_h - wall - 0.1, total_h + 0.1, 0.75)

    # LED window: 3mm hole at top (for APA102C cold-rated LED)
    tris = cutout_circle(tris, 0.0, 12.0, total_h - wall - 0.1, total_h + 0.1, 1.5)

    # ── Carabiner loop at top (Y=+case_r direction) ──
    # Loop: 8mm opening, 3mm thick walls, extends 6mm above case
    loop_cy = case_r + 3.0  # Center of loop ring
    loop_outer_r = 5.0
    loop_inner_r = 4.0
    loop_z_bot = total_h - 5.0  # Start from near top of case
    loop_z_top = total_h + 1.0  # Extend slightly above

    # Outer ring of carabiner loop
    loop_outer = circle_profile(0.0, loop_cy, loop_outer_r, 32)
    loop_inner_pts = circle_profile(0.0, loop_cy, loop_inner_r, 32)
    tris += make_shell(loop_outer, loop_inner_pts, loop_z_bot, loop_z_top)

    # Bridge from case body to loop
    bridge_profile = rect_profile(0.0, case_r + 1.0, 6.0, 4.0)
    tris += extrude_profile(bridge_profile, loop_z_bot, loop_z_top, close=True)
    tris += fill_profile(bridge_profile, loop_z_bot, flip=True)
    tris += fill_profile(bridge_profile, loop_z_top, flip=False)

    # ── Rugged diagonal rib grooves across the top face ──
    # 5 parallel grooves, each 1.2mm deep — cut into the top cap
    for groove_i in range(-2, 3):
        offset = groove_i * 5.0
        # Cut a narrow rectangular band across the top
        tris = cutout_rect(tris, offset * 0.7, offset * 0.7,
                           total_h - 1.3, total_h + 0.1,
                           case_r * 2, 1.4)

    # ── Prominent carabiner loop tab sticking out ──
    # Wide tab (16mm) with a visible 5mm through-hole
    tab_y = case_r + 5.0
    tab_half = 6.0  # Half width
    tab_x_base = 0.0
    tab_z_lo = total_h - 5.0
    tab_z_hi = total_h - 1.0
    # Tab as a flat rounded rectangle extruded in Z
    tab_profile = rounded_rect_profile(0.0, tab_y, 12.0, 8.0, 3.0, 16)
    tris += extrude_profile(tab_profile, tab_z_lo, tab_z_hi)
    tris += fill_profile(tab_profile, tab_z_lo, flip=True)
    tris += fill_profile(tab_profile, tab_z_hi, flip=False)
    # Through-hole
    tris = cutout_circle(tris, 0.0, tab_y, tab_z_lo - 0.2, tab_z_hi + 0.2, 2.5)

    # Snap-fit lip on bottom half (ridge at split_z) — tighter for IP67
    lip_r = inner_r + SNAP_TOL * 0.5  # Tighter interference for seal
    lip_profile = circle_profile(0, 0, lip_r, segs)
    tris += extrude_profile(lip_profile, split_z - 1.2, split_z)
    tris += fill_profile(lip_profile, split_z, flip=False)

    # "KOE" text indent on bottom (decorative, 0.3mm deep)
    tris = cutout_rect(tris, 0.0, 0.0, -0.1, 0.3, 10.0, 4.0)

    # ── 4x M2 corner screw bosses for extra IP68 compression ──
    for ang in [math.pi / 4, 3 * math.pi / 4, 5 * math.pi / 4, 7 * math.pi / 4]:
        bx = (case_r - 2.5) * math.cos(ang)
        by = (case_r - 2.5) * math.sin(ang)
        # Boss (internal)
        tris += standoff(bx, by, 0, split_z - 0.5,
                         outer_r=1.8, inner_r=1.0, segs=16)
        # Through-hole in top half
        tris = cutout_circle(tris, bx, by, top_z - 0.1, total_h + 0.1, 1.1)

    # ── Pressure equalization vent pocket (Gore-Tex membrane area) ──
    tris = cutout_circle(tris, -case_r + 3.5, 0.0, total_h - 1.0, total_h + 0.1, 1.5)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case: Seed Dot — Smallest possible Koe device (20mm x 5mm)
# ════════════════════════════════════════════════════════════════════
# No speaker, no battery. Just PCB + piezo + BLE beacon.
# Find My tracker only. Stick-on adhesive back.

def generate_seed_dot():
    """
    Dot — "The Seed"
    Literally a seed shape. Like a lentil or coffee bean.
    Plan: circle 20mm. Cross-section: lenticular (double convex).
    Center thickness: 4mm. Edge: razor-thin taper to 0.5mm.
    One tiny dimple on top (LED). Adhesive flat spot on bottom (3mm circle).
    The most minimal object possible — could be jewelry.
    """
    case_r = 10.0           # 20mm diameter
    wall = 0.6              # Thinner walls for seed-like thinness
    center_h = 4.0          # Center thickness
    edge_h = 0.5            # Razor-thin edge
    pcb_thick = 1.0

    segs = 192
    tris = []

    z_mid = center_h / 2    # Center plane
    top_rise = (center_h - edge_h) / 2
    bot_rise = (center_h - edge_h) / 2

    outer = circle_profile(0, 0, case_r, segs)
    inner = circle_profile(0, 0, case_r - wall, segs)

    # ── Top lenticular surface ──
    tris += make_dome_lenticular(outer, z_mid + edge_h / 2, top_rise, rings=40)

    # ── Bottom lenticular surface (inverted) ──
    bot_base = z_mid - edge_h / 2
    dome_rings = 40
    prev_ring = outer
    prev_z = bot_base
    for ri in range(1, dome_rings + 1):
        t = ri / dome_rings
        shrink = t * 0.95
        curr_ring = [(px * (1 - shrink), py * (1 - shrink)) for px, py in outer]
        curr_r = case_r * (1 - shrink)
        ring_z = bot_base - lenticular_z(curr_r, case_r, bot_rise)

        nr = len(prev_ring)
        nc = len(curr_ring)
        for i in range(max(nr, nc)):
            pi_i = i % nr; pj_i = (i + 1) % nr
            ci_i = i % nc; cj_i = (i + 1) % nc
            px1, py1 = prev_ring[pi_i]; px2, py2 = prev_ring[pj_i]
            cx1, cy1 = curr_ring[ci_i]; cx2, cy2 = curr_ring[cj_i]
            tris.append(make_tri(
                (px1, py1, prev_z), (cx2, cy2, ring_z), (cx1, cy1, ring_z)))
            tris.append(make_tri(
                (px1, py1, prev_z), (px2, py2, prev_z), (cx2, cy2, ring_z)))
        prev_ring = curr_ring
        prev_z = ring_z
    tris += fill_profile(prev_ring, prev_z, flip=True)

    # ── Razor-thin edge wall ──
    tris += extrude_profile(outer, bot_base, z_mid + edge_h / 2)

    # ── Inner cavity ──
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1, y1, wall), (x2, y2, center_h - wall), (x2, y2, wall)))
        tris.append(make_tri((x1, y1, wall), (x1, y1, center_h - wall), (x2, y2, center_h - wall)))
    tris += ring_fill(outer, inner, wall, flip=False)
    tris += ring_fill(outer, inner, center_h - wall, flip=True)
    tris += fill_profile(inner, wall, flip=True)
    tris += fill_profile(inner, center_h - wall, flip=False)

    # ── LED: tiny dimple at apex ──
    top_apex = z_mid + edge_h / 2 + top_rise
    tris = cutout_circle(tris, 0.0, 0.0, center_h - wall - 0.1, top_apex + 0.1, 0.4)

    # ── 3 LED pinpricks around the top dome ──
    for ang in [0, 120, 240]:
        ar = math.radians(ang)
        px = (case_r - 2.0) * math.cos(ar)
        py = (case_r - 2.0) * math.sin(ar)
        tris = cutout_circle(tris, px, py, center_h - wall - 0.1, top_apex + 0.1, 0.2)

    # ── Mic pinhole ──
    tris = cutout_circle(tris, 0.0, case_r * 0.4,
                         center_h - wall - 0.1, top_apex + 0.1, 0.3)

    # ── Wireless-charging coil recess on bottom (circular 8mm, 0.8mm deep) ──
    bot_apex = z_mid - edge_h / 2 - bot_rise
    tris = cutout_circle(tris, 0.0, 0.0, bot_apex - 0.1, bot_apex + 0.8, 4.0)

    # ── Tact button recess on edge ──
    tris = cutout_rect(tris, case_r - 0.3, 0.0,
                       z_mid - 0.7, z_mid + 0.7, 1.0, 2.5)

    # Snap-fit lip (hidden inside the thin edge)
    lip_profile = circle_profile(0, 0, case_r - wall + SNAP_TOL, segs)
    tris += extrude_profile(lip_profile, z_mid - 0.3, z_mid)
    tris += fill_profile(lip_profile, z_mid, flip=False)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case: nRF5340 Audio DK Case — "Koe Seed Developer Edition"
# ════════════════════════════════════════════════════════════════════
# Off-the-shelf nRF5340 Audio DK (approx 130x60x20mm) enclosed in a
# simple open-top box with cutouts for USB-C, 3.5mm audio, buttons,
# LEDs, and "Koe Seed" text indent. Rubber feet holes at corners.

def generate_dk_case():
    """
    nRF5340 Audio DK case — Premium redesign (Mac Mini / Apple TV aesthetic).
    DK dimensions approx 130x60x20mm -> case 135.6x65.6x24.5mm outer.
    Features: rounded corners (5mm radius), chamfered top edge, elegant ventilation
    slots, recessed logo area, rubber feet hemispheres, filleted connector cutouts.
    """
    dk_w, dk_h = 130.0, 60.0
    wall = 2.5
    dk_thick = 20.0
    corner_r = 5.0         # Rounded corners
    chamfer = 2.0          # Top edge chamfer
    segs_corner = 32       # Smooth corner arcs

    case_w = dk_w + PCB_TOL * 2 + wall * 2
    case_h = dk_h + PCB_TOL * 2 + wall * 2
    total_z = wall + dk_thick + 2.0

    cx, cy = case_w / 2, case_h / 2
    dk_ox = wall + PCB_TOL
    dk_oy = wall + PCB_TOL

    tris = []

    # Use rounded rectangle profiles instead of sharp rectangles
    outer = rounded_rect_profile(cx, cy, case_w, case_h, corner_r, segs_corner)
    inner = rounded_rect_profile(cx, cy, case_w - wall * 2, case_h - wall * 2,
                                  max(corner_r - wall, 1.0), segs_corner)

    # Chamfered top edge profile (slightly inset at top)
    outer_chamfer = rounded_rect_profile(cx, cy, case_w - chamfer * 2, case_h - chamfer * 2,
                                          max(corner_r - chamfer, 1.0), segs_corner)

    # ── Main box with rounded corners ──
    # Bottom plate
    tris += fill_profile(outer, 0, flip=True)
    # Outer walls (lower portion, full width)
    tris += extrude_profile(outer, 0, total_z - chamfer)
    # Chamfer band (outer transitions from full to inset)
    tris += ring_fill(outer, outer_chamfer, total_z - chamfer, flip=False)
    # Chamfer wall (short inset section at top)
    tris += extrude_profile(outer_chamfer, total_z - chamfer, total_z)

    # Inner walls
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1, y1, wall), (x2, y2, total_z), (x2, y2, wall)))
        tris.append(make_tri((x1, y1, wall), (x1, y1, total_z), (x2, y2, total_z)))

    # Bottom ring (floor inner ledge)
    tris += ring_fill(outer, inner, wall, flip=False)
    # Top ring (open top edge — using chamfered outer)
    tris += ring_fill(outer_chamfer, inner, total_z, flip=False)

    # PCB support standoffs (4 corners)
    for mx, my in [(5, 5), (125, 5), (5, 55), (125, 55)]:
        tris += standoff(dk_ox + mx, dk_oy + my, wall, 2.0,
                         outer_r=3.0, inner_r=1.1, segs=16)

    conn_z_lo = wall

    # ── USB-C cutout (front center, filleted by using slightly oversized rect) ──
    tris = cutout_rect(tris, cx, 0, conn_z_lo + 3.0, conn_z_lo + 10.0, 10.0, wall + 1.0)

    # ── 3.5mm audio jack cutouts (front, smooth circles) ──
    tris = cutout_circle(tris, dk_ox + 25, 0, conn_z_lo + 4.0, conn_z_lo + 11.0, 3.5)
    tris = cutout_circle(tris, dk_ox + 105, 0, conn_z_lo + 4.0, conn_z_lo + 11.0, 3.5)

    # ── Elegant ventilation slots on sides (parallel horizontal slots) ──
    # Right side: 6 narrow parallel slots instead of button holes
    slot_spacing = 6.0
    slot_start_x = 30.0
    for i in range(6):
        bx = slot_start_x + i * slot_spacing
        tris = cutout_rect(tris, dk_ox + bx, case_h, conn_z_lo + 9.0, conn_z_lo + 12.0,
                           3.5, wall + 1.0)

    # Left side: matching ventilation slots for symmetry
    for i in range(4):
        tris = cutout_rect(tris, 0, dk_oy + 12 + i * slot_spacing,
                           conn_z_lo + 6.0, conn_z_lo + 9.0, wall + 1.0, 3.0)

    # ── LED window (right wall, clean elongated slot) ──
    tris = cutout_rect(tris, case_w, dk_oy + 28, conn_z_lo + 6.0, conn_z_lo + 11.0,
                       wall + 1.0, 14.0)

    # ── Debug header slot (left side, narrower) ──
    tris = cutout_rect(tris, 0, cy, conn_z_lo + 3.0, conn_z_lo + 12.0, wall + 1.0, 18.0)

    # ── Recessed Koe logo area on top (oval indent, 0.5mm deep) ──
    logo_w, logo_h, logo_depth = 30.0, 12.0, 0.5
    logo_r = 6.0
    logo_profile = rounded_rect_profile(cx, cy, logo_w, logo_h, logo_r, 8)
    # Open-top box, so logo goes on the bottom (visible when flipped)
    tris += extrude_profile(logo_profile, -logo_depth, 0)
    tris += fill_profile(logo_profile, -logo_depth, flip=True)

    # ── Rubber feet hemispheres at 4 corners (small raised bumps on bottom) ──
    feet_r = 3.5
    feet_h = 1.2
    feet_segs = 32
    for fx, fy in [(12, 12), (case_w - 12, 12), (12, case_h - 12), (case_w - 12, case_h - 12)]:
        # Hemisphere approximated as a short cylinder with domed top
        foot_profile = circle_profile(fx, fy, feet_r, feet_segs)
        tris += extrude_profile(foot_profile, -feet_h, 0)
        tris += fill_profile(foot_profile, -feet_h, flip=True)

    # ── Top lid (separate piece, larger gap for visible seam) ──
    lid_h = 3.0
    lid_gap = 3.5  # Bigger visible air gap
    lid_z0 = total_z + lid_gap
    lid_z1 = lid_z0 + lid_h
    lid_profile = rounded_rect_profile(cx, cy, case_w - 0.4, case_h - 0.4,
                                       max(corner_r - 0.2, 1.0), segs_corner)
    tris += extrude_profile(lid_profile, lid_z0, lid_z1)
    tris += fill_profile(lid_profile, lid_z0, flip=True)
    tris += fill_profile(lid_profile, lid_z1, flip=False)

    # Large ventilation slots across the lid
    for i in range(6):
        sy = dk_oy + 10 + i * 9
        tris = cutout_rect(tris, cx, sy, lid_z0 - 0.1, lid_z1 + 0.1,
                           case_w * 0.7, 4.0)

    # M3 screw bosses at 4 corners (3.2mm clearance hole)
    for mx, my in [(8, 8), (case_w - 8, 8), (8, case_h - 8), (case_w - 8, case_h - 8)]:
        tris = cutout_circle(tris, mx, my, lid_z0 - 0.1, lid_z1 + 0.1, 1.6)
        # Boss inside the case for thread engagement
        tris += standoff(mx, my, wall, total_z - wall - 2.0,
                         outer_r=3.0, inner_r=1.25, segs=16)

    # Snap hooks on lid sides (visual feature) - small lip tabs
    for tab_x in [case_w * 0.25, case_w * 0.75]:
        tris = cutout_rect(tris, tab_x, cy, lid_z0 - 0.1, lid_z1 + 0.1, 8.0, 1.0)

    return tris


# ════════════════════════════════════════════════════════════════════
# Case: Seed Wristband Pod v2 — shallower biconvex with retention slots
# ════════════════════════════════════════════════════════════════════
# Separate from "The Lens" (seed-wristband-pod.stl) — this is for the
# sport category "Wristband Pod" button. Shallower, with lateral strap
# retention slots and visible charging contacts on the bottom.

def generate_seed_wristband_v2():
    """
    Wristband Pod v2 — for sport wristband.
    Shallower biconvex (center 5mm, edge 2mm), 32×22mm oval.
    2x lateral retention slots for silicone strap.
    Circular charging contact pads on bottom.
    """
    pod_a = 16.0            # semi-major
    pod_b = 11.0            # semi-minor
    center_thick = 5.0      # Shallower than The Lens
    edge_thick = 2.0
    wall = 0.8

    segs = 128
    tris = []

    cx, cy = 0, 0
    outer = superellipse_profile(cx, cy, pod_a, pod_b, n=2.4, segs=segs)
    inner = superellipse_profile(cx, cy, pod_a - wall, pod_b - wall, n=2.4, segs=segs)

    max_r = max(math.sqrt(p[0]**2 + p[1]**2) for p in outer)
    z_mid = center_thick / 2
    top_rise = (center_thick - edge_thick) / 2
    bot_rise = (center_thick - edge_thick) / 2

    # Top convex
    tris += make_dome_lenticular(outer, z_mid + edge_thick / 2, top_rise, rings=28)

    # Bottom convex (inverted)
    bot_base = z_mid - edge_thick / 2
    dome_rings = 28
    prev_ring = outer
    prev_z = bot_base
    for ri in range(1, dome_rings + 1):
        t = ri / dome_rings
        shrink = t * 0.95
        curr_ring = [(px * (1 - shrink), py * (1 - shrink)) for px, py in outer]
        curr_r = max_r * (1 - shrink)
        ring_z = bot_base - lenticular_z(curr_r, max_r, bot_rise)
        nr = len(prev_ring); nc = len(curr_ring)
        for i in range(max(nr, nc)):
            pi_i = i % nr; pj_i = (i + 1) % nr
            ci_i = i % nc; cj_i = (i + 1) % nc
            px1, py1 = prev_ring[pi_i]; px2, py2 = prev_ring[pj_i]
            cx1, cy1 = curr_ring[ci_i]; cx2, cy2 = curr_ring[cj_i]
            tris.append(make_tri((px1, py1, prev_z), (cx2, cy2, ring_z), (cx1, cy1, ring_z)))
            tris.append(make_tri((px1, py1, prev_z), (px2, py2, prev_z), (cx2, cy2, ring_z)))
        prev_ring = curr_ring
        prev_z = ring_z
    tris += fill_profile(prev_ring, prev_z, flip=True)

    # Edge wall
    tris += extrude_profile(outer, bot_base, z_mid + edge_thick / 2)

    # Inner cavity
    n = len(inner)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = inner[i]; x2, y2 = inner[j]
        tris.append(make_tri((x1, y1, wall + 0.3), (x2, y2, center_thick - wall - 0.3), (x2, y2, wall + 0.3)))
        tris.append(make_tri((x1, y1, wall + 0.3), (x1, y1, center_thick - wall - 0.3), (x2, y2, center_thick - wall - 0.3)))
    tris += ring_fill(outer, inner, wall + 0.3, flip=False)
    tris += ring_fill(outer, inner, center_thick - wall - 0.3, flip=True)
    tris += fill_profile(inner, wall + 0.3, flip=True)
    tris += fill_profile(inner, center_thick - wall - 0.3, flip=False)

    # ── 2x lateral retention slots for silicone strap ──
    # Wider/taller than The Lens's band channels
    tris = cutout_rect(tris, -pod_a, 0, z_mid - 2.0, z_mid + 2.0, wall + 1.5, 8.0)
    tris = cutout_rect(tris, pod_a, 0, z_mid - 2.0, z_mid + 2.0, wall + 1.5, 8.0)

    # ── Charging contacts on bottom (3 flat pad recesses) ──
    bot_apex = z_mid - edge_thick / 2 - bot_rise
    for pad_x in [-4.0, 0.0, 4.0]:
        tris = cutout_circle(tris, pad_x, 0.0, bot_apex + 0.05, bot_apex + 0.4, 1.2)

    # Speaker grille on top
    tris = apply_fibonacci_speaker(tris, 0.0, -3.0,
                                   center_thick - wall - 0.4, z_mid + edge_thick / 2 + top_rise + 0.1,
                                   grid_r=2.5, hole_r=0.3, n_holes=8)

    # Mic pinhole
    tris = cutout_circle(tris, 0.0, pod_b * 0.5,
                         center_thick - wall - 0.4, z_mid + edge_thick / 2 + top_rise + 0.1, 0.35)

    return tris


# ════════════════════════════════════════════════════════════════════
# Koe Stone Mini — Ø50mm pocket sibling
# ════════════════════════════════════════════════════════════════════

def generate_koe_mini_case():
    """
    Koe Stone Mini — Ø50 × 15mm pocket sibling of the Stone.
    ─────────────────────────────────────────────────────────
    Shares the superellipse n=3.5 language with the full Stone at smaller
    scale. CNC aluminum unibody, catenary dome, Qi wireless charge, NFC
    tag, single K-logo recess. Lanyard slot through the side for cord
    carry. ~90g target in 6061-T6.
    """
    # ── Outer dimensions ─────────────────────────────────────
    case_r       = 25.0     # Ø50mm diameter
    total_h      = 15.0     # Body height
    SUPER_N      = 3.5
    segs         = 160
    dome_h       = 1.5
    edge_fillet  = 1.0
    fillet_segs  = 10

    # ── Internal structure ───────────────────────────────────
    side_wall    = 1.2
    floor_t      = 2.5
    top_wall_t   = 1.2
    standoff_h   = 1.6
    standoff_or  = 1.3
    standoff_ir  = 0.65

    # ── Bottom-face features ─────────────────────────────────
    rad_a, rad_b = 12.5, 7.5     # Passive radiator 25×15
    qi_r         = 17.5          # Ø35 Qi coil
    qi_depth     = 1.0
    nfc_r        = 3.0           # Ø6 NFC tag
    nfc_depth    = 1.0
    nfc_cx, nfc_cy = 0.0, 15.0

    # ── Top K-logo recess ────────────────────────────────────
    logo_w, logo_h = 6.0, 6.0
    logo_depth     = 0.3

    tris = []

    outer = superellipse_profile(0, 0, case_r, case_r, n=SUPER_N, segs=segs)
    inner_scale = (case_r - side_wall - edge_fillet) / case_r
    inner = [(x * inner_scale, y * inner_scale) for x, y in outer]

    def _ring_quads(lower_ring, lower_z, upper_ring, upper_z):
        out = []
        nr = len(lower_ring)
        for i in range(nr):
            j = (i + 1) % nr
            px1, py1 = lower_ring[i]
            px2, py2 = lower_ring[j]
            cx1, cy1 = upper_ring[i]
            cx2, cy2 = upper_ring[j]
            out.append(make_tri((px1, py1, lower_z), (cx1, cy1, upper_z), (cx2, cy2, upper_z)))
            out.append(make_tri((px1, py1, lower_z), (cx2, cy2, upper_z), (px2, py2, lower_z)))
        return out

    # ── 1. Bottom fillet ring ───────────────────────────────
    bottom_fillet_base = [(x * (case_r - edge_fillet) / case_r,
                           y * (case_r - edge_fillet) / case_r) for x, y in outer]
    tris += fill_profile(bottom_fillet_base, 0.0, flip=True)
    prev_ring = bottom_fillet_base
    prev_z = 0.0
    for k in range(1, fillet_segs + 1):
        t = (math.pi / 2) * k / fillet_segs
        dr = edge_fillet * (1.0 - math.sin(t))
        dz = edge_fillet * (1.0 - math.cos(t))
        scale = (case_r - dr) / case_r
        curr_ring = [(x * scale, y * scale) for x, y in outer]
        curr_z = dz
        tris += _ring_quads(prev_ring, prev_z, curr_ring, curr_z)
        prev_ring = curr_ring
        prev_z = curr_z

    # ── 2. Vertical wall ────────────────────────────────────
    wall_z0 = edge_fillet
    wall_z1 = total_h - edge_fillet
    tris += extrude_profile(outer, wall_z0, wall_z1)

    # ── 3. Top fillet ring ──────────────────────────────────
    prev_ring = outer
    prev_z = wall_z1
    for k in range(1, fillet_segs + 1):
        t = (math.pi / 2) * k / fillet_segs
        dr = edge_fillet * (1.0 - math.cos(t))
        dz = edge_fillet * math.sin(t)
        scale = (case_r - dr) / case_r
        curr_ring = [(x * scale, y * scale) for x, y in outer]
        curr_z = wall_z1 + dz
        tris += _ring_quads(prev_ring, prev_z, curr_ring, curr_z)
        prev_ring = curr_ring
        prev_z = curr_z

    # ── 4. Catenary dome ────────────────────────────────────
    tris += make_dome_catenary(prev_ring, prev_z, dome_h, rings=28)
    dome_top = prev_z + dome_h

    # ── 5. Internal cavity ──────────────────────────────────
    cav_z0 = floor_t
    cav_z1 = total_h - top_wall_t
    n_in = len(inner)
    for i in range(n_in):
        j = (i + 1) % n_in
        x1, y1 = inner[i]
        x2, y2 = inner[j]
        tris.append(make_tri((x1, y1, cav_z0), (x2, y2, cav_z1), (x2, y2, cav_z0)))
        tris.append(make_tri((x1, y1, cav_z0), (x1, y1, cav_z1), (x2, y2, cav_z1)))
    tris += fill_profile(inner, cav_z0, flip=False)
    tris += fill_profile(inner, cav_z1, flip=True)

    # ── 6. Bottom recesses ──────────────────────────────────
    # Passive radiator (small ellipse via circle-scan)
    rad_steps = 16
    for ix in range(-rad_steps, rad_steps + 1):
        fx = ix / rad_steps
        for iy in range(-rad_steps, rad_steps + 1):
            fy = iy / rad_steps
            if fx * fx + fy * fy > 1.0:
                continue
            px = fx * rad_a
            py = fy * rad_b
            tris = cutout_circle(tris, px, py, -0.5, 2.0 + 0.01, 0.9)

    # Qi coil recess (shallow)
    tris = cutout_circle(tris, 0.0, 0.0, -0.5, qi_depth + 0.01, qi_r)

    # NFC tag
    tris = cutout_circle(tris, nfc_cx, nfc_cy, -0.5, nfc_depth + 0.01, nfc_r)

    # ── 7. K-logo recess at dome apex ───────────────────────
    tris = cutout_rect(tris, 0.0, 0.0,
                       dome_top - logo_depth - 0.01, dome_top + 0.01,
                       logo_w, logo_h)

    # ── 8. PCB standoffs (3) ────────────────────────────────
    standoff_r = (case_r - side_wall) * 0.55
    for angle_deg in [30, 150, 270]:
        a = math.radians(angle_deg)
        sx = standoff_r * math.cos(a)
        sy = standoff_r * math.sin(a)
        tris += standoff(sx, sy, cav_z0, standoff_h,
                         outer_r=standoff_or, inner_r=standoff_ir, segs=24)

    # ── 9. Lanyard slot — Ø3mm × 8mm horizontal through side ─
    # Slot center slightly below the top fillet, passing side-to-side
    # along +X axis. Approximate by a line of circular cutouts.
    slot_cy  = 0.0
    slot_cz  = total_h - edge_fillet - 2.5
    slot_r   = 1.5
    slot_len = 8.0
    for i in range(-8, 9):
        fx = i / 8.0
        offset_x = fx * (slot_len / 2)
        # Cut from +Y wall inward
        tris = cutout_circle(tris,
                             case_r * 0.85 + offset_x, slot_cy,
                             slot_cz - slot_r, slot_cz + slot_r,
                             slot_r + 0.05)

    return tris


# ════════════════════════════════════════════════════════════════════
# Koe Pick — Guitar body contact transmitter
# ════════════════════════════════════════════════════════════════════

def generate_koe_pick_case():
    """
    Koe Pick — pick-shaped contact transmitter for electric guitar.
    ───────────────────────────────────────────────────────────────
    40mm Reuleaux triangle, tapered lens cross-section 4→1.5mm.
    Flat back face with central silicone contact bump and transverse
    strap grooves. Smooth front with K-logo recess. No ports.
    Adhered to guitar body with silicone wrap — zero installation.
    """
    pick_width   = 40.0
    thick_center = 4.0
    thick_edge   = 1.5
    fillet_r     = 0.8
    segs         = 192

    tris = []

    outer = reuleaux_triangle_profile(0, 0, pick_width, segs)
    n_out = len(outer)

    # Centroid & max radius
    pcx = sum(p[0] for p in outer) / n_out
    pcy = sum(p[1] for p in outer) / n_out
    max_r = max(math.sqrt((p[0] - pcx) ** 2 + (p[1] - pcy) ** 2) for p in outer)

    # ── Lens thickness profile — 4mm at center, 1.5mm at edge ─
    def edge_thick_at(x, y):
        """Interpolate thickness based on radial distance."""
        r = math.sqrt((x - pcx) ** 2 + (y - pcy) ** 2)
        t = min(1.0, r / max_r)
        # Smooth lens: quadratic fall-off
        return thick_edge + (thick_center - thick_edge) * (1 - t * t)

    z_mid = thick_center / 2

    # ── Back face (z_bottom) — flat at the edge, shallow dome inward
    # Use ring-based approach: concentric shrunk rings from outer→center
    rings = 24
    # For each ring r in [0..rings], scale outer profile toward center.
    # Bottom z falls as radius shrinks (so center is lowest point, maximizing thickness)
    back_rings = []
    for ri in range(rings + 1):
        scale = 1.0 - ri / rings
        ring = [(pcx + (x - pcx) * scale, pcy + (y - pcy) * scale) for x, y in outer]
        # Thickness at this ring radius
        ring_r = max_r * scale
        # z_bot = middle minus half the local thickness
        eff_r = ring_r
        thick = thick_edge + (thick_center - thick_edge) * (1 - (eff_r / max_r) ** 2)
        z_bot = z_mid - thick / 2
        back_rings.append((ring, z_bot))

    # Tessellate back surface (outward/downward normals)
    for ri in range(rings):
        ring_a, z_a = back_rings[ri]
        ring_b, z_b = back_rings[ri + 1]
        na = len(ring_a)
        for i in range(na):
            j = (i + 1) % na
            x1a, y1a = ring_a[i]
            x2a, y2a = ring_a[j]
            x1b, y1b = ring_b[i]
            x2b, y2b = ring_b[j]
            # Downward normals — winding flipped
            tris.append(make_tri((x1a, y1a, z_a), (x2a, y2a, z_a), (x1b, y1b, z_b)))
            tris.append(make_tri((x2a, y2a, z_a), (x2b, y2b, z_b), (x1b, y1b, z_b)))

    # Center back vertex
    ring_last, z_last = back_rings[-1]
    if len(ring_last) > 0:
        # collapse to a small disc
        pass

    # ── Front face (z_top) — symmetric to back ──────────────
    front_rings = []
    for ri in range(rings + 1):
        scale = 1.0 - ri / rings
        ring = [(pcx + (x - pcx) * scale, pcy + (y - pcy) * scale) for x, y in outer]
        ring_r = max_r * scale
        thick = thick_edge + (thick_center - thick_edge) * (1 - (ring_r / max_r) ** 2)
        z_top = z_mid + thick / 2
        front_rings.append((ring, z_top))

    for ri in range(rings):
        ring_a, z_a = front_rings[ri]
        ring_b, z_b = front_rings[ri + 1]
        na = len(ring_a)
        for i in range(na):
            j = (i + 1) % na
            x1a, y1a = ring_a[i]
            x2a, y2a = ring_a[j]
            x1b, y1b = ring_b[i]
            x2b, y2b = ring_b[j]
            # Upward normals
            tris.append(make_tri((x1a, y1a, z_a), (x1b, y1b, z_b), (x2a, y2a, z_a)))
            tris.append(make_tri((x2a, y2a, z_a), (x1b, y1b, z_b), (x2b, y2b, z_b)))

    # ── Side wall — connects back and front at ring 0 ────────
    # back_rings[0] is the outer edge at z_mid - thick_edge/2
    # front_rings[0] is the outer edge at z_mid + thick_edge/2
    outer_back = back_rings[0][0]
    z_b_edge = back_rings[0][1]
    z_f_edge = front_rings[0][1]
    # Thin vertical band
    for i in range(n_out):
        j = (i + 1) % n_out
        x1, y1 = outer_back[i]
        x2, y2 = outer_back[j]
        tris.append(make_tri((x1, y1, z_b_edge), (x2, y2, z_b_edge), (x2, y2, z_f_edge)))
        tris.append(make_tri((x1, y1, z_b_edge), (x2, y2, z_f_edge), (x1, y1, z_f_edge)))

    # ── Central silicone contact bump (back face raised dome) ─
    # Ø8 × 1mm domed cone sticking out the back (lowest z).
    bump_r = 4.0
    bump_h = 1.0
    z_back_center = z_mid - thick_center / 2
    # Build a small cone downward (away from body)
    cone_segs = 48
    for i in range(cone_segs):
        a1 = 2 * math.pi * i / cone_segs
        a2 = 2 * math.pi * ((i + 1) % cone_segs) / cone_segs
        r_base = bump_r
        x1 = pcx + r_base * math.cos(a1)
        y1 = pcy + r_base * math.sin(a1)
        x2 = pcx + r_base * math.cos(a2)
        y2 = pcy + r_base * math.sin(a2)
        tip = (pcx, pcy, z_back_center - bump_h)
        tris.append(make_tri((x1, y1, z_back_center), (x2, y2, z_back_center), tip))

    # ── Transverse silicone strap grooves on the back ────────
    # Two grooves running parallel to x-axis across the back face, 2mm wide.
    groove_w = 2.0
    groove_depth = 0.5
    for gy in [-10.0, 10.0]:
        tris = cutout_rect(tris, pcx, pcy + gy,
                           z_back_center - 0.01,
                           z_back_center + groove_depth + 0.01,
                           pick_width + 2.0, groove_w)

    # ── K-logo recess on the front (5×5mm × 0.3mm) ───────────
    logo_w, logo_h, logo_d = 5.0, 5.0, 0.3
    z_front_center = z_mid + thick_center / 2
    tris = cutout_rect(tris, pcx, pcy,
                       z_front_center - logo_d - 0.01,
                       z_front_center + 0.01,
                       logo_w, logo_h)

    # NFC recess on the back (small, offset)
    nfc_r = 3.0
    tris = cutout_circle(tris, pcx, pcy + 6.0,
                         z_back_center - 0.01,
                         z_back_center + 0.5 + 0.01,
                         nfc_r)

    return tris


# ════════════════════════════════════════════════════════════════════
# Koe Pendant — Ø35mm waterproof teardrop wearable
# ════════════════════════════════════════════════════════════════════

def generate_koe_pendant_case():
    """
    Koe Pendant — waterproof teardrop wearable with integrated bail.
    ─────────────────────────────────────────────────────────────────
    IPX7, 10mm thick, teardrop profile with catenary top dome. A
    rounded tab projects from the pointed end as a CNC'd neck-cord
    bail. O-ring groove around the middle seals the unit.
    """
    body_long   = 45.0      # Teardrop long axis (fat→point)
    body_wide   = 30.0      # Teardrop wide axis (fat end Ø)
    total_h     = 10.0
    dome_h      = 1.5
    edge_fillet = 0.8
    fillet_segs = 8
    segs        = 200

    wall        = 1.0
    floor_t     = 1.5
    top_wall_t  = 1.2

    # ── Teardrop outer profile (explicit — stronger narrowing than helper) ─
    def _teardrop(center_x, center_y, length, width, n_segs):
        """More dramatic teardrop than the default helper — narrows to ~Ø15mm at point."""
        pts = []
        half_w = width / 2
        for i in range(n_segs):
            t = 2 * math.pi * i / n_segs
            cos_t = math.cos(t)
            sin_t = math.sin(t)
            if sin_t >= 0:
                # Top half = narrow end — strong narrowing
                r_scale = 0.5 - 0.5 * sin_t  # at sin_t=1 → 0 at point; at sin_t=0 → 0.5
                # We want narrow tip at half_w * 0.25, fat equator at half_w
                w_factor = 1.0 - 0.75 * sin_t
                x = half_w * w_factor * abs(cos_t) ** 0.85 * (1 if cos_t >= 0 else -1)
                y = (length * 0.6) * sin_t
            else:
                # Bottom half = fat end — round
                x = half_w * abs(cos_t) ** 0.95 * (1 if cos_t >= 0 else -1)
                y = (length * 0.35) * sin_t
            pts.append((center_x + x, center_y + y))
        return pts

    outer = _teardrop(0, 0, body_long, body_wide, segs)
    pcx = sum(p[0] for p in outer) / len(outer)
    pcy = sum(p[1] for p in outer) / len(outer)
    outer = [(x - pcx, y - pcy) for x, y in outer]

    # Inner — offset inward
    inner = []
    for (x, y) in outer:
        dx = x
        dy = y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 1e-6:
            inner.append((x, y))
            continue
        off = wall + edge_fillet
        inner.append((x * (1 - off / dist), y * (1 - off / dist)))

    tris = []

    def _ring_quads(lower_ring, lower_z, upper_ring, upper_z):
        out = []
        nr = len(lower_ring)
        for i in range(nr):
            j = (i + 1) % nr
            px1, py1 = lower_ring[i]
            px2, py2 = lower_ring[j]
            cx1, cy1 = upper_ring[i]
            cx2, cy2 = upper_ring[j]
            out.append(make_tri((px1, py1, lower_z), (cx1, cy1, upper_z), (cx2, cy2, upper_z)))
            out.append(make_tri((px1, py1, lower_z), (cx2, cy2, upper_z), (px2, py2, lower_z)))
        return out

    # Bottom fillet base — slightly inset
    def inset_profile(profile, offset):
        out = []
        for (x, y) in profile:
            dist = math.sqrt(x * x + y * y)
            if dist < 1e-6:
                out.append((x, y))
                continue
            out.append((x * (1 - offset / dist), y * (1 - offset / dist)))
        return out

    bottom_fillet_base = inset_profile(outer, edge_fillet)
    tris += fill_profile(bottom_fillet_base, 0.0, flip=True)

    prev_ring = bottom_fillet_base
    prev_z = 0.0
    for k in range(1, fillet_segs + 1):
        t = (math.pi / 2) * k / fillet_segs
        dr = edge_fillet * (1.0 - math.sin(t))
        dz = edge_fillet * (1.0 - math.cos(t))
        curr_ring = inset_profile(outer, dr)
        curr_z = dz
        tris += _ring_quads(prev_ring, prev_z, curr_ring, curr_z)
        prev_ring = curr_ring
        prev_z = curr_z

    # Vertical wall (with mid-line O-ring groove built in by inset)
    wall_z0 = edge_fillet
    wall_z1 = total_h - edge_fillet
    tris += extrude_profile(outer, wall_z0, wall_z1)

    # Top fillet
    prev_ring = outer
    prev_z = wall_z1
    for k in range(1, fillet_segs + 1):
        t = (math.pi / 2) * k / fillet_segs
        dr = edge_fillet * (1.0 - math.cos(t))
        dz = edge_fillet * math.sin(t)
        curr_ring = inset_profile(outer, dr)
        curr_z = wall_z1 + dz
        tris += _ring_quads(prev_ring, prev_z, curr_ring, curr_z)
        prev_ring = curr_ring
        prev_z = curr_z

    # Catenary dome
    tris += make_dome_catenary(prev_ring, prev_z, dome_h, rings=24)
    dome_top = prev_z + dome_h

    # Internal cavity
    cav_z0 = floor_t
    cav_z1 = total_h - top_wall_t
    n_in = len(inner)
    for i in range(n_in):
        j = (i + 1) % n_in
        x1, y1 = inner[i]
        x2, y2 = inner[j]
        tris.append(make_tri((x1, y1, cav_z0), (x2, y2, cav_z1), (x2, y2, cav_z0)))
        tris.append(make_tri((x1, y1, cav_z0), (x1, y1, cav_z1), (x2, y2, cav_z1)))
    tris += fill_profile(inner, cav_z0, flip=False)
    tris += fill_profile(inner, cav_z1, flip=True)

    # ── Bottom features ────────────────────────────────────
    # Qi coil Ø22
    tris = cutout_circle(tris, 0.0, -2.0, -0.5, 1.0 + 0.01, 11.0)
    # NFC Ø6
    tris = cutout_circle(tris, 0.0, 8.0, -0.5, 0.5 + 0.01, 3.0)
    # Passive radiator 15×10 as ellipse-scan
    for ix in range(-10, 11):
        fx = ix / 10
        for iy in range(-10, 11):
            fy = iy / 10
            if fx * fx + fy * fy > 1.0:
                continue
            px = fx * 7.5
            py = -2.0 + fy * 5.0
            tris = cutout_circle(tris, px, py, -0.5, 1.5 + 0.01, 0.7)

    # 2× M2 standoffs
    for sx, sy in [(-6.0, 0.0), (6.0, 0.0)]:
        tris += standoff(sx, sy, cav_z0, 1.5, outer_r=1.2, inner_r=0.55, segs=20)

    # ── Top K-logo 4×4×0.3mm, slightly toward fat end ─────────
    logo_w, logo_h, logo_d = 4.0, 4.0, 0.3
    tris = cutout_rect(tris, 0.0, -3.0,
                       dome_top - logo_d - 0.01, dome_top + 0.01,
                       logo_w, logo_h)

    # ── O-ring groove around perimeter at mid-height ─────────
    # 0.8 wide × 0.4 deep at z = total_h / 2
    groove_z_center = total_h / 2
    groove_half = 0.4
    groove_depth = 0.4
    groove_profile = inset_profile(outer, groove_depth)
    # Cut an annular band by extruding a slightly-inset profile — approximate by
    # a row of circular cutouts sweeping along the perimeter.
    for (ox, oy) in outer[::2]:
        # Direction from center
        d = math.sqrt(ox * ox + oy * oy)
        if d < 1e-6:
            continue
        nx = ox / d
        ny = oy / d
        # A point just inside the wall
        gx = ox - nx * (groove_depth * 0.5)
        gy = oy - ny * (groove_depth * 0.5)
        tris = cutout_circle(tris, gx, gy,
                             groove_z_center - groove_half,
                             groove_z_center + groove_half,
                             groove_depth + 0.3)

    # ── Lanyard bail — rounded tab extending from pointed end ─
    # The pointed end is at +Y by construction.
    ys = [p[1] for p in outer]
    max_y = max(ys)
    # Build a rounded-rect bail that projects from the point
    bail_cy = max_y + 3.5
    bail_w = 7.0
    bail_l = 7.0
    bail_h = total_h          # Match body height
    # Rounded rect profile
    bail_profile = rounded_rect_profile(0.0, bail_cy, bail_w, bail_l, 3.0, segs_per_corner=16)
    bail_z0 = 0.0
    bail_z1 = bail_h
    tris += extrude_profile(bail_profile, bail_z0, bail_z1)
    tris += fill_profile(bail_profile, bail_z0, flip=True)
    tris += fill_profile(bail_profile, bail_z1, flip=False)
    # Ø3mm through-hole
    tris = cutout_circle(tris, 0.0, bail_cy,
                         bail_z0 - 0.1, bail_z1 + 0.1, 1.5)

    return tris


# ════════════════════════════════════════════════════════════════════
# Koe Amp — 60x60x55mm shelf speaker
# ════════════════════════════════════════════════════════════════════

def generate_koe_amp_case():
    """
    Koe Amp — shelf speaker, 60 × 60 × 55mm, step-trapezoid.
    ─────────────────────────────────────────────────────────
    Big BMR driver, 5000mAh cell, fibonacci-grille front face,
    back-face Qi charging. CNC aluminum unibody. Tilts back ~5°
    so the face aims up and out like a classic combo amp.
    """
    body_w       = 60.0      # X — horizontal width (front view)
    body_h_front = 60.0      # Z — front-face height
    body_h_back  = 55.0      # Z — back-face height (5mm shorter → 5° tilt)
    body_d       = 55.0      # Y — depth front to back
    SUPER_N      = 4.0
    segs         = 128
    wall_t       = 2.0
    fillet_r     = 1.2

    tris = []

    # Build as a vertical prism along Y (depth). The outline in XZ-plane is
    # a superellipse rect-ish profile whose Z max differs between front and back.
    # Easier to tessellate as two superellipse rects (front XZ, back XZ) connected
    # by side walls.
    # Treat this as: a superellipse plan-view in Y direction extrusion — no.
    # Let me use the other direction: build a "box" whose 6 faces are superellipses
    # in the plane perpendicular to their outward normal.
    #
    # Simpler approach: think of the amp as an extrusion along Y (depth).
    # The XZ profile is a superellipse rect of width=body_w, height=body_h(y).
    # The height linearly decreases from body_h_front (at y=0) to body_h_back (at y=body_d).

    # Cross-section at given Y
    def xz_profile_at(y, n_segs=segs, n=SUPER_N):
        # Interpolated height
        t = y / body_d
        h = body_h_front * (1 - t) + body_h_back * t
        half_w = body_w / 2
        half_h = h / 2
        pts = []
        for i in range(n_segs):
            theta = 2 * math.pi * i / n_segs
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)
            x = half_w * abs(cos_t) ** (2 / n) * (1 if cos_t >= 0 else -1)
            z = half_h * abs(sin_t) ** (2 / n) * (1 if sin_t >= 0 else -1)
            pts.append((x, z + h / 2))  # shift so bottom sits at z=0
        return pts

    # Number of Y slices
    y_slices = 32
    rings = []
    for si in range(y_slices + 1):
        y = body_d * si / y_slices
        prof = xz_profile_at(y)
        rings.append((y, prof))

    # Connect rings to form side wall
    for si in range(y_slices):
        y_a, prof_a = rings[si]
        y_b, prof_b = rings[si + 1]
        n = len(prof_a)
        for i in range(n):
            j = (i + 1) % n
            x1a, z1a = prof_a[i]
            x2a, z2a = prof_a[j]
            x1b, z1b = prof_b[i]
            x2b, z2b = prof_b[j]
            tris.append(make_tri((x1a, y_a, z1a), (x1b, y_b, z1b), (x2a, y_a, z2a)))
            tris.append(make_tri((x2a, y_a, z2a), (x1b, y_b, z1b), (x2b, y_b, z2b)))

    # Front face (y=0) — fan fill
    _, prof_front = rings[0]
    n = len(prof_front)
    cx_f = 0.0
    cz_f = sum(p[1] for p in prof_front) / n
    for i in range(n):
        j = (i + 1) % n
        x1, z1 = prof_front[i]
        x2, z2 = prof_front[j]
        # Front face — outward normal -Y
        tris.append(make_tri((cx_f, 0.0, cz_f), (x2, 0.0, z2), (x1, 0.0, z1)))

    # Back face (y=body_d)
    _, prof_back = rings[-1]
    n = len(prof_back)
    cz_b = sum(p[1] for p in prof_back) / n
    for i in range(n):
        j = (i + 1) % n
        x1, z1 = prof_back[i]
        x2, z2 = prof_back[j]
        tris.append(make_tri((cx_f, body_d, cz_b), (x1, body_d, z1), (x2, body_d, z2)))

    # ── Grille on the +Y face (which is what the thumbnail camera sees) ─
    # The thumbnail camera looks from (+X, +Y), so the +Y face (back of the
    # depth extrusion, but visually "front" from camera POV) is the natural
    # place for the Fibonacci grille. Qi charging goes on the -Y face instead.
    grille_cx = 0.0
    grille_cz = body_h_back / 2
    grille_y  = body_d

    def cutout_cyl_y(tris_in, cx, cz, y0, y1, r):
        result = []
        for tri in tris_in:
            _, (v1, v2, v3) = tri
            mx = (v1[0] + v2[0] + v3[0]) / 3
            my = (v1[1] + v2[1] + v3[1]) / 3
            mz = (v1[2] + v2[2] + v3[2]) / 3
            dist = math.sqrt((mx - cx) ** 2 + (mz - cz) ** 2)
            if dist < r and y0 <= my <= y1:
                continue
            result.append(tri)
        return result

    # Fibonacci holes — big and deep, drilled inward from +Y face
    holes = fibonacci_spiral_holes(grille_cx, grille_cz, 22.0, n_holes=13)
    for hx, hz in holes:
        tris = cutout_cyl_y(tris, hx, hz, grille_y - 5.0, grille_y + 0.5, 3.2)
    # Central hole — largest (driver center)
    tris = cutout_cyl_y(tris, grille_cx, grille_cz,
                        grille_y - 5.0, grille_y + 0.5, 5.0)
    # Outer ring of smaller holes around the grille
    for ang in range(0, 360, 30):
        a = math.radians(ang)
        rx = grille_cx + 18.0 * math.cos(a)
        rz = grille_cz + 18.0 * math.sin(a)
        tris = cutout_cyl_y(tris, rx, rz, grille_y - 5.0, grille_y + 0.5, 1.6)

    # ── Top face K-logo — the top of the trapezoid ──────────
    # Top surface is a sloped plane from (z=body_h_front, y=0) to (z=body_h_back, y=body_d).
    # Use an X-aligned cutout near y=body_d/2, z=body_h_front-2
    # It's a sloped surface so we cut a rectangular prism through it.
    logo_w = 8.0
    logo_l = 8.0
    logo_d = 0.3
    # Approximate as rectangular pocket near the top surface at y=body_d/2
    # At y = body_d / 2 → h_here = (body_h_front + body_h_back)/2
    top_cz = (body_h_front + body_h_back) / 2
    tris = cutout_rect(tris, 0.0, body_d / 2,
                       top_cz - logo_d - 0.01, top_cz + 5.0,
                       logo_w, logo_l)

    # ── -Y face Qi coil recess (the "back" where it rests for charging) ─
    back_cz = body_h_front / 2
    tris = cutout_cyl_y(tris, 0.0, back_cz,
                        -0.5, 2.0, 20.0)
    # NFC recess near Qi
    tris = cutout_cyl_y(tris, 14.0, back_cz,
                        -0.5, 1.0, 3.0)

    # ── Bottom rubber-foot recesses (4× corners, Ø8 × 0.5) ──
    # Bottom is at z=0
    for fx, fy in [(-22.0, 6.0), (22.0, 6.0),
                   (-22.0, body_d - 6.0), (22.0, body_d - 6.0)]:
        tris = cutout_circle(tris, fx, fy, -0.1, 0.5 + 0.01, 4.0)

    # (Cavity omitted at thumbnail resolution — in CNC the cavity is milled
    # from a bottom access plate in post. For STL visualization, the solid
    # exterior is what matters.)

    return tris


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 65)
    print("Koe Device -- Production Case Generator (PCB-accurate)")
    print("=" * 65)

    cases = [
        ("Pebble — The Stone", "coin-lite-case.stl",
         "Superellipse n=3, 26mm, catenary dome, Fibonacci speaker",
         generate_coin_lite_case),
        ("Pro v2", "pro-v2-case.stl",
         "49.4x34.4x20.7mm pill shape, snap-fit 2-piece",
         generate_pro_v2_case),
        ("Hub v2", "hub-v2-case.stl",
         "146.6x126.6x28.6mm box + screw-down lid",
         generate_hub_v2_case),
        ("Band — The Lens", "seed-wristband-pod.stl",
         "Superellipse 28x20mm, biconvex lens, edge 2mm center 6mm",
         generate_seed_wristband_pod),
        ("Tag — The Drop", "seed-keychain.stl",
         "Teardrop 26x20mm, catenary dome, torus keyring loop",
         generate_seed_keychain),
        ("Seed Clip", "seed-clip.stl",
         "35x25x12mm oval + integrated belt/backpack clip",
         generate_seed_clip),
        ("Seed Badge", "seed-badge.stl",
         "55x35x8mm event badge, name card window, lanyard hole",
         generate_seed_badge),
        ("Seed Pendant", "seed-pendant.stl",
         "35x28x10mm teardrop pebble, cord hole, river-stone shape",
         generate_seed_pendant),
        ("Seed Sticker", "seed-sticker.stl",
         "Ø32mm disc, 6mm ultra-thin, 3M adhesive back",
         generate_seed_sticker),
        ("Pick — The Plectrum", "seed-pick.stl",
         "Reuleaux triangle 24mm, constant-width, grip taper 4.5→2mm",
         generate_seed_pick),
        ("Seed Drum Key", "seed-drumkey.stl",
         "T-shape 35mm handle + 20mm head, drum rim clip",
         generate_seed_drumkey),
        ("Seed Capo", "seed-capo.stl",
         "40x20x15mm spring clip, guitar neck/mic stand mount",
         generate_seed_capo),
        # ── Wearable Audio ──
        ("Seed Ring", "seed-ring.stl",
         "finger ring US8, 24mm outer, signet mount with speaker",
         generate_seed_ring),
        ("Seed Earphone", "seed-earphone.stl",
         "15x12x10mm TWS earphone shell, ear canal nozzle",
         generate_seed_earphone),
        ("Seed Headphone", "seed-headphone.stl",
         "60x50x25mm over-ear cup, 40mm driver, headband hinge",
         generate_seed_headphone),
        ("Seed Neckband", "seed-neckband.stl",
         "U-shape neckband, 140mm neck radius, dual speaker pods",
         generate_seed_neckband),
        ("Seed Glasses", "seed-glasses.stl",
         "170x15x8mm temple arm clip, ear-tip speaker",
         generate_seed_glasses),
        # ── Lifestyle ──
        ("Seed Watch", "seed-watch.stl",
         "42mm dial, 10mm thick, bone-conduction back, band lugs",
         generate_seed_watch),
        ("Seed Hat Clip", "seed-hat-clip.stl",
         "25x15x8mm brim clip, spring arm, near-ear speaker",
         generate_seed_hat_clip),
        ("Seed Shoe", "seed-shoe.stl",
         "100x40x5mm insole insert, dual vibration motor cavities",
         generate_seed_shoe),
        ("Seed Bottle", "seed-bottle.stl",
         "Ø45mm cap, 20mm tall, 28mm bottle thread, top speaker",
         generate_seed_bottle),
        # ── Pro/Studio ──
        ("Seed Mic Clip", "seed-mic-clip.stl",
         "30x20x12mm body + C-clamp for 25mm mic stand",
         generate_seed_mic_clip),
        ("Seed Pedalboard", "seed-pedalboard.stl",
         "60x40x25mm pedal, footswitch, 1/4\" jacks, stage-rugged",
         generate_seed_pedalboard),
        ("Seed Amp", "seed-amp.stl",
         "50x50x50mm desktop cube, 40mm speaker, volume knob",
         generate_seed_amp),
        # ── Fun/Novel ──
        ("Seed Ball", "seed-ball.stl",
         "40mm sphere, omnidirectional, flat bottom, roll-safe",
         generate_seed_ball),
        ("Card", "seed-card.stl",
         "85x54x4mm credit card size, edge-firing speaker, wallet-fit",
         generate_seed_card),
        ("Seed Figurine", "seed-figurine.stl",
         "Ø40mm base, 15mm tall, figure mount hole, LED ring",
         generate_seed_figurine),
        # ── Outdoor ──
        ("Seed Outdoor", "seed-outdoor.stl",
         "Ø38mm, 15mm tall, IP67, -30°C rated, PA12 nylon, carabiner loop",
         generate_seed_outdoor),
        ("Seed Wristband Pod v2", "seed-wristband.stl",
         "32x22mm biconvex, shallower, lateral strap slots, charging contacts",
         generate_seed_wristband_v2),
        # ── Ultra-compact ──
        ("Dot — The Seed", "seed-dot.stl",
         "Ø20mm lenticular, 4mm center, 0.5mm edge, double-convex lens",
         generate_seed_dot),
        # ── Developer Edition ──
        ("DK Case", "dk-case.stl",
         "135x65x25mm open-top box for nRF5340 Audio DK",
         generate_dk_case),
        # ── Koe Platform Siblings (5-SKU family) ──
        ("Stone Mini", "koe-mini-case.stl",
         "Ø50x15mm pocket sibling, superellipse n=3.5, lanyard slot",
         generate_koe_mini_case),
        ("Koe Pick", "koe-pick-case.stl",
         "40mm Reuleaux guitar contact transmitter, lens taper 4→1.5mm",
         generate_koe_pick_case),
        ("Koe Pendant", "koe-pendant-case.stl",
         "Ø35x10mm teardrop IPX7 wearable, integrated CNC bail",
         generate_koe_pendant_case),
        ("Koe Amp", "koe-amp-case.stl",
         "60x60x55 shelf speaker, fibonacci grille, 5° tilt",
         generate_koe_amp_case),
    ]

    for name, filename, desc, gen_func in cases:
        print(f"\nGenerating {name} ({desc})...")
        tris = gen_func()
        path = OUT_DIR / filename
        write_stl(path, tris)
        print(f"  {path.name}: {len(tris)} triangles, {path.stat().st_size:,} bytes")

    print("\n" + "=" * 65)
    print("All cases generated. PCB-accurate dimensions with:")
    print(f"  PCB tolerance: {PCB_TOL}mm")
    print(f"  Snap-fit interference: {SNAP_TOL}mm")
    print()
    print("Recommended print settings:")
    print("  Material: SLA Black Resin (COIN Lite, Pro v2)")
    print("           MJF Nylon PA12 (Hub v2)")
    print("  Tolerance: 0.1mm (SLA) / 0.2mm (MJF)")
    print()
    print("Order at:")
    print("  JLCPCB 3D: https://jlcpcb.com/3d-printing")
    print("  PCBWay 3D: https://www.pcbway.com/rapid-prototyping/3d-printing/")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
