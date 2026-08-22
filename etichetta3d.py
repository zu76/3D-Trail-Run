#!/usr/bin/env python3
"""
etichetta3d.py — 3D printable label: individual letters + snap-off runner.

The label is NOT a name plate. Every letter is a separate solid; there is no
material behind or between them. A single straight runner (spine) sits above the
text and reaches each letter through a post that ends in a thin snap notch, so
the whole label can be handled and glued as one piece and the runner then broken
off, leaving only the letters on the surface. Same principle as an injection
moulding sprue or a model kit runner.

Front-face chamfer as a distance-field roof
-------------------------------------------
The chamfer cannot be an inward polygon offset: the narrowest neck in this text
is 0.39 mm (the shoulder of "m" at cap 6.5 mm), so offsetting inward by 0.40 mm
per side would collapse the front face and self-intersect. Instead the top
surface is the height field

    z(x, y) = min(DEPTH, DEPTH - CHAMFER + d(x, y))

with d the exact distance to the glyph outline. Where the glyph is wider than
2*CHAMFER this is a flat front face with a 45 deg bevel all round; where it is
narrower the bevel simply meets itself and forms a ridge below DEPTH. Same level
set idiom as rilievo3d_intarsio.py, and robust for any chamfer size.

Meshes written by hand, no CAD libraries. Validation: manifold, Euler
characteristic, signed volume against an independent analytical estimate.

Dependencies: numpy, scipy, matplotlib (font outlines only)
Output: 3d-outputs/GTC55-2026/GTC55-2026_label_<length>mm.stl

Usage:
    python3 etichetta3d.py --fit --max-len 180
    python3 etichetta3d.py --part letters --out 3d-outputs/GTC55-2026
    python3 etichetta3d.py --cap 6.5
"""
import argparse, os, struct
import numpy as np
from scipy.spatial import Delaunay
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
from matplotlib.ft2font import FT2Font

# ------------------------------------------------------------------ parameters
FONT_PATH = r"C:\Windows\Fonts\impact.ttf"
TEXT = "2026 GTC55 \u2013 Courmayeur Mont Blanc"
FONT_SIZE = 1000.0        # font units used for outline extraction

CAP = 6.50                # cap height, mm  -> total 126.47 mm
DEPTH = 2.00              # extrusion depth, mm (Z, back face on the bed)
CHAMFER = 0.40            # front-face chamfer, mm (45 deg)
MIN_GAP = 0.50            # minimum air gap between adjacent letter inks, mm

SPINE_H = 1.00            # runner rail height, mm (Y)
SPINE_CLR = 0.40          # rail underside above the tallest ink, mm
RAIL_Z = 1.00             # runner depth, mm (Z, flush with the back face)
POST_W = 0.80             # post width, mm (X)
NOTCH_W = 0.45            # snap notch width, mm (X)
NOTCH_H = 0.35            # snap notch length, mm (Y)
NOTCH_OVER = 0.10         # notch penetration into the letter, mm
BRIDGE_Z = 0.60           # depth of the bridge joining parts of one glyph, mm

MESH_FINE = 0.10          # top-surface point spacing inside the chamfer band, mm
MESH_COARSE = 0.25        # top-surface point spacing on the flat front face, mm
BSTEP = 0.05              # outline densification step, mm


# ------------------------------------------------------------------- outlines
def _font():
    fp = FontProperties(fname=FONT_PATH)
    ft = FT2Font(FONT_PATH)
    ft.set_size(FONT_SIZE, 72)
    return fp, ft


def glyph_loops(ch, fp, steps=8):
    """Closed outline loops of one glyph, in font units.

    to_polygons() repeats the first point at the end and can emit consecutive
    duplicates; both are stripped so every loop is a clean cycle of distinct
    vertices and np.roll gives the edges directly.
    """
    p = TextPath((0, 0), ch, size=FONT_SIZE, prop=fp)
    p._interpolation_steps = steps
    out = []
    for q in p.to_polygons():
        L = np.asarray(q, float)
        keep = np.concatenate([[True], np.linalg.norm(np.diff(L, axis=0), axis=1) > 1e-9])
        L = L[keep]
        if len(L) > 1 and np.linalg.norm(L[-1] - L[0]) < 1e-9:
            L = L[:-1]
        if len(L) >= 3:
            out.append(L)
    return out


