# Changelog

All notable changes to this project, and the reasoning behind them.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Dimensions are millimetres unless stated otherwise. Every entry that changes
printable geometry records its validation result, because in this project a
change is not done until the mesh has been re-validated: manifold, Euler
characteristic, and signed volume against an independent analytical estimate.

---

## [Unreleased]

### Changed — insert clearance widened after physical feedback

- `GROOVE_W` 1.15 -> **1.20**, taking clearance from 0.125 to **0.150 mm per
  side**. `TRACK_W` stays 0.90 and `FLOOR_Z`/`SPORG` are untouched.
- **Driven by the built object, not by a measurement.** The GTC55 insert did go
  into its recess and the piece was completed, but it was stiff and awkward to
  seat safely. Every numerical check had passed, so this is a case where the
  mesh validation could not have caught the problem — only handling the parts
  could.
- The step size comes from the calibration ladder in `provino_taratura.py`, which
  tests 1.05 / 1.10 / 1.15 / 1.20 / 1.25. The medium rung, 1.15, is what was in
  use; one rung further is 1.20.
- **Only the relief changes.** `build()` selects `half = GROOVE_W / 2` for the
  relief and `TRACK_W / 2` for the insert, so the insert is independent of the
  groove. Confirmed rather than assumed: the regenerated track STL is
  byte-identical to the previous one (md5 match), so an already-printed insert
  still fits a rebuilt base. Labels are unaffected.
- Added `--groove` and `--track` to `rilievo3d_intarsio.py` so the clearance can
  be tuned per project without editing the module.
- `verifica_congruenza.py`: `GW` updated to 1.20, and both the reported nominal
  and the pass threshold are now derived from `(GW - TW) / 2` instead of being
  hardcoded to the old 0.125. The threshold had been a bare `worst > 0.10`, which
  would have silently kept passing against the wrong target after this change.
- GTC55-2026 was deliberately **not** regenerated: its DEM tiles are not held
  locally, and the existing piece is already assembled.

### Regenerated — Valgrosina-2026 relief

| | before (groove 1.15) | after (groove 1.20) |
|---|---|---|
| relief volume | 680.78 cm3 | 680.42 cm3 |
| facets | 2 047 554 | 2 047 362 |
| validation | manifold, chi=2, dev. 0.01 % | manifold, chi=2, dev. 0.01 % |
| nominal clearance | 0.125 mm/side | 0.150 mm/side |
| **minimum** measured clearance | 0.1007 mm (z=20) | **0.1259 mm** (z=17) |
| mean measured clearance | 0.132 mm | 0.159 mm |
| seating error | 0.0000 mm | 0.0000 mm |
| protrusion (nominal 0.4000) | 0.3991 mm | 0.3989 mm |
| verdict | compatibili | compatibili |

The small volume drop is the extra material removed by the wider recess. The
minimum and the mean both moved by very close to the full 0.025 mm added to the
nominal, which is the evidence that the change reached the tight spots and not
just the average. The tightest point of the new build, 0.1259 mm, is now as
generous as the *nominal* of the build that was stiff to assemble.

Worth keeping in view: the pinch points are still 0.126 rather than the 0.150
nominal, because where the corridor merges the contour discretisation eats into
the gap. If 1.20 still feels tight in the hand, the next rung on the
`provino_taratura.py` ladder is 1.25.

### Added — Valgrosina-2026

- Second project: **Trail Valgrosina 38k**, from `activity_23900042032.gpx`
  (37.70 km, ~2518 m D+ smoothed, 654-2186 m, recorded 2026-08-08, near-loop with
  a 503 m start-to-finish gap). Relief, track insert and label.
- `rilievo3d_intarsio.py` parameterised: `--name`, `--bbox`, `--size`, `--vex`,
  `--plinth`, `--grid`, `--out`. The module constants are overridden at run time
  rather than threaded through every function, so the validated code paths are
  untouched. Output now goes to `3d-outputs/<name>/` with the size in the name.
- `etichetta3d.py` parameterised: `--name`, `--text`, `--out`.
- `components()` in `etichetta3d.py`, splitting a glyph into disconnected solids,
  and `BRIDGE_Z` for joining them.
- `hgt/N46E010.hgt` downloaded (SRTM1, 3601x3601, no voids, 221-3900 m).

### Generated — Valgrosina-2026

