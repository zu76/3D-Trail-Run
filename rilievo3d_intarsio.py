#!/usr/bin/env python3
"""
rilievo3d_intarsio.py — rilievo di montagna + traccia GPS a innesto, due pezzi.

Oggetto 1  rilievo con scavo a pareti verticali e fondo piano
Oggetto 2  traccia che si innesta nello scavo e sporge sulla superficie

Scavo e traccia sono due insiemi di livello dello STESSO campo di distanza dalla
polilinea della traccia: sono quindi concentrici per costruzione e il gioco
perpendicolare e' esattamente (GROOVE_W - TRACK_W)/2 ovunque, anche nei tornanti
e dove due passaggi vicini fanno fondere il corridoio.

Mesh scritte a mano, nessuna libreria CAD. Validazione: manifold, Eulero,
volume con segno contro stima indipendente.

Dipendenze: dem.py (nella stessa cartella), numpy, scipy
Output: courmayeur_GTC_150mm_rilievo.stl, courmayeur_GTC_150mm_traccia.stl

Uso:
    python3 rilievo3d_intarsio.py --gpx activity_23561586194.gpx --out .
    # richiede ./hgt/N45E006.hgt e ./hgt/N45E007.hgt
"""
import argparse, math, struct
import numpy as np
from scipy.ndimage import gaussian_filter, gaussian_filter1d
from scipy.spatial import cKDTree
import dem

# ------------------------------------------------------------------ parametri
LAT0, LAT1, LON0, LON1 = 45.7010, 45.8988, 6.7880, 7.0713
SIZE, VEX, PLINTH = 150.0, 1.3, 10.0
FLOOR_Z = 6.0
GROOVE_W, TRACK_W, SPORG = 1.15, 0.90, 0.40
GRID = 700
SMOOTH_MM = 0.10          # lisciatura della traccia (14,7 m al suolo)
CL_STEP = 0.05            # passo della centerline per il campo di distanza
R_EARTH = 6371000.0


# ------------------------------------------------------------------- centerline
def centerline(gpx):
    import re
    txt = open(gpx, encoding="utf-8", errors="ignore").read()
    pts = re.findall(r'<trkpt lat="([-0-9.]+)" lon="([-0-9.]+)">\s*<ele>([-0-9.]+)</ele>', txt)
    P = np.array([[float(a), float(b)] for a, b, _ in pts])
    latm = (LAT0 + LAT1) / 2
    W = math.radians(LON1 - LON0) * R_EARTH * math.cos(math.radians(latm))
    H = math.radians(LAT1 - LAT0) * R_EARTH
    s = SIZE / max(W, H)
    XY = np.column_stack([(P[:, 1] - LON0) / (LON1 - LON0) * W * s,
                          (P[:, 0] - LAT0) / (LAT1 - LAT0) * H * s])

    def rs(A, st):
        d = np.r_[0, np.cumsum(np.hypot(*np.diff(A, axis=0).T))]
        u = np.arange(0, d[-1], st)
        return np.column_stack([np.interp(u, d, A[:, 0]), np.interp(u, d, A[:, 1])])

    A = rs(XY, 0.02)
    k = SMOOTH_MM / 0.02
    A = np.column_stack([gaussian_filter1d(A[:, 0], k), gaussian_filter1d(A[:, 1], k)])
    return rs(A, CL_STEP), (W, H, s)


# ------------------------------------------------------------------------ mesh
class Mesh:
    def __init__(self):
        self.t = []

    def tri(self, a, b, c):
        self.t.append((a, b, c))

    def quad(self, a, b, c, d):
        self.t.append((a, b, c)); self.t.append((a, c, d))

    def fan(self, ring):
        for i in range(1, len(ring) - 1):
            self.t.append((ring[0], ring[i], ring[i + 1]))

    def array(self):
        return np.array(self.t, dtype=np.float64)