def signed_area(loop):
    x, y = loop[:, 0], loop[:, 1]
    return 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)


def orient(loops):
    """Outer loops counter-clockwise, holes clockwise: the solid stays on the
    left of every edge, so one wall formula gives outward normals everywhere."""
    out = []
    for i, L in enumerate(loops):
        depth = 0
        pt = L[0]
        for j, O in enumerate(loops):
            if i != j and _crossings(pt[None, :], O) % 2 == 1:
                depth += 1
        ccw = signed_area(L) > 0
        want_ccw = (depth % 2 == 0)
        out.append(L[::-1].copy() if ccw != want_ccw else L.copy())
    return out


def _crossings(P, loop):
    """Ray crossing count of points P against one closed loop."""
    A, B = loop, np.roll(loop, -1, axis=0)
    cnt = np.zeros(len(P), np.int64)
    for i in range(0, len(A), 512):
        a, b = A[i:i + 512], B[i:i + 512]
        y1, y2 = a[:, 1][None, :], b[:, 1][None, :]
        px, py = P[:, 0][:, None], P[:, 1][:, None]
        straddle = (y1 > py) != (y2 > py)
        dy = np.where(np.abs(y2 - y1) < 1e-18, 1e-18, y2 - y1)
        xin = (b[:, 0] - a[:, 0])[None, :] * (py - y1) / dy + a[:, 0][None, :]
        cnt += (straddle & (px < xin)).sum(1)
    return cnt


def inside(P, loops):
    """Even-odd containment of points P in a set of loops."""
    cnt = np.zeros(len(P), np.int64)
    for L in loops:
        cnt += _crossings(P, L)
    return cnt % 2 == 1


def densify(loop, step):
    """Resample a closed loop so no edge is longer than step."""
    out = []
    for a, b in zip(loop, np.roll(loop, -1, axis=0)):
        n = max(1, int(np.ceil(np.linalg.norm(b - a) / step)))
        for k in range(n):
            out.append(a + (b - a) * k / n)
    return np.array(out)


def dist_to_edges(P, A, B):
    """Exact distance from every point of P to the closest segment A->B."""
    AB = B - A
    L2 = np.einsum("ij,ij->i", AB, AB)
    L2 = np.where(L2 < 1e-18, 1e-18, L2)
    out = np.empty(len(P))
    for i in range(0, len(P), 512):
        q = P[i:i + 512]
        w = q[:, None, :] - A[None, :, :]
        t = np.clip(np.einsum("kij,ij->ki", w, AB) / L2, 0.0, 1.0)
        pr = A[None, :, :] + t[:, :, None] * AB[None, :, :]
        out[i:i + 512] = np.linalg.norm(q[:, None, :] - pr, axis=2).min(1)
    return out