| File | Size | Validation |
|---|---|---|
| `Valgrosina-2026_150mm_rilievo.stl` | 150 x 150 x 52.99 mm, GRID=1000 | manifold, chi=2, volume dev. 0.01 %, 2 047 554 facets |
| `Valgrosina-2026_150mm_traccia.stl` | 28.1 x 134.7 mm, z 6.00-35.02, GRID=1000 | manifold, chi=-2, one connected piece, genus 2 |
| `Valgrosina-2026_label_180mm.stl` | 180.00 x 11.98 x 2.00 mm, cap 10.514 | manifold, chi=152, volume dev. 0.03 % |
| `Valgrosina-2026_label_160mm.stl` | 159.79 mm, cap 9.322 | manifold, chi=148 — same cap height as the GTC55 label, kept as the matched-set option |

The label chi is again a prediction rather than an observation: 89 shells give
178, minus 2 for each of the 13 counters in this text (three `0`, two `6`, two in
`8`, three `a`, and one each in `g o d`), giving 152.

### Fixed

- **`--fit` solved the cap height against the wrong text.** `fit_cap()` ran before
  the `--text` override was applied, so it sized the label for the module-default
  GTC55 string: the first Valgrosina label came out 159.79 mm at cap 9.322 mm
  instead of the requested 180 mm. It looked plausible, which is what made it
  worth recording — the give-away was the cap height being identical to the
  previous project's.
- **Multi-part glyphs were only held by one post.** Impact's `i` is a stem plus a
  separate dot, so both dots printed unattached to the runner and would have been
  lost. The GTC55 text contained no dotted glyph, so this had never surfaced.
- **First attempt at that fix broke manifoldness** (non-manifold 10, orientation
  20). Giving every part its own post sends the stem's post straight through the
  dot and the dot's post; the boxes share x, z and part of y, so their faces
  coincide and weld. The dot sits only 0.52 mm above the stem and overlaps it
  across the full 2.65 mm width, so there is room for neither two notches in the
  gap nor a sideways detour. Resolved by posting the *highest* part to the spine
  and bridging lower parts to it: 0.45 mm wide, 0.60 mm deep, leaving the front
  1.40 mm of the letter depth clear.

### Decisions

- **Relief frames are 150 x 150 mm square from now on**, squared on the track
  bbox centre with a 12 % margin. Recorded in `CLAUDE.md`.
- **Elongated routes are not cropped to their own proportions.** Valgrosina is a
  2.28 x 11.18 km sliver (4.9:1); a tight crop would have been a 37 x 180 mm
  ribbon with the label five times wider than the relief. In the square frame the
  route fills 89 % of the height and 18 % of the width, and the valley reads well.
- **Label at 180 mm** to match the proportion of the approved GTC55 piece, which
  is a 180 mm label on a 150 mm relief. The 160 mm version is kept because it
  shares the GTC55 letter height, if the two are ever wanted as a matched set.
- **Bridges rather than separate posts for multi-part glyphs.** A bridge is
  permanent and slightly alters the letterform; the alternative leaves a 2.65 x
  1.34 mm chip to be glued by hand in the right place. Positioning accuracy won.

### Fixed — track clearance

- **GRID raised from 700 to 1000 for this route**, after `verifica_congruenza.py`
  returned DA CONTROLLARE on the first build. The two runs, same geometry and
  same nominal 0.125 mm per side:

  | | GRID=700 | GRID=1000 |
  |---|---|---|
  | minimum lateral clearance | 0.0844 mm (z=12) | **0.1007 mm** (z=20) |
  | mean clearance | 0.132 mm | 0.132 mm |
  | seating error | 0.0000 mm | 0.0000 mm |
  | protrusion (nominal 0.4000) | 0.3997 mm | 0.3991 mm |
  | verdict | DA CONTROLLARE | **compatibili, nessuna interferenza** |

  The mean sat on nominal in both runs, so the deficit was never a design error:
  it was the contour discretisation pinching where the corridor merges, and it is
  the failure mode the handoff already predicted in section 7.2. The delivered
  files are the GRID=1000 builds; the relief is 102 MB and 2 047 554 facets, four
  times the GRID=700 build, which is the price of the fix.
- Insert genus also changes with the grid, 3 at GRID=700 and 2 at GRID=1000, so
  one of the merge points is resolved differently at each resolution. Neither is
  wrong — it reflects how close those legs genuinely are.

### Open

- 31 % of the centreline has another leg within the 1.15 mm groove width, closest
  approach 0.013 mm, so grooves merge into single wider channels along the valley.
  Safe by construction, and the insert stays one piece, but merged legs read as
  one band. This is inherent to fitting a 4.9:1 route into a square frame, not
  something the grid can fix.
- Minimum clearance 0.1007 mm is a pass but not comfortable, against 0.125
  nominal. If the insert binds on this route, the documented lever is TRACK_W
  0.90 -> 0.86, which requires re-running `verifica_congruenza.py` because
  FLOOR_Z, SPORG, GROOVE_W and TRACK_W are coupled.

### Added — documentation

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