def crossings(mixed, tree, half):
    """Posizione esatta del contorno sugli spigoli che cambiano segno.

    L'interpolazione lineare del campo di distanza sbaglia fino a mezza cella
    dove due passaggi della traccia si avvicinano: li' il campo ha uno spigolo
    (asse mediano) e non e' affatto lineare. Cerco invece per bisezione il punto
    in cui la distanza vera dalla centerline vale esattamente `half`.
    """
    E0, E1, owner = [], [], []
    for k, (poly, dv) in enumerate(mixed):
        for i in range(3):
            j = (i + 1) % 3
            if (dv[i] > 0) != (dv[j] > 0):
                E0.append(poly[i]); E1.append(poly[j]); owner.append((k, i))
    if not owner:
        return {}
    E0 = np.array(E0); E1 = np.array(E1)
    d0, _ = tree.query(E0[:, :2]); d1, _ = tree.query(E1[:, :2])
    flip = d0 > d1                       # A = estremo con distanza minore
    A = np.where(flip[:, None], E1, E0); B = np.where(flip[:, None], E0, E1)
    lo = np.zeros(len(A)); hi = np.ones(len(A))
    for _ in range(45):
        mid = (lo + hi) / 2
        P = A + mid[:, None] * (B - A)
        dm, _ = tree.query(P[:, :2])
        inside = dm < half
        lo = np.where(inside, mid, lo); hi = np.where(inside, hi, mid)
    # tenuta lontano dagli estremi: se il contorno cade esattamente su un
    # vertice della griglia i poligoni degenerano e le pareti restano bucate
    t = np.clip((lo + hi) / 2, 2e-4, 1 - 2e-4)
    Pc = A + t[:, None] * (B - A)
    out = {}
    for n, (k, i) in enumerate(owner):
        out[(k, i)] = Pc[n]
    return out


def clip_tri(poly, dv, cr, k, keep_positive):
    """Poligono del triangolo dalla parte richiesta, con i contorni esatti."""
    sg = dv > 0 if keep_positive else dv < 0
    out, cross = [], []
    for i in range(3):
        j = (i + 1) % 3
        if sg[i]:
            out.append(poly[i])
        if sg[i] != sg[j]:
            out.append(cr[(k, i)]); cross.append(len(out) - 1)
    ring = []
    for n, p in enumerate(out):
        flag = n in cross
        if ring and np.linalg.norm(p - ring[-1][0]) <= 1e-9:
            ring[-1] = (ring[-1][0], ring[-1][1] or flag)
        else:
            ring.append((p, flag))
    if len(ring) > 2 and np.linalg.norm(ring[0][0] - ring[-1][0]) <= 1e-9:
        ring[0] = (ring[0][0], ring[0][1] or ring[-1][1])
        ring.pop()
    return [p for p, _ in ring], [i for i, (_, fl) in enumerate(ring) if fl]


