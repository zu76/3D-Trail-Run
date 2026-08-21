#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rilievo3d_v1.py — Approach A: generates a printable 3D STL model of a mountain
relief with the GPS track incised into the surface.

This is version 1 of the pipeline (approach A — incised track). The final
validated model was 180 mm, approach A v3. See docs/project_handoff.md §3 for
the full history and parameters.

Approach B (two-piece inlay) is implemented in rilievo3d_intarsio.py.

TYPICAL USAGE
-------------
1) Preview phase (choose framing by looking at PNG previews):
       python3 rilievo3d_v1.py --gpx traccia.gpx --preview
   -> prints the track bounding box and generates 'preview_inquadratura.png'
      with the track on a shaded relief and a centre grid.
   Adjust --bbox / --pad until the composition looks right.

2) STL generation:
       python3 rilievo3d_v1.py --gpx traccia.gpx \
           --bbox 45.7010 45.8988 6.7880 7.0713 \
           --size 180 --vex 1.3 --plinth 12 \
           --out modello.stl

If --bbox is not provided, the bounding box is computed around the track using
--pad (margin fraction per side, default 0.25 = +25% per side).

DEPENDENCIES
------------
numpy, scipy, matplotlib (for previews). No external CAD library:
the mesh is written by hand as a watertight manifold binary STL.

ELEVATION DATA
--------------
SRTM 1 arcsecond tiles (~30 m) covering the area are required, in raw
big-endian .hgt format (3601x3601 int16), named NxxEyyy.hgt / SxxWyyy.hgt.
Place them in the folder given by --hgt-dir (default: current directory).
The script automatically mosaics the required tiles.
Original source (public GitHub mirror, European tiles):
    https://raw.githubusercontent.com/danielementary/Alpano/master/NxxEyyy.hgt
