#!/usr/bin/env python3
"""
provino_taratura.py — Provino di taratura per il modello rilievo + traccia a innesto.

Genera due STL:
  provino_piastra.stl  piastra con 5 scavi sinusoidali di larghezza crescente + 1 tornante
  provino_tracce.stl   6 spezzoni di traccia (larghezza fissa) nelle stesse coordinate XY

Scopo: determinare sperimentalmente quale larghezza di scavo accetta una traccia
di larghezza nominale TRACK_W stampata sulla propria stampante, sia su parete
curva (sinusoidi) sia in tornante stretto.

Pipeline coerente con rilievo3d.py: numpy puro, mesh costruite esplicitamente
con normali uscenti, validazione manifold + Eulero + volume con segno.
"""

import numpy as np
import struct
import argparse

# --------------------------------------------------------------------------
# PARAMETRI
# --------------------------------------------------------------------------
PLATE_X, PLATE_Y, PLATE_Z = 70.0, 52.0, 11.0
GROOVE_DEPTH = 8.0
FLOOR_Z = PLATE_Z - GROOVE_DEPTH          # 3.0 mm di base sotto lo scavo

TRACK_W    = 0.90                          # larghezza traccia (fissa)
SPORGENZA  = 0.40                          # sporgenza sul piano della piastra
CH_BOT_H, CH_BOT_S = 0.20, 0.10            # smusso di base (h, arretramento)
CH_TOP_H, CH_TOP_S = 0.20, 0.20            # smusso di sommita'

AMP, LAM = 1.8, 18.0                       # ampiezza e periodo della sinusoide

# (larghezza scavo, y di riferimento, x di inizio scavo cieco)
WAVY = [
    (1.05, 46.0, 26.0),
    (1.10, 39.0, 22.0),
    (1.15, 32.0, 18.0),
    (1.20, 25.0, 14.0),
    (1.25, 18.0, 10.0),
]
HP_W, HP_CX, HP_CY, HP_R = 1.10, 16.0, 8.0, 2.0   # tornante

INSERT_GAP, INSERT_X1 = 0.5, 69.5          # franco al fondo cieco, fine spezzone
DS = 0.4                                    # passo di campionamento [mm]
EPS = 1e-7


# --------------------------------------------------------------------------
# GEOMETRIA 2D
# --------------------------------------------------------------------------
def wave_path(x0, x1, y_ref, ds=DS):
    """Sinusoide con fase tale da avere tangente orizzontale in x = PLATE_X."""
    n = max(2, int(round((x1 - x0) / ds)) + 1)
    x = np.linspace(x0, x1, n)
    k = 2.0 * np.pi / LAM
    y = y_ref + AMP * np.cos(k * (x - PLATE_X))
    dy = -AMP * k * np.sin(k * (x - PLATE_X))
    t = np.stack([np.ones_like(x), dy], axis=1)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    return np.stack([x, y], axis=1), t


def hairpin_path(x_end, ds=DS):
    """Tornante: gamba bassa da destra, arco a sinistra, gamba alta verso destra."""
    n_leg = max(2, int(round((x_end - HP_CX) / ds)) + 1)
    n_arc = max(6, int(round(np.pi * HP_R / ds)) + 1)

    x_in = np.linspace(x_end, HP_CX, n_leg)
    p1 = np.stack([x_in, np.full_like(x_in, HP_CY - HP_R)], axis=1)
    t1 = np.tile([-1.0, 0.0], (n_leg, 1))

    a = np.linspace(-np.pi / 2, -3 * np.pi / 2, n_arc)          # senso orario
    p2 = np.stack([HP_CX + HP_R * np.cos(a), HP_CY + HP_R * np.sin(a)], axis=1)
    t2 = np.stack([np.sin(a), -np.cos(a)], axis=1)

    x_out = np.linspace(HP_CX, x_end, n_leg)
    p3 = np.stack([x_out, np.full_like(x_out, HP_CY + HP_R)], axis=1)
    t3 = np.tile([1.0, 0.0], (n_leg, 1))

    p = np.vstack([p1[:-1], p2, p3[1:]])
    t = np.vstack([t1[:-1], t2, t3[1:]])
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    return p, t


def offsets(p, t, h):
    """Offset normali sinistro (+h) e destro (-h)."""
    nrm = np.stack([-t[:, 1], t[:, 0]], axis=1)
    return p + h * nrm, p - h * nrm


def shoelace(poly):
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)


def as_ccw(poly):
    return poly if shoelace(poly) > 0 else poly[::-1].copy()