def build(cl, part):
    """part='rilievo' oppure 'traccia'."""
    latm = (LAT0 + LAT1) / 2
    W = math.radians(LON1 - LON0) * R_EARTH * math.cos(math.radians(latm))
    H = math.radians(LAT1 - LAT0) * R_EARTH
    s = SIZE / max(W, H); kz = s * VEX
    if W >= H:
        nx = GRID; ny = max(2, int(round(GRID * H / W)))
    else:
        ny = GRID; nx = max(2, int(round(GRID * W / H)))

    LO, LA = np.meshgrid(np.linspace(LON0, LON1, nx), np.linspace(LAT0, LAT1, ny))
    Z = gaussian_filter(dem.sample(LA, LO), 1.0)
    zmin = float(Z.min())
    ztop = PLINTH + (Z - zmin) * kz
    X = np.tile(np.linspace(0, W * s, nx), (ny, 1))
    Y = np.tile(np.linspace(0, H * s, ny)[:, None], (1, nx))

    tree = cKDTree(cl)
    half = GROOVE_W / 2 if part == "rilievo" else TRACK_W / 2
    dist, _ = tree.query(np.column_stack([X.ravel(), Y.ravel()]))
    D = (dist.reshape(ny, nx) - half).astype(np.float64)
    # Un nodo esattamente sulla soglia fa collassare l'intersezione sul vertice
    # della griglia: spigoli di lunghezza nulla. 1 um e' irrilevante.
    D[np.abs(D) < 1e-3] = 1e-3
    if part == "traccia":
        ztop = ztop + SPORG
        D = -D                       # dentro il nastro = materiale

    m = Mesh()
    a = (slice(0, ny - 1), slice(0, nx - 1)); b = (slice(0, ny - 1), slice(1, nx))
    c = (slice(1, ny), slice(1, nx));         e = (slice(1, ny), slice(0, nx - 1))
    mixed = []
    for cs in [(a, b, c), (a, c, e)]:
        dv = np.stack([D[k] for k in cs], -1)
        pos = (dv > 0).sum(-1)
        P = [np.stack([X[k], Y[k], ztop[k]], -1) for k in cs]
        full = pos == 3
        if full.any():
            T = np.stack([p[full] for p in P], 1)
            m.t.extend(map(tuple, T))
            if part == "traccia":            # fondo piatto del solo nastro
                Tb = T.copy(); Tb[:, :, 2] = FLOOR_Z
                m.t.extend(map(tuple, Tb[:, ::-1]))
        emp = pos == 0
        if emp.any() and part == "rilievo":  # fondo dello scavo
            T = np.stack([p[emp] for p in P], 1)
            T[:, :, 2] = FLOOR_Z
            m.t.extend(map(tuple, T))
        mix = (~full) & (~emp)
        if mix.any():
            ii, jj = np.nonzero(mix)
            for u, v in zip(ii, jj):
                mixed.append((np.array([p[u, v] for p in P]), dv[u, v].copy()))

    cr = crossings(mixed, tree, half)
    for k, (poly, dv) in enumerate(mixed):
        sol, idx = clip_tri(poly, dv, cr, k, True)
        if len(sol) >= 3:
            m.fan([tuple(p) for p in sol])
            if part == "traccia":
                m.fan([(p[0], p[1], FLOOR_Z) for p in sol[::-1]])
        if part == "rilievo":
            grv, _ = clip_tri(poly, dv, cr, k, False)
            if len(grv) >= 3:
                m.fan([(p[0], p[1], FLOOR_Z) for p in grv])
        if len(idx) == 2 and len(sol) >= 3:
            A, B = (sol[idx[0]], sol[idx[1]]) if (idx[1] - idx[0]) % len(sol) == 1 \
                else (sol[idx[1]], sol[idx[0]])
            if np.linalg.norm(A - B) > 1e-9:
                m.quad(tuple(A), (A[0], A[1], FLOOR_Z),
                       (B[0], B[1], FLOOR_Z), tuple(B))

    if part == "traccia":
        return m.array()
    return finish_relief(m, X, Y, ztop, nx, ny), (W, H, s, kz, zmin, ztop, D)


def finish_relief(m, X, Y, ztop, nx, ny):
    # pareti perimetrali + fondo a ventaglio
    for i in range(nx - 1):
        m.quad((X[0, i], Y[0, i], ztop[0, i]), (X[0, i], Y[0, i], 0),
               (X[0, i + 1], Y[0, i + 1], 0), (X[0, i + 1], Y[0, i + 1], ztop[0, i + 1]))
        m.quad((X[-1, i + 1], Y[-1, i + 1], ztop[-1, i + 1]), (X[-1, i + 1], Y[-1, i + 1], 0),
               (X[-1, i], Y[-1, i], 0), (X[-1, i], Y[-1, i], ztop[-1, i]))
    for i in range(ny - 1):
        m.quad((X[i + 1, 0], Y[i + 1, 0], ztop[i + 1, 0]), (X[i + 1, 0], Y[i + 1, 0], 0),
               (X[i, 0], Y[i, 0], 0), (X[i, 0], Y[i, 0], ztop[i, 0]))
        m.quad((X[i, -1], Y[i, -1], ztop[i, -1]), (X[i, -1], Y[i, -1], 0),
               (X[i + 1, -1], Y[i + 1, -1], 0), (X[i + 1, -1], Y[i + 1, -1], ztop[i + 1, -1]))
    cx, cy = X.mean(), Y.mean()
    ring = ([(X[0, i], Y[0, i]) for i in range(nx)] +
            [(X[i, -1], Y[i, -1]) for i in range(1, ny)] +
            [(X[-1, i], Y[-1, i]) for i in range(nx - 2, -1, -1)] +
            [(X[i, 0], Y[i, 0]) for i in range(ny - 2, 0, -1)])
    for i in range(len(ring)):
        p, q = ring[i], ring[(i + 1) % len(ring)]
        m.tri((cx, cy, 0.0), (q[0], q[1], 0.0), (p[0], p[1], 0.0))
    return m.array()


