#!/usr/bin/env python3
"""Verifica di congruenza fra rilievo e traccia, partendo solo dai due STL.

Nessun riferimento al campo di distanza o alla centerline che li hanno generati:
i due file vengono riletti da zero e confrontati geometricamente.

Uso:
    python3 verifica_congruenza.py
    python3 verifica_congruenza.py --rel rilievo.stl --trk traccia.stl
"""
import argparse, struct
import numpy as np
from scipy.spatial import cKDTree

FLOOR, GW, TW, SPORG = 6.0, 1.20, 0.90, 0.40


def load(p):
    d = open(p, "rb").read()
    n = struct.unpack("<I", d[80:84])[0]
    r = np.frombuffer(d, dtype=[("d", "<f4", 12), ("a", "<u2")], count=n, offset=84)
    return r["d"][:, 3:12].reshape(-1, 3, 3).astype(np.float64)


def slice_z(T, z):
    """Segmenti della sezione del solido al piano z."""
    v = T - np.array([0, 0, z])
    s = v[:, :, 2]
    above = s > 0
    cnt = above.sum(1)
    sel = (cnt == 1) | (cnt == 2)
    T2, s2, ab = T[sel], s[sel], above[sel]
    segs = []
    for tri, sv, a in zip(T2, s2, ab):
        pts = []
        for i in range(3):
            j = (i + 1) % 3
            if a[i] != a[j]:
                t = sv[i] / (sv[i] - sv[j])
                pts.append(tri[i] + t * (tri[j] - tri[i]))
        if len(pts) == 2:
            segs.append((pts[0][:2], pts[1][:2]))
    return np.array(segs)


def pt_seg_dist(P, S):
    """Distanza minima di ogni punto P dai segmenti S, a blocchi."""
    A, B = S[:, 0], S[:, 1]
    AB = B - A
    L2 = np.einsum("ij,ij->i", AB, AB)
    L2[L2 == 0] = 1e-18
    out = np.empty(len(P))
    for k in range(0, len(P), 256):
        q = P[k:k + 256]
        w = q[:, None, :] - A[None, :, :]
        t = np.clip(np.einsum("kij,ij->ki", w, AB) / L2, 0, 1)
        proj = A[None, :, :] + t[:, :, None] * AB[None, :, :]
        out[k:k + 256] = np.linalg.norm(q[:, None, :] - proj, axis=2).min(1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rel", default="courmayeur_GTC_150mm_rilievo.stl",
                    help="STL del rilievo")
    ap.add_argument("--trk", default="courmayeur_GTC_150mm_traccia.stl",
                    help="STL della traccia")
    args = ap.parse_args()

    R, K = load(args.rel), load(args.trk)
    vr = np.unique(np.round(R.reshape(-1, 3), 5), axis=0)
    vk = np.unique(np.round(K.reshape(-1, 3), 5), axis=0)

    print("1. INGOMBRI")
    print("   rilievo  x %.2f-%.2f  y %.2f-%.2f  z %.2f-%.2f"
          % (vr[:, 0].min(), vr[:, 0].max(), vr[:, 1].min(),
             vr[:, 1].max(), vr[:, 2].min(), vr[:, 2].max()))
    print("   traccia  x %.2f-%.2f  y %.2f-%.2f  z %.2f-%.2f"
          % (vk[:, 0].min(), vk[:, 0].max(), vk[:, 1].min(), vk[:, 1].max(),
             vk[:, 2].min(), vk[:, 2].max()))
    inside = (vk[:, 0].min() >= vr[:, 0].min() and vk[:, 0].max() <= vr[:, 0].max()
              and vk[:, 1].min() >= vr[:, 1].min() and vk[:, 1].max() <= vr[:, 1].max())
    print("   traccia dentro l'impronta del rilievo: %s" % inside)

    print("\n2. APPOGGIO SUL FONDO")
    print("   quota minima traccia   %.4f mm" % vk[:, 2].min())
    fl = vr[np.abs(vr[:, 2] - FLOOR) < 1e-6]
    print("   fondo scavo rilievo    %.4f mm  (%d vertici)" % (FLOOR, len(fl)))
    print("   scarto di appoggio     %.4f mm" % abs(vk[:, 2].min() - FLOOR))

    print("\n3. GIOCO LATERALE — sezioni orizzontali indipendenti")
    print("   z      punti traccia   gioco min   gioco medio   gioco max")
    worst = 9.9
    for z in (6.5, 8.0, 10.0, 12.0, 14.0, 17.0, 20.0, 22.0):
        sk = slice_z(K, z)
        if len(sk) == 0:
            continue
        sr = slice_z(R, z)
        P = np.unique(np.round(sk.reshape(-1, 2), 6), axis=0)
        d = pt_seg_dist(P, sr)
        worst = min(worst, d.min())
        print("   %5.1f  %8d      %.4f      %.4f       %.4f"
              % (z, len(P), d.min(), d.mean(), d.max()))
    print("   gioco nominale %.4f mm per lato" % ((GW - TW) / 2))

    print("\n4. SPORGENZA SULLA SUPERFICIE")
    top = vk[vk[:, 2] > vk[:, 2].min() + 0.01]
    srf = vr[vr[:, 2] > FLOOR + 0.01]
    t2 = cKDTree(srf[:, :2])
    idx = t2.query(vk[:, :2], k=1)[1]
    hi = []
    for zq in (0,):
        pass
    d2, i2 = t2.query(top[:, :2], k=8)
    dz = top[:, 2][:, None] - srf[i2, 2]
    best = dz[np.arange(len(top)), np.argmin(np.abs(dz - SPORG), axis=1)]
    print("   differenza traccia-superficie: mediana %.4f mm  (nominale %.4f)"
          % (np.median(best), SPORG))
    print("   quota massima traccia %.2f  <  quota massima rilievo %.2f: %s"
          % (vk[:, 2].max(), vr[:, 2].max(), vk[:, 2].max() < vr[:, 2].max()))

    print("\nESITO: %s" % ("compatibili, nessuna interferenza"
                           if worst > 0.80 * (GW - TW) / 2 and inside else "DA CONTROLLARE"))


if __name__ == "__main__":
    main()