# --------------------------------------------------------------------------
# TRIANGOLAZIONE DI POLIGONI SEMPLICI (ear clipping)
# --------------------------------------------------------------------------
def ear_clip(poly):
    """Poligono semplice CCW -> lista di triangoli (indici sui vertici dati)."""
    n = len(poly)
    idx = list(range(n))
    tris = []
    guard = 0
    while len(idx) > 3:
        guard += 1
        if guard > 4 * n:
            raise RuntimeError("ear clipping bloccato")
        clipped = False
        m = len(idx)
        for i in range(m):
            ia, ib, ic = idx[(i - 1) % m], idx[i], idx[(i + 1) % m]
            a, b, c = poly[ia], poly[ib], poly[ic]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= EPS:
                continue                                  # riflesso o degenere
            others = np.array([poly[j] for j in idx if j not in (ia, ib, ic)])
            if len(others) and _any_inside(a, b, c, others):
                continue
            tris.append((ia, ib, ic))
            idx.pop(i)
            clipped = True
            break
        if not clipped:
            raise RuntimeError("nessuna orecchia trovata: poligono non semplice")
    tris.append(tuple(idx))
    return tris


def _any_inside(a, b, c, pts):
    d1 = (b[0] - a[0]) * (pts[:, 1] - a[1]) - (b[1] - a[1]) * (pts[:, 0] - a[0])
    d2 = (c[0] - b[0]) * (pts[:, 1] - b[1]) - (c[1] - b[1]) * (pts[:, 0] - b[0])
    d3 = (a[0] - c[0]) * (pts[:, 1] - c[1]) - (a[1] - c[1]) * (pts[:, 0] - c[0])
    return np.any((d1 >= -EPS) & (d2 >= -EPS) & (d3 >= -EPS))


# --------------------------------------------------------------------------
# ACCUMULATORE DI MESH
# --------------------------------------------------------------------------
class Mesh:
    def __init__(self):
        self.tris = []

    def tri(self, a, b, c):
        self.tris.append((np.asarray(a, float), np.asarray(b, float),
                          np.asarray(c, float)))

    def quad(self, a, b, c, d):
        self.tri(a, b, c)
        self.tri(a, c, d)

    def array(self):
        return np.array(self.tris, dtype=np.float64)


def wall_strip(mesh, loop, z_top, z_bot, skip_right_edge=False):
    """Parete verticale sotto un anello percorso con il materiale a sinistra."""
    n = len(loop)
    for i in range(n):
        a, b = loop[i], loop[(i + 1) % n]
        if skip_right_edge and a[0] > PLATE_X - 1e-6 and b[0] > PLATE_X - 1e-6:
            continue
        at, bt = (a[0], a[1], z_top), (b[0], b[1], z_top)
        ab, bb = (a[0], a[1], z_bot), (b[0], b[1], z_bot)
        mesh.quad(at, ab, bb, bt)


# --------------------------------------------------------------------------
# VALIDAZIONE
# --------------------------------------------------------------------------
def validate(tris, name, expected_volume=None, n_shells=1):
    v = tris.reshape(-1, 3)
    key = np.round(v, 6)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    f = inv.reshape(-1, 3)

    edges = {}
    for t in f:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            e = (min(a, b), max(a, b))
            edges[e] = edges.get(e, 0) + 1
    bad = sum(1 for c in edges.values() if c != 2)

    V, E, F = len(uniq), len(edges), len(f)
    chi = V - E + F

    p0, p1, p2 = tris[:, 0], tris[:, 1], tris[:, 2]
    vol = np.sum(np.einsum('ij,ij->i', p0, np.cross(p1, p2))) / 6.0

    print(f"  {name}")
    print(f"    V={V}  E={E}  F={F}   chi={chi} (atteso {2 * n_shells})")
    print(f"    spigoli non manifold: {bad}")
    print(f"    volume con segno: {vol / 1000.0:.4f} cm^3", end="")
    if expected_volume is not None:
        err = abs(vol - expected_volume) / expected_volume * 100
        print(f"   (atteso {expected_volume / 1000.0:.4f}, scarto {err:.3f} %)")
    else:
        print()
    ok = (bad == 0) and (chi == 2 * n_shells) and (vol > 0)
    print(f"    esito: {'OK' if ok else 'ATTENZIONE'}")
    return ok


def write_stl(tris, path, name="mesh"):
    p0, p1, p2 = tris[:, 0], tris[:, 1], tris[:, 2]
    nrm = np.cross(p1 - p0, p2 - p0)
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.divide(nrm, ln, out=np.zeros_like(nrm), where=ln > 0)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<80sI", name.encode()[:80].ljust(80, b"\0"),
                             len(tris)))
        buf = bytearray()
        for i in range(len(tris)):
            buf += struct.pack("<12fH", *nrm[i], *p0[i], *p1[i], *p2[i], 0)
        fh.write(buf)