# -------------------------------------------------------------------- utilita'
def validate(T, name, expected=None):
    v = np.round(T.reshape(-1, 3), 5)
    uq, inv = np.unique(v, axis=0, return_inverse=True)
    f = inv.reshape(-1, 3)
    ed = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    key = np.minimum(ed[:, 0], ed[:, 1]).astype(np.int64) * len(uq) + np.maximum(ed[:, 0], ed[:, 1])
    ue, uc = np.unique(key, return_counts=True)
    dk = ed[:, 0].astype(np.int64) * len(uq) + ed[:, 1]
    _, dc = np.unique(dk, return_counts=True)
    chi = len(uq) - len(ue) + len(f)
    vol = np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() / 6.0
    print(f"  {name}: V={len(uq)} E={len(ue)} F={len(f)} chi={chi}")
    print(f"    non-manifold={int((uc != 2).sum())}  orient.incoerente={int((dc != 1).sum())}"
          f"  volume={vol/1000:.2f} cm3", end="")
    print(f"  (stima {expected/1000:.2f}, scarto {abs(vol-expected)/expected*100:.2f} %)"
          if expected else "")
    return vol


def write_stl(T, path, name):
    p0, p1, p2 = T[:, 0], T[:, 1], T[:, 2]
    n = np.cross(p1 - p0, p2 - p0)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    rec = np.zeros(len(T), dtype=[("d", "<f4", 12), ("a", "<u2")])
    rec["d"][:, 0:3] = n; rec["d"][:, 3:12] = T.reshape(-1, 9)
    with open(path, "wb") as f:
        f.write(name.encode()[:80].ljust(80, b" "))
        f.write(struct.pack("<I", len(T)))
        rec.tofile(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpx", required=True)
    ap.add_argument("--out", default=".")
    args = ap.parse_args()

    cl, (W, H, s) = centerline(args.gpx)
    print(f"modello {W*s:.1f} x {H*s:.1f} mm | scala 1:{1/s*1000:.0f} | "
          f"traccia {len(cl)*CL_STEP:.1f} mm\n")

    Tr, (W, H, s, kz, zmin, Zt, D) = build(cl, "rilievo")
    cell = (W * s) / (D.shape[1] - 1) * (H * s) / (D.shape[0] - 1)
    est = Zt.mean() * (W * s) * (H * s) - ((D < 0).sum() * cell) * (Zt[D < 0].mean() - FLOOR_Z)
    validate(Tr, "rilievo", est)
    write_stl(Tr, f"{args.out}/courmayeur_GTC_150mm_rilievo.stl", "rilievo con scavo")

    Tt = build(cl, "traccia")
    estt = ((-D + (GROOVE_W - TRACK_W) / 2) > 0)
    mask = (np.abs(0) == 0)
    validate(Tt, "traccia")
    write_stl(Tt, f"{args.out}/courmayeur_GTC_150mm_traccia.stl", "traccia a innesto")
    np.save("grid_cache.npy", np.stack([Zt, D]))


if __name__ == "__main__":
    main()