# --------------------------------------------------------------- triangulation
def triangulate(loops, cham):
    """Triangulate the region bounded by loops.

    Returns (pts, tris, bidx) where bidx lists the boundary index pairs in loop
    order. The boundary of the returned triangle set is verified to be exactly
    the polygon boundary, so walls stitched onto bidx close the solid.
    """
    bstep = BSTEP
    for _ in range(4):
        dl = [densify(L, bstep) for L in loops]
        bpts = np.vstack(dl)
        bidx, off = [], 0
        for L in dl:
            n = len(L)
            bidx += [(off + i, off + (i + 1) % n) for i in range(n)]
            off += n
        A = bpts[[i for i, _ in bidx]]
        B = bpts[[j for _, j in bidx]]

        lo, hi = bpts.min(0), bpts.max(0)
        extra = []
        for spacing, band in ((MESH_FINE, True), (MESH_COARSE, False)):
            gx = np.arange(lo[0] + spacing / 2, hi[0], spacing)
            gy = np.arange(lo[1] + spacing / 2, hi[1], spacing)
            if not len(gx) or not len(gy):
                continue
            G = np.stack(np.meshgrid(gx, gy), -1).reshape(-1, 2)
            G = G[inside(G, loops)]
            if not len(G):
                continue
            d = dist_to_edges(G, A, B)
            edge = cham + 0.15
            keep = (d > 0.55 * spacing) & ((d < edge) if band else (d >= edge))
            extra.append(G[keep])

        pts = np.vstack([bpts] + [e for e in extra if len(e)])
        dt = Delaunay(pts)
        tri, nb, N = dt.simplices.copy(), dt.neighbors, len(pts)

        # Flood fill with the outline edges as walls. Classifying triangles one
        # by one on their centroid is not safe: three consecutive boundary
        # points form a near-degenerate sliver whose centroid sits essentially
        # on the outline and lands on the wrong side along concave arcs. Region
        # growing only ever tests one large triangle per region instead.
        wall = {min(i, j) * N + max(i, j) for i, j in bidx}
        comp = np.full(len(tri), -1)
        ncomp = 0
        for s0 in range(len(tri)):
            if comp[s0] >= 0:
                continue
            comp[s0], stack = ncomp, [s0]
            while stack:
                s = stack.pop()
                for m in range(3):
                    t = nb[s, m]
                    if t < 0 or comp[t] >= 0:
                        continue
                    a, b = tri[s, (m + 1) % 3], tri[s, (m + 2) % 3]
                    if min(a, b) * N + max(a, b) in wall:
                        continue
                    comp[t] = ncomp
                    stack.append(t)
            ncomp += 1

        p = pts[tri]
        e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
        cross = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
        area = np.abs(cross) / 2.0
        keep = np.zeros(len(tri), bool)
        for c in range(ncomp):
            idx = np.flatnonzero(comp == c)
            rep = idx[np.argmax(area[idx])]
            if inside(pts[tri[rep]].mean(0)[None, :], loops)[0]:
                keep[idx] = True
        # Densifying straight outline segments feeds qhull exactly collinear
        # points, and it answers with zero-area simplices. They carry no
        # surface, but if one is kept it duplicates the outline edges it sits
        # on and the shell stops being manifold, so discard them.
        keep &= area > 1e-9
        tri = tri[keep]

        # keep triangles counter-clockwise so the top normal is +Z
        neg = cross[keep] < 0
        tri[neg] = tri[neg][:, ::-1]

        # the region boundary must be exactly the polygon boundary
        ed = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
        key = np.minimum(ed[:, 0], ed[:, 1]) * len(pts) + np.maximum(ed[:, 0], ed[:, 1])
        u, c = np.unique(key, return_counts=True)
        got = set(u[c == 1].tolist())
        want = {min(i, j) * len(pts) + max(i, j) for i, j in bidx}
        if got == want:
            return pts, tri, bidx
        bstep *= 0.5
    raise RuntimeError("triangulation boundary does not match the outline")


def extrude(loops, depth, cham):
    """Solid with a flat back face at z=0 and a chamfered front face at z=depth."""
    pts, tri, bidx = triangulate(loops, cham)
    A = pts[[i for i, _ in bidx]]
    B = pts[[j for _, j in bidx]]
    d = dist_to_edges(pts, A, B)
    ztop = np.minimum(depth, depth - cham + d)
    zrim = depth - cham

    T = []
    bot = np.dstack([pts[tri], np.zeros((len(tri), 3, 1))])
    T.append(bot[:, ::-1])                                   # normal -Z
    top = np.dstack([pts[tri], ztop[tri][:, :, None]])
    T.append(top)                                            # normal +Z
    for i, j in bidx:                                        # vertical walls
        a, b = pts[i], pts[j]
        p00 = [a[0], a[1], 0.0]; p10 = [b[0], b[1], 0.0]
        p11 = [b[0], b[1], zrim]; p01 = [a[0], a[1], zrim]
        T.append(np.array([[p00, p10, p11], [p00, p11, p01]]))
    return np.concatenate(T)