# --------------------------------------------------------------------------
# PIASTRA
# --------------------------------------------------------------------------
def build_plate():
    mesh = Mesh()
    grooves = []          # (loop_ccw, left, right)  loop = anello del canale

    for w, y_ref, x0 in WAVY:
        p, t = wave_path(x0, PLATE_X, y_ref)
        L, R = offsets(p, t, w / 2.0)
        loop = as_ccw(np.vstack([L, R[::-1]]))
        grooves.append((loop, L, R))

    p, t = hairpin_path(PLATE_X)
    L, R = offsets(p, t, HP_W / 2.0)
    loop = as_ccw(np.vstack([L, R[::-1]]))
    grooves.append((loop, L, R))
    hp_inner = R

    # --- fondo di ogni scavo (quad strip, normale +Z) + pareti ---
    groove_area = 0.0
    for loop, L, R in grooves:
        for i in range(len(L) - 1):
            mesh.quad((R[i, 0], R[i, 1], FLOOR_Z),
                      (R[i + 1, 0], R[i + 1, 1], FLOOR_Z),
                      (L[i + 1, 0], L[i + 1, 1], FLOOR_Z),
                      (L[i, 0], L[i, 1], FLOOR_Z))
        wall_strip(mesh, loop[::-1], PLATE_Z, FLOOR_Z, skip_right_edge=True)
        groove_area += abs(shoelace(loop))

    # --- faccia superiore: pettine + isola del tornante ---
    bites = []
    for (w, y_ref, x0), (loop, L, R) in zip(WAVY, grooves[:5]):
        bites.append((R[-1, 1], np.vstack([R[::-1], L])))
    hp_L = grooves[5][1]
    bites.append((hp_L[0, 1], hp_L))
    bites.sort(key=lambda b: b[0])

    comb = [np.array([0.0, 0.0]), np.array([PLATE_X, 0.0])]
    for _, pts in bites:
        comb.extend(list(pts))
    comb.extend([np.array([PLATE_X, PLATE_Y]), np.array([0.0, PLATE_Y])])
    comb = _dedupe(np.array(comb))
    comb = as_ccw(comb)

    for ia, ib, ic in ear_clip(comb):
        mesh.tri((comb[ia, 0], comb[ia, 1], PLATE_Z),
                 (comb[ib, 0], comb[ib, 1], PLATE_Z),
                 (comb[ic, 0], comb[ic, 1], PLATE_Z))

    tongue = _dedupe(np.vstack([hp_inner, [[PLATE_X, hp_inner[0, 1]]]]))
    tongue = as_ccw(tongue)
    for ia, ib, ic in ear_clip(tongue):
        mesh.tri((tongue[ia, 0], tongue[ia, 1], PLATE_Z),
                 (tongue[ib, 0], tongue[ib, 1], PLATE_Z),
                 (tongue[ic, 0], tongue[ic, 1], PLATE_Z))

    # --- fondo della piastra (normale -Z) ---
    mesh.quad((0, 0, 0), (0, PLATE_Y, 0), (PLATE_X, PLATE_Y, 0), (PLATE_X, 0, 0))

    # --- facce laterali ---
    mesh.quad((0, 0, 0), (PLATE_X, 0, 0), (PLATE_X, 0, PLATE_Z), (0, 0, PLATE_Z))
    mesh.quad((PLATE_X, PLATE_Y, 0), (0, PLATE_Y, 0),
              (0, PLATE_Y, PLATE_Z), (PLATE_X, PLATE_Y, PLATE_Z))
    mesh.quad((0, PLATE_Y, 0), (0, 0, 0), (0, 0, PLATE_Z), (0, PLATE_Y, PLATE_Z))

    # faccia destra: unico poligono a pettine nel piano (y, z), triangolato.
    # Trattarla come quad separati creerebbe T-junction sui bordi condivisi
    # con la faccia inferiore e con quelle a y = 0 e y = PLATE_Y.
    openings = []
    for loop, L, R in grooves[:5]:
        openings.append((min(L[-1, 1], R[-1, 1]), max(L[-1, 1], R[-1, 1])))
    hpL, hpR = grooves[5][1], grooves[5][2]
    openings.append(tuple(sorted([hpL[0, 1], hpR[0, 1]])))
    openings.append(tuple(sorted([hpL[-1, 1], hpR[-1, 1]])))
    openings.sort()

    face = [[0.0, 0.0], [PLATE_Y, 0.0], [PLATE_Y, PLATE_Z]]
    for lo, hi in reversed(openings):
        face.extend([[hi, PLATE_Z], [hi, FLOOR_Z],
                     [lo, FLOOR_Z], [lo, PLATE_Z]])
    face.append([0.0, PLATE_Z])
    face = as_ccw(_dedupe(np.array(face)))
    for ia, ib, ic in ear_clip(face):
        mesh.tri((PLATE_X, face[ia, 0], face[ia, 1]),
                 (PLATE_X, face[ib, 0], face[ib, 1]),
                 (PLATE_X, face[ic, 0], face[ic, 1]))

    expected = PLATE_X * PLATE_Y * PLATE_Z - groove_area * GROOVE_DEPTH
    return mesh.array(), expected


