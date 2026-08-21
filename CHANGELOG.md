# Changelog

All notable changes to this project, and the reasoning behind them.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Dimensions are millimetres unless stated otherwise. Every entry that changes
printable geometry records its validation result, because in this project a
change is not done until the mesh has been re-validated: manifold, Euler
characteristic, and signed volume against an independent analytical estimate.

---

## [Unreleased]

### Added

- `CHANGELOG.md` — this file, tracking changes and the decisions behind them.
- `CLAUDE.md` — working conventions, including the rule that every change is
  logged here.
- `docs/images/` — photographs documenting the built object: the two pieces on
  the printer bed, the insert seated in its recess, and the finished piece
  mounted on a wooden base with the label letters glued below it.
- Results gallery in `README.md`.

### Changed

- Approach B status corrected from *validated numerically, not yet printed* to
  **printed and assembled**. The photographs show the red track insert seated in
  the white relief and the finished object mounted on wood, so the 0.125/side
  clearance and the snap-off label runner are both confirmed in the physical
  part and not only in mesh validation.

---

## [2026-08-21] Label pipeline

### Added

- `etichetta3d.py` — generator for the name label: individual letter solids plus
  a snap-off runner, no name plate.
- `--fit` flag, solving the cap height for a target total length. Worth having
  because the relation is not a ratio: `MIN_GAP` is absolute, so the air gaps
  take a growing share of the width as the letters shrink (0.47 of added
  tracking at 180, 3.35 at 100).
- `.gitignore` for STL build artefacts, SRTM tiles and `__pycache__`.
- Output convention `3d-outputs/<project>/`, with the total length in the
  filename so several sizes coexist.

### Generated

| File | Cap | Total | Depth | Triangles | Validation |
|---|---|---|---|---|---|
| `GTC55-2026_label_126mm.stl` | 6.50 | 126.47 | 2.00 | 204 224 | manifold, chi=158, volume dev. 0.14 % |
| `GTC55-2026_label_180mm.stl` | 9.322 | 180.00 | 2.00 | 318 936 | manifold, chi=158, volume dev. 0.05 % |

chi = 158 is a topology assertion, not just an observation: 88 closed shells give
2x88 = 176, minus 2 for each of the seven single-counter letters in the text
(`o o a a e 0 6`, each a solid torus) and minus 4 for `B` (genus 2). If chi drifts
from 158, either the counters are being filled in or a shell is open.

### Fixed

- **Chamfer could not be an inward polygon offset.** A 0.40 chamfer needs 0.80 of
  material, and the narrowest neck in the text is 0.39 (the shoulder of `m` at
  cap 6.50), so the front face collapsed and self-intersected there. Rebuilt as a
  distance-field roof, `z = min(DEPTH, DEPTH - CHAMFER + d)`, which degrades into
  a ridge where the glyph is narrow instead of failing. Same level-set idiom as
  `rilievo3d_intarsio.py`.
- **Delaunay plus a per-triangle centroid test produced non-manifold shells.**
  Densifying straight outline segments feeds qhull exactly collinear points and
  it returns zero-area simplices. Those sit *on* the outline, so the centroid
  test is a coin flip, and a kept one duplicates the outline edges it lies on.
  Replaced with region growing that treats the outline edges as walls, testing
  one large representative triangle per region, then discarding degenerate
  triangles. `triangulate()` now asserts that the triangulated region's boundary
  equals the outline exactly, so this cannot regress quietly.
- **Duplicate closing vertices.** `Path.to_polygons()` repeats the first point at
  the end, creating zero-length edges that corrupted the index-based boundary.

### Measurement methods that gave wrong answers

Recorded because both are easy to repeat and neither fails loudly.

- Chord-based stroke width (scanline intersections) is dominated by tapered
  terminals and by grazing slivers where an arch meets a stem. It reported
  0.04 features on `n u r` that do not exist. An early claim of "1.05 thinnest
  stroke" came from sampling only 15 scanlines per glyph and was wrong; the real
  figure at cap 6.50 is 0.39.
- `matplotlib.path.Path.contains_points` on a whole glyph path **fills the
  counters**, so the first erosion test measured solid blobs while computing
  distances to hole outlines, and its results were meaningless. Rasterise each
  contour separately and XOR them (even-odd).

### Decisions