"""
import argparse, math, os, re, struct, sys
import numpy as np
from scipy import ndimage

# --------------------------------------------------------------------------- #
#  1. GPX READING
# --------------------------------------------------------------------------- #
def read_gpx(path):
    """Returns Nx3 array (lat, lon, ele). GPX elevation is used only to
    position the track in altitude along the surface, not to model the
    terrain (that comes from the DEM)."""
    txt = open(path, encoding="utf-8", errors="ignore").read()
    pts = re.findall(r'<trkpt lat="([-0-9.]+)" lon="([-0-9.]+)">\s*<ele>([-0-9.]+)</ele>', txt)
    if not pts:                      # fallback: trkpt without <ele>
        pts = [(a, b, "0") for a, b in re.findall(r'<trkpt lat="([-0-9.]+)" lon="([-0-9.]+)"', txt)]
    if not pts:
        sys.exit("No <trkpt> found in the GPX.")
    return np.array([[float(a), float(b), float(c)] for a, b, c in pts])


# --------------------------------------------------------------------------- #
#  2. DEM: mosaic of SRTM .hgt tiles + bilinear sampling
# --------------------------------------------------------------------------- #
class DEM:
    def __init__(self, lat0, lat1, lon0, lon1, hgt_dir="."):
        tiles_lat = range(int(math.floor(lat0)), int(math.floor(lat1)) + 1)
        tiles_lon = range(int(math.floor(lon0)), int(math.floor(lon1)) + 1)
        self.lat_s, self.lat_n = min(tiles_lat), max(tiles_lat) + 1
        self.lon_w, self.lon_e = min(tiles_lon), max(tiles_lon) + 1
        rows, cols = [], []
        for la in range(self.lat_n - 1, self.lat_s - 1, -1):    # top (north) down
            band = []
            for lo in range(self.lon_w, self.lon_e):
                band.append(self._load_tile(la, lo, hgt_dir))
            # adjacent tiles share one row/column: overlap by 1
            rows.append(np.concatenate([band[0]] + [b[:, 1:] for b in band[1:]], axis=1))
        self.H = np.concatenate([rows[0]] + [r[1:, :] for r in rows[1:]], axis=0)
        # fill any voids with nearest neighbour
        if np.isnan(self.H).any():
            m = np.isnan(self.H)
            idx = ndimage.distance_transform_edt(m, return_distances=False, return_indices=True)
            self.H = self.H[tuple(idx)]
        self.NR, self.NC = self.H.shape

    @staticmethod
    def _load_tile(lat, lon, hgt_dir):
        name = "%s%02d%s%03d.hgt" % ("N" if lat >= 0 else "S", abs(lat),
                                     "E" if lon >= 0 else "W", abs(lon))
        p = os.path.join(hgt_dir, name)
        if not os.path.exists(p):
            sys.exit("Missing tile: %s  (download it to %s)" % (name, hgt_dir))
        a = np.fromfile(p, dtype=">i2").astype(np.float32).reshape(3601, 3601)
        a[a < -1000] = np.nan
        return a

    def sample(self, lats, lons):
        """Bilinear interpolation. row0 = northernmost latitude of the mosaic."""
        r = np.clip((self.lat_n - np.asarray(lats)) * 3600.0, 0, self.NR - 1 - 1e-6)
        c = np.clip((np.asarray(lons) - self.lon_w) * 3600.0, 0, self.NC - 1 - 1e-6)
        r0 = np.floor(r).astype(int); c0 = np.floor(c).astype(int)
        fr = r - r0; fc = c - c0
        r1 = r0 + 1; c1 = c0 + 1
        H = self.H
        return (H[r0, c0] * (1 - fr) * (1 - fc) + H[r1, c0] * fr * (1 - fc)
              + H[r0, c1] * (1 - fr) * fc + H[r1, c1] * fr * fc)

    def grid(self, lat0, lat1, lon0, lon1, n):
        """Samples a regular grid. n = number of cells on the long side.
        Returns Z (ny,nx) and (W,H,nx,ny) with W,H in metres (local projection)."""
        R = 6371000.0; latm = (lat0 + lat1) / 2
        W = math.radians(lon1 - lon0) * R * math.cos(math.radians(latm))
        Hm = math.radians(lat1 - lat0) * R
        if W >= Hm:
            nx = n; ny = max(2, int(round(n * Hm / W)))
        else:
            ny = n; nx = max(2, int(round(n * W / Hm)))
        LO, LA = np.meshgrid(np.linspace(lon0, lon1, nx),
                             np.linspace(lat1, lat0, ny))   # row0 = north
        return self.sample(LA, LO), (W, Hm, nx, ny)


# --------------------------------------------------------------------------- #
#  3. UTILITIES
# --------------------------------------------------------------------------- #
def densify(trk, step_m=10.0):
    """Densifies the track polyline to step <= step_m, so the groove remains
    continuous even where GPS has signal gaps."""
    seg = []
    for k in range(len(trk) - 1):
        p, q = trk[k, :2], trk[k + 1, :2]
        dm = max(abs(q[0] - p[0]) * 111200, abs(q[1] - p[1]) * 77600)
        m = max(1, int(dm // step_m))
        t = np.linspace(0, 1, m, endpoint=False)[:, None]
        seg.append(p + (q - p) * t)
    seg.append(trk[-1:, :2])
    return np.concatenate(seg)


def bbox_from_track(trk, pad):
    """Square bounding box around the track, with margin 'pad' per side."""
    la0, la1 = trk[:, 0].min(), trk[:, 0].max()
    lo0, lo1 = trk[:, 1].min(), trk[:, 1].max()
    dla, dlo = la1 - la0, lo1 - lo0
    la0 -= dla * pad; la1 += dla * pad
    lo0 -= dlo * pad; lo1 += dlo * pad
    # make square in metres
    latm = (la0 + la1) / 2
    Wm = (lo1 - lo0) * math.cos(math.radians(latm))
    Hm = (la1 - la0)
    if Wm > Hm:
        extra = (Wm - Hm) / 2
        la0 -= extra; la1 += extra
    else:
        extra = (Hm - Wm) / 2 / max(math.cos(math.radians(latm)), 1e-6)
        lo0 -= extra; lo1 += extra
    return la0, la1, lo0, lo1


# --------------------------------------------------------------------------- #
#  4. MESH CONSTRUCTION -> binary STL
# --------------------------------------------------------------------------- #
def build(dem, trk, lat0, lat1, lon0, lon1, size_mm, n,
          plinth, vex, g_flat, g_taper, g_depth, smooth, out):
    Z, (W, Hm, nx, ny) = dem.grid(lat0, lat1, lon0, lon1, n)
    Z = ndimage.gaussian_filter(Z, smooth)
    scale = size_mm / max(W, Hm)                 # mm per metre
    cell = (W / (nx - 1)) * scale                # mm per cell
    zmin = Z.min()
    Ztop = (Z - zmin) * scale * vex + plinth

    # --- incised track groove ---
    den = densify(trk)
    col = (den[:, 1] - lon0) / (lon1 - lon0) * (nx - 1)
    row = (lat1 - den[:, 0]) / (lat1 - lat0) * (ny - 1)
    mask = np.ones((ny, nx), bool)
    ri = np.clip(np.round(row).astype(int), 0, ny - 1)
    ci = np.clip(np.round(col).astype(int), 0, nx - 1)
    mask[ri, ci] = False
    dist = ndimage.distance_transform_edt(mask) * cell        # mm from track centre
    prof = np.clip((g_flat + g_taper - dist) / g_taper, 0.0, 1.0)
    Ztop = Ztop - g_depth * prof

    # --- surface vertices ---
    xs = np.linspace(0, W * scale, nx)
    ys = np.linspace(Hm * scale, 0, ny)          # row0 = north = maximum y
    X, Y = np.meshgrid(xs, ys)
    Vg = np.stack([X, Y, Ztop], -1)              # (ny,nx,3)

    tris = []
    i, j = np.meshgrid(np.arange(ny - 1), np.arange(nx - 1), indexing="ij")
    a = Vg[i, j]; b = Vg[i, j + 1]; c = Vg[i + 1, j + 1]; d = Vg[i + 1, j]
    tris.append(np.stack([a, c, b], -2).reshape(-1, 3, 3))    # surface, normal +z
    tris.append(np.stack([a, d, c], -2).reshape(-1, 3, 3))

    # --- vertical walls (normals outward) ---
    def wall(top_pts):
        p = top_pts.copy()
        q = p.copy(); q[:, 2] = 0.0
        t1 = np.stack([p[:-1], q[1:], q[:-1]], -2)
        t2 = np.stack([p[:-1], p[1:], q[1:]], -2)
        return np.concatenate([t1, t2])
    # perimeter clockwise from above
    for p in [Vg[0, :], Vg[:, -1], Vg[-1, ::-1], Vg[::-1, 0]]:
        tris.append(wall(p))

    # --- flat bottom (fan from centre, normal -z) ---
    loop = np.concatenate([Vg[0, :-1], Vg[:-1, -1], Vg[-1, :0:-1], Vg[::-1, 0][:-1]]).copy()
    loop[:, 2] = 0.0
    ctr = np.array([xs.mean(), ys.mean(), 0.0])
    l2 = np.roll(loop, -1, axis=0)
    tris.append(np.stack([np.repeat(ctr[None], len(loop), 0), loop, l2], -2))

    T = np.concatenate(tris).astype(np.float32)

    # --- write binary STL ---
    nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.where(ln > 0, nrm / np.maximum(ln, 1e-12), 0).astype(np.float32)
    buf = np.zeros((len(T), 12), np.float32)
    buf[:, 0:3] = nrm; buf[:, 3:12] = T.reshape(-1, 9)
    rec = np.zeros(len(T), dtype=[("d", "<f4", 12), ("a", "<u2")]); rec["d"] = buf
    with open(out, "wb") as f:
        f.write(b"rilievo3d - SRTM 1arcsec + GPX track".ljust(80, b" "))
        f.write(struct.pack("<I", len(T)))
        rec.tofile(f)

    # --- report + volume check ---
    sv = np.einsum("ij,ij->i", T.astype(np.float64)[:, 0],
                   np.cross(T.astype(np.float64)[:, 1], T.astype(np.float64)[:, 2])).sum() / 6.0
    info = dict(W=W, Hm=Hm, nx=nx, ny=ny, scale=scale, cell=cell,
                zmin=zmin, zmax=float(Z.max()), Ztop=Ztop,
                relief=Ztop.max() - plinth + g_depth, htot=Ztop.max(),
                ntri=len(T), vol_cm3=sv / 1000.0, plinth=plinth, vex=vex)
    print("model %.1f x %.1f mm | cell %.3f mm (%.0f m terrain) | scale 1:%.0f"
          % (W * scale, Hm * scale, cell, W / (nx - 1), 1000 / scale))
    print("elevations %.0f-%.0f m | relief %.1f mm | plinth %.1f mm | total h %.1f mm"
          % (zmin, Z.max(), info["relief"], plinth, info["htot"]))
    print("triangles %d | volume %.1f cm3 | STL: %s" % (len(T), info["vol_cm3"], out))
    return info


def validate(out):
    """Independent check: manifold, orientation, Euler characteristic."""
    f = open(out, "rb"); f.read(80)
    n = struct.unpack("<I", f.read(4))[0]
    rec = np.fromfile(f, dtype=[("d", "<f4", 12), ("a", "<u2")], count=n)
    T = rec["d"][:, 3:12].reshape(-1, 3, 3)
    V = np.round(T.reshape(-1, 3), 4)
    uq, inv = np.unique(V, axis=0, return_inverse=True)
    idx = inv.reshape(-1, 3)
    de = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]])
    dir_k = de[:, 0].astype(np.int64) * len(uq) + de[:, 1]
    _, dc = np.unique(dir_k, return_counts=True)
    und = np.minimum(de[:, 0], de[:, 1]).astype(np.int64) * len(uq) + np.maximum(de[:, 0], de[:, 1])
    ue, uc = np.unique(und, return_counts=True)
    euler = len(uq) - len(ue) + n
    ok = (dc != 1).sum() == 0 and (uc != 2).sum() == 0 and euler == 2
    print("VALIDATE: incoherent_orient=%d  non-manifold=%d  Euler=%d  ->  %s"
          % ((dc != 1).sum(), (uc != 2).sum(), euler, "OK, closed solid" if ok else "PROBLEM"))
    return ok


# --------------------------------------------------------------------------- #
#  5. PREVIEWS (PNG)
# --------------------------------------------------------------------------- #
def preview_frame(dem, trk, lat0, lat1, lon0, lon1, png):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource
    Z, (W, Hm, gx, gy) = dem.grid(lat0, lat1, lon0, lon1, 1100)
    ls = LightSource(azdeg=315, altdeg=45)
    fig, ax = plt.subplots(figsize=(9, 9 * Hm / W), dpi=140)
    ax.imshow(ls.shade(Z, cmap=plt.cm.gist_earth, blend_mode="soft", vert_exag=1.5,
                       dx=W / gx, dy=Hm / gy), extent=[lon0, lon1, lat0, lat1], aspect="auto")
    ax.contour(np.linspace(lon0, lon1, gx), np.linspace(lat1, lat0, gy), Z,
               levels=np.arange(500, 4900, 250), colors="k", linewidths=.2, alpha=.3)
    ax.plot(trk[:, 1], trk[:, 0], color="#e10600", lw=1.6)
    ax.plot(trk[0, 1], trk[0, 0], "o", color="#0033cc", ms=6)
    ax.axvline((lon0 + lon1) / 2, color="k", lw=.5, ls=":")
    ax.axhline((lat0 + lat1) / 2, color="k", lw=.5, ls=":")
    ax.set_title("Framing %.1f x %.1f km  (grid = model centre)" % (W / 1000, Hm / 1000),
                 fontsize=9)
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout(); fig.savefig(png, dpi=140, bbox_inches="tight"); plt.close(fig)
    print("framing preview:", png)


def preview_model(info, png):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource
    Z = info["Ztop"]; cell = info["cell"]; ny, nx = Z.shape
    Wm = info["W"] * info["scale"]; Hm = info["Hm"] * info["scale"]
    ls = LightSource(azdeg=315, altdeg=45)
    fig = plt.figure(figsize=(15, 6.2), dpi=140)
    a1 = fig.add_subplot(131)
    a1.imshow(0.72 + 0.28 * ls.shade(Z, cmap=plt.cm.gray, blend_mode="overlay", dx=cell, dy=cell),
              extent=[0, Wm, 0, Hm]); a1.set_title("Top view (%.0f x %.0f mm)" % (Wm, Hm), fontsize=10)
    a1.set_xlabel("mm")
    a2 = fig.add_subplot(132, projection="3d", computed_zorder=False)
    s = 2
    X, Y = np.meshgrid(np.linspace(0, Wm, nx)[::s], np.linspace(Hm, 0, ny)[::s])
    Zs = Z[::s, ::s]
    a2.plot_surface(X, Y, Zs, facecolors=0.72 + 0.28 * ls.shade(Zs, cmap=plt.cm.gray,
                    blend_mode="overlay", dx=cell * s, dy=cell * s),
                    rstride=1, cstride=1, linewidth=0, antialiased=False, shade=False)
    a2.set_box_aspect((Wm, Hm, max(Z.max(), 1) * 2.4)); a2.view_init(elev=38, azim=-62); a2.set_axis_off()
    a2.set_title("3D preview", fontsize=10)
    a3 = fig.add_subplot(133)
    yc = int(ny * 0.5); xx = np.arange(nx) * cell
    a3.fill_between(xx, 0, Z[yc, :], color="#d8d3c8", ec="#5a5a5a", lw=.7)
    a3.axhline(info["plinth"], color="#d81e05", lw=1, ls="--")
    a3.set_aspect("equal"); a3.set_ylim(-2, Z.max() + 6)
    a3.set_title("Section: solid body (vex %.2gx)" % info["vex"], fontsize=10)
    a3.set_xlabel("mm"); a3.set_ylabel("mm"); a3.grid(alpha=.25)
    fig.tight_layout(); fig.savefig(png, dpi=140, facecolor="#f4f1eb"); plt.close(fig)
    print("model preview:", png)


# --------------------------------------------------------------------------- #
#  6. CLI
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="3D mountain relief + GPX track -> STL (approach A: incised)")
    ap.add_argument("--gpx", required=True)
    ap.add_argument("--hgt-dir", default=".", help="folder containing .hgt tiles")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("LAT0", "LAT1", "LON0", "LON1"),
                    help="explicit bounding box; if absent, computed around the track")
    ap.add_argument("--pad", type=float, default=0.25, help="margin per side if bbox is auto (fraction)")
    ap.add_argument("--size", type=float, default=180.0, help="long side of the model [mm]")
    ap.add_argument("--n", type=int, default=600, help="cells on the long side (mesh detail)")
    ap.add_argument("--vex", type=float, default=1.3, help="vertical exaggeration")
    ap.add_argument("--plinth", type=float, default=12.0, help="plinth below the minimum [mm]")
    ap.add_argument("--g-flat", type=float, default=0.35, help="groove flat-bottom half-width [mm]")
    ap.add_argument("--g-taper", type=float, default=0.35, help="groove taper [mm]")
    ap.add_argument("--g-depth", type=float, default=0.80, help="groove depth [mm]")
    ap.add_argument("--smooth", type=float, default=0.6, help="DEM Gaussian sigma [cells]")
    ap.add_argument("--out", default="modello.stl")
    ap.add_argument("--preview", action="store_true", help="framing preview only, no STL")
    args = ap.parse_args()

    trk = read_gpx(args.gpx)
    print("track: %d points | lat %.4f..%.4f lon %.4f..%.4f | ele %.0f..%.0f m"
          % (len(trk), trk[:, 0].min(), trk[:, 0].max(), trk[:, 1].min(), trk[:, 1].max(),
             trk[:, 2].min(), trk[:, 2].max()))

    if args.bbox:
        lat0, lat1, lon0, lon1 = args.bbox
    else:
        lat0, lat1, lon0, lon1 = bbox_from_track(trk, args.pad)
        print("auto bbox: %.4f %.4f %.4f %.4f" % (lat0, lat1, lon0, lon1))

    dem = DEM(lat0, lat1, lon0, lon1, args.hgt_dir)

    if args.preview:
        preview_frame(dem, trk, lat0, lat1, lon0, lon1, "preview_inquadratura.png")
        return

    preview_frame(dem, trk, lat0, lat1, lon0, lon1,
                  os.path.splitext(args.out)[0] + "_framing.png")
    info = build(dem, trk, lat0, lat1, lon0, lon1, args.size, args.n,
                 args.plinth, args.vex, args.g_flat, args.g_taper, args.g_depth,
                 args.smooth, args.out)
    validate(args.out)
    preview_model(info, os.path.splitext(args.out)[0] + "_model.png")


if __name__ == "__main__":
    main()