def _dedupe(poly):
    keep = [0]
    for i in range(1, len(poly)):
        if np.linalg.norm(poly[i] - poly[keep[-1]]) > 1e-9:
            keep.append(i)
    if np.linalg.norm(poly[keep[-1]] - poly[keep[0]]) < 1e-9:
        keep.pop()
    return poly[keep]


# --------------------------------------------------------------------------
# TRACCE
# --------------------------------------------------------------------------
def profile():
    """Sezione della traccia nel piano (offset perpendicolare, z)."""
    h = TRACK_W / 2.0
    ztop = GROOVE_DEPTH + SPORGENZA
    return np.array([
        [-(h - CH_BOT_S), 0.0],
        [+(h - CH_BOT_S), 0.0],
        [+h, CH_BOT_H],
        [+h, ztop - CH_TOP_H],
        [+(h - CH_TOP_S), ztop],
        [-(h - CH_TOP_S), ztop],
        [-h, ztop - CH_TOP_H],
        [-h, CH_BOT_H],
    ])


def sweep(mesh, p, t, prof):
    nrm = np.stack([-t[:, 1], t[:, 0]], axis=1)
    m = len(prof)
    ring = np.empty((len(p), m, 3))
    for j, (u, z) in enumerate(prof):
        ring[:, j, 0] = p[:, 0] + u * nrm[:, 0]
        ring[:, j, 1] = p[:, 1] + u * nrm[:, 1]
        ring[:, j, 2] = z
    for i in range(len(p) - 1):
        for j in range(m):
            k = (j + 1) % m
            mesh.quad(ring[i, j], ring[i, k], ring[i + 1, k], ring[i + 1, j])
    for j in range(1, m - 1):
        mesh.tri(ring[0, 0], ring[0, j + 1], ring[0, j])
    for j in range(1, m - 1):
        mesh.tri(ring[-1, 0], ring[-1, j], ring[-1, j + 1])
    return abs(shoelace(prof)) * _path_length(p)


def _path_length(p):
    return float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1)))


def build_tracks():
    """Uno spezzone per scavo: parte dal fondo cieco del proprio scavo, cosi'
    la fase della sinusoide coincide quando lo si spinge in battuta.
    Spezzoni identici per tutti gli scavi NON funzionano: i fondi ciechi sono
    scaglionati di 4 mm, che non e' un sottomultiplo del periodo di 18 mm."""
    mesh = Mesh()
    prof = profile()
    expected = 0.0
    for _, y_ref, x0 in WAVY:
        p, t = wave_path(x0 + INSERT_GAP, INSERT_X1, y_ref)
        expected += sweep(mesh, p, t, prof)
    p, t = hairpin_path(INSERT_X1)
    expected += sweep(mesh, p, t, prof)
    return mesh.array(), expected


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    args = ap.parse_args()

    print("Provino di taratura — accoppiamento scavo/traccia\n")
    print(f"  piastra  {PLATE_X:.0f} x {PLATE_Y:.0f} x {PLATE_Z:.0f} mm"
          f"   scavi profondi {GROOVE_DEPTH:.1f} mm   base {FLOOR_Z:.1f} mm")
    print(f"  traccia  larghezza {TRACK_W:.2f} mm   altezza "
          f"{GROOVE_DEPTH + SPORGENZA:.2f} mm   sporgenza {SPORGENZA:.2f} mm")
    print(f"  scavi    {', '.join(f'{w:.2f}' for w, _, _ in WAVY)}"
          f"   tornante {HP_W:.2f} (R {HP_R:.1f} mm)\n")

    plate, exp_p = build_plate()
    ok1 = validate(plate, "provino_piastra.stl", exp_p, n_shells=1)
    write_stl(plate, f"{args.out}/provino_piastra.stl", "provino_piastra")

    tracks, exp_t = build_tracks()
    ok2 = validate(tracks, "provino_tracce.stl", exp_t, n_shells=6)
    write_stl(tracks, f"{args.out}/provino_tracce.stl", "provino_tracce")

    print(f"\n  {'tutto validato' if ok1 and ok2 else 'controllare gli avvisi'}")


if __name__ == "__main__":
    main()