- **Letters only, plus a removable runner** — not a name plate. Nothing behind or
  between the letters; a straight rail above the text reaches each letter through
  a post ending in a thin snap notch. This took four preview iterations to
  converge, because "connection on the top of them" was repeatedly drawn as a
  solid bar behind the text. The distinguishing test is whether you can see
  through the gaps between the letters.
- **Straight rail with posts of differing length**, rather than a stepped rail
  hugging each letter top. A straight rail is much stiffer along the label, which
  is its entire purpose, and the notch rather than the post sets the break force,
  so a 0.40 post and a 5.29 post snap identically.
- **Impact, not Arial Narrow Bold.** Arial Narrow Bold measured 0.22 at its
  thinnest point, the curve terminals of `a c e`, and would have printed as
  broken gaps.
- **The binding constraint is the counters, not stroke width.** Below roughly
  0.45 an enclosed hole closes up while printing and the letter reads as a solid
  blob. This is what ruled out the smaller sizes: at 100 the narrowest counter is
  0.40, under one 0.42 bead.
- **En dash, not em dash** — the em dash was what pushed the earlier Arial Narrow
  layout past 150.
- **Runner flush with the back face, chamfer pointing up.** Forced rather than
  preferred: printing chamfer-down would make the first layer of the `l` stem
  only 0.3 wide.
- **88 separate shells accepted** instead of computing a boolean union. Slicers
  union overlapping shells reliably and each shell is individually validated.
- **Minimum air gap 0.50 between adjacent letter inks**, enforced by adding
  tracking, so letters cannot fuse at the base through over-extrusion.
- Length budget moved 100 to 130 to 180 as the trade-off became measurable.
  Depth reduced 3.00 to 2.00.

### Open

- The 0.45 x 1.00 notch section is a reasoned estimate of snap force, not a
  measured one. It is the only number in the label design that cannot be
  verified computationally and it deserves a test strip with notch widths
  0.35 / 0.45 / 0.55, in the spirit of `provino_taratura.py`.
- At cap 9.322 the en dash post is 5.29 long at 0.80 x 1.00 section, the one
  slender spot in the runner. Widening `POST_W` fixes it if it proves floppy.

### Environment

- Installed scipy 1.18.0. It was missing entirely, which meant `rilievo3d_v1.py`,
  `rilievo3d_intarsio.py` and `verifica_congruenza.py` could not run on this
  machine at all.

---

## [2026-08-21] Repository creation and consolidation

Four commits, `6bd4256` through `a40c784`.

### Added

- `rilievo3d_v1.py` (`f393d5c`) — approach A, single piece with the track incised
  as a groove via distance transform. Final model: bbox 45.7010-45.8988 /
  6.7880-7.0713, size 180, vertical exaggeration 1.3, plinth 12, grid 600x600.
- `rilievo3d_intarsio.py` (`a9196e4`) — approach B, two-piece inlay: relief with
  a recess, plus a track insert.
- `dem.py`, `provino_taratura.py`, `verifica_congruenza.py` (`a40c784`) — DEM
  loader, calibration test piece, and independent congruence check.
- `docs/project_handoff.md` (`f393d5c`) — design history, parameters, error
  history and validation checklist, translated from the original Italian.

### Changed

- Documentation standard set to English; the source handoff document was Italian.
- `rilievo3d.py` renamed to `rilievo3d_v1.py` to sit alongside approach B.

### Fixed

- Hardcoded `/mnt/user-data/outputs/` paths in `verifica_congruenza.py` and
  `rilievo3d_intarsio.py` replaced with CLI arguments. They were absolute paths
  from a different environment and made both scripts unrunnable locally.

### Decisions

- **Public repository**, `zu76/3D-Trail-Run`.
- **No CAD libraries** — no trimesh, shapely, open3d or CGAL. Meshes are built
  triangle by triangle and validated from scratch.
- **Both approaches kept in parallel** rather than choosing one.
- **Approach B derives both pieces as level sets of one shared distance field**,
  so recess and insert are concentric by construction and the perpendicular
  clearance is exactly `(GROOVE_W - TRACK_W)/2` everywhere, including in the
  switchbacks where a sweep/offset construction self-intersects.
- **Contours extracted by 45-iteration bisection on the true KD-tree distance**,
  not by linear interpolation of the sampled field, which is wrong by up to half
  a cell near the medial axis. Result: track at 0.4500, recess at 0.5750.
- `FLOOR_Z`, `SPORG`, `GROOVE_W` and `TRACK_W` are coupled: changing any of them
  requires re-running `verifica_congruenza.py`.