def box(x0, x1, y0, y1, z0, z1):
    """Axis-aligned box with outward normals."""
    v = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
         (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
         (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return v[np.array(f)]


# --------------------------------------------------------------------- layout
def components(loops):
    """Split a glyph into its disconnected solids: each outer loop with the
    holes nested inside it. Impact's `i` is a stem plus a separate dot, so a
    glyph is not always one piece, and every piece needs its own post or it
    prints unattached to the runner."""
    depth = []
    for i, L in enumerate(loops):
        d = sum(1 for j, O in enumerate(loops)
                if i != j and _crossings(L[0][None, :], O)[0] % 2 == 1)
        depth.append(d)
    out = []
    for i, L in enumerate(loops):
        if depth[i] % 2:
            continue
        holes = [O for j, O in enumerate(loops)
                 if depth[j] % 2 and _crossings(O[0][None, :], L)[0] % 2 == 1]
        out.append([L] + holes)
    return out


def scan_x(loops, y):
    """Solid x intervals of the glyph at height y."""
    xs = []
    for L in loops:
        for a, b in zip(L, np.roll(L, -1, axis=0)):
            if (a[1] <= y < b[1]) or (b[1] <= y < a[1]):
                xs.append(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
    xs.sort()
    return list(zip(xs[0::2], xs[1::2]))


def layout(cap):
    """Glyph metrics and pen positions, honouring MIN_GAP between inks."""
    fp, ft = _font()
    cap_units = max(q[:, 1].max() for q in glyph_loops("0", fp))
    k = cap / cap_units

    M = {}
    for ch in set(TEXT) - {" "}:
        L = [q * k for q in glyph_loops(ch, fp)]
        gates = []
        for comp in components(L):
            ctop = max(q[:, 1].max() for q in comp)
            best = (0.0, 0.0)
            for f in (0.02, 0.04, 0.07, 0.10):
                for a, b in scan_x(comp, ctop - f * cap):
                    if b - a > best[1] - best[0]:
                        best = (a, b)
                if best[1] - best[0] > 0.10 * cap:
                    break
            gates.append(dict(top=ctop,
                               bot=min(q[:, 1].min() for q in comp),
                               il=min(q[:, 0].min() for q in comp),
                               ir=max(q[:, 0].max() for q in comp),
                               ga=best[0], gb=best[1]))
        M[ch] = dict(loops=L,
                     adv=ft.load_char(ord(ch)).linearHoriAdvance / 65536.0 * k,
                     il=min(q[:, 0].min() for q in L),
                     ir=max(q[:, 0].max() for q in L),
                     top=max(q[:, 1].max() for q in L),
                     bot=min(q[:, 1].min() for q in L),
                     gates=gates)
    space = ft.load_char(32).linearHoriAdvance / 65536.0 * k

    pen, placed, added = 0.0, [], 0.0
    for ch in TEXT:
        if ch == " ":
            pen += space
            continue
        m = M[ch]
        if placed:
            p = placed[-1]
            gap = (pen + m["il"]) - (p["x"] + M[p["ch"]]["ir"])
            if gap < MIN_GAP:
                pen += MIN_GAP - gap
                added += MIN_GAP - gap
        placed.append(dict(ch=ch, x=pen))
        pen += m["adv"]

    x0 = min(p["x"] + M[p["ch"]]["il"] for p in placed)
    for p in placed:
        p["x"] -= x0
    width = max(p["x"] + M[p["ch"]]["ir"] for p in placed)
    return M, placed, width, added


def fit_cap(target, lo=2.0, hi=20.0):
    """Largest cap height whose total ink length still fits target, mm.

    Not a plain ratio: MIN_GAP is absolute, so as the letters shrink the air
    gaps take a growing share of the width and the relation is only piecewise
    linear."""
    for _ in range(40):
        mid = (lo + hi) / 2
        if layout(mid)[2] <= target:
            lo = mid
        else:
            hi = mid
    return lo


# ------------------------------------------------------------------ validation
def validate(T, name, expected=None):
    v = np.round(T.reshape(-1, 3), 5)
    uq, inv = np.unique(v, axis=0, return_inverse=True)
    f = inv.reshape(-1, 3)
    ed = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    key = (np.minimum(ed[:, 0], ed[:, 1]).astype(np.int64) * len(uq)
           + np.maximum(ed[:, 0], ed[:, 1]))
    ue, uc = np.unique(key, return_counts=True)
    dk = ed[:, 0].astype(np.int64) * len(uq) + ed[:, 1]
    _, dc = np.unique(dk, return_counts=True)
    chi = len(uq) - len(ue) + len(f)
    vol = np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() / 6.0
    print(f"  {name}: V={len(uq)} E={len(ue)} F={len(f)} chi={chi}")
    print(f"    non-manifold={int((uc != 2).sum())}  "
          f"inconsistent-orientation={int((dc != 1).sum())}  "
          f"volume={vol/1000:.3f} cm3", end="")
    print(f"  (estimate {expected/1000:.3f}, deviation {abs(vol-expected)/expected*100:.2f} %)"
          if expected else "")
    return vol


def write_stl(T, path, name):
    p0, p1, p2 = T[:, 0], T[:, 1], T[:, 2]
    n = np.cross(p1 - p0, p2 - p0)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    rec = np.zeros(len(T), dtype=[("d", "<f4", 12), ("a", "<u2")])
    rec["d"][:, 0:3] = n
    rec["d"][:, 3:12] = T.reshape(-1, 9)
    with open(path, "wb") as f:
        f.write(name.encode()[:80].ljust(80, b" "))
        f.write(struct.pack("<I", len(T)))
        rec.tofile(f)


# ------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="GTC55-2026",
                    help="project name: output subfolder and filename prefix")
    ap.add_argument("--text", default=TEXT, help="label text")
    ap.add_argument("--out", default=None,
                    help="output directory (default 3d-outputs/<name>)")
    ap.add_argument("--part", default="all", choices=["all", "letters", "runner"])
    ap.add_argument("--cap", type=float, default=CAP)
    ap.add_argument("--depth", type=float, default=DEPTH)
    ap.add_argument("--chamfer", type=float, default=CHAMFER)
    ap.add_argument("--max-len", type=float, default=130.0)
    ap.add_argument("--fit", action="store_true",
                    help="solve the cap height so the label fills --max-len")
    args = ap.parse_args()

    globals()["TEXT"] = args.text
    if args.out is None:
        args.out = os.path.join("3d-outputs", args.name)

    if args.fit:
        args.cap = fit_cap(args.max_len)
        print(f"fitted cap {args.cap:.3f} mm for a {args.max_len:.0f} mm budget")

    M, placed, width, added = layout(args.cap)
    top = max(M[p["ch"]]["top"] for p in placed)
    bot = min(M[p["ch"]]["bot"] for p in placed)
    spine_y = top + SPINE_CLR

    print(f"font {os.path.basename(FONT_PATH)} | cap {args.cap:.2f} mm | "
          f"depth {args.depth:.2f} mm | chamfer {args.chamfer:.2f} mm")
    print(f"text  {TEXT!r}")
    print(f"total {width:.2f} x {top - bot:.2f} mm, {len(placed)} letters "
          f"({'OK' if width <= args.max_len else 'OVER'} vs {args.max_len:.0f} mm limit) | "
          f"tracking added {added:.2f} mm")
    print(f"spine {spine_y:.2f}..{spine_y + SPINE_H:.2f} mm | "
          f"overall height {spine_y + SPINE_H - bot:.2f} mm")

    parts, est = [], 0.0
    if args.part in ("all", "letters"):
        for p in placed:
            m = M[p["ch"]]
            loops = orient([L + np.array([p["x"], 0.0]) for L in m["loops"]])
            T = extrude(loops, args.depth, args.chamfer)
            parts.append(T)
            area = abs(sum(signed_area(L) for L in loops))
            per = sum(np.linalg.norm(np.diff(np.vstack([L, L[:1]]), axis=0), axis=1).sum()
                      for L in loops)
            est += area * args.depth - per * args.chamfer ** 2 / 2
        print(f"letters: {len(placed)} shells, "
              f"{sum(len(t) for t in parts)} triangles")

    if args.part in ("all", "runner"):
        n0 = len(parts)
        parts.append(box(0.0, width, spine_y, spine_y + SPINE_H, 0.0, RAIL_Z))
        est += width * SPINE_H * RAIL_Z
        posts, nbridge = [], 0
        for p in placed:
            # highest part carries the post; lower parts hang off it. A second
            # post to a lower part would have to pass straight through the one
            # above (Impact's `i` dot overlaps its stem across the full width),
            # welding coincident faces and breaking manifoldness.
            g = sorted(M[p["ch"]]["gates"], key=lambda d: -d["top"])
            head = g[0]
            cx = p["x"] + (head["ga"] + head["gb"]) / 2
            pw = min(POST_W, max(0.35, (head["gb"] - head["ga"]) - 0.25))
            y_notch = head["top"] + NOTCH_H
            parts.append(box(cx - pw / 2, cx + pw / 2, y_notch, spine_y, 0.0, RAIL_Z))
            parts.append(box(cx - NOTCH_W / 2, cx + NOTCH_W / 2,
                             head["top"] - NOTCH_OVER, y_notch, 0.0, RAIL_Z))
            est += pw * max(0.0, spine_y - y_notch) * RAIL_Z
            est += NOTCH_W * (NOTCH_H + NOTCH_OVER) * RAIL_Z
            posts.append(spine_y - head["top"])

            for part in g[1:]:
                up = min((u for u in g if u["top"] > part["top"]
                          and min(u["ir"], part["ir"]) > max(u["il"], part["il"])),
                         key=lambda u: u["bot"], default=None)
                if up is None:
                    continue
                x0 = max(up["il"], part["il"]); x1 = min(up["ir"], part["ir"])
                bw = min(NOTCH_W, x1 - x0)
                bx = p["x"] + (x0 + x1) / 2
                parts.append(box(bx - bw / 2, bx + bw / 2,
                                 part["top"] - NOTCH_OVER, up["bot"] + NOTCH_OVER,
                                 0.0, BRIDGE_Z))
                est += bw * (up["bot"] - part["top"] + 2 * NOTCH_OVER) * BRIDGE_Z
                nbridge += 1

        print(f"runner : {len(parts) - n0} shells (1 spine + {len(placed)} posts "
              f"+ {len(placed)} notches + {nbridge} bridges), "
              f"post length {min(posts):.2f}..{max(posts):.2f} mm")
        multi = sorted({p["ch"] for p in placed if len(M[p["ch"]]["gates"]) > 1})
        if multi:
            print(f"         multi-part glyphs bridged at the back "
                  f"({BRIDGE_Z:.1f} mm deep, front {DEPTH - BRIDGE_Z:.1f} mm clear): "
                  f"{' '.join(multi)}")

    T = np.concatenate(parts).astype(np.float64)
    print("validation")
    validate(T, args.part, est)

    os.makedirs(args.out, exist_ok=True)
    suffix = {"all": "", "letters": "_letters", "runner": "_runner"}[args.part]
    path = os.path.join(args.out, f"{args.name}_label_{width:.0f}mm{suffix}.stl")
    write_stl(T, path, f"{args.name} label {args.part}")
    print(f"written {path}  ({os.path.getsize(path)/1e6:.2f} MB, {len(T)} triangles)")


if __name__ == "__main__":
    main()
