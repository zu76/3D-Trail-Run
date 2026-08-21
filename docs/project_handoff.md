# `rilievo3d` Project — Handoff Document

Continuity document for resuming the project in Claude Code.
Contains: objective, data, **both developed approaches** (incised track and inlay track),
all parameters, decision history and errors, validation method, and conventions to
respect so as not to break what has already been done.

Last updated: August 2026. Conversations conducted in Italian.

---

## 1. Objective

Generate printable 3D STL models of mountain reliefs with an embedded GPS track,
in the style of alpine relief plaques (visual reference: *alpen-werk #RB60*).

The reference case is the **Gran Trail Courmayeur (GTC)**: a 55.66 km loop with
~3,066 m of elevation gain around the Mont Blanc massif in Valle d'Aosta, run by
the user.

The project has two dimensions:
1. produce physically correct prints for the Courmayeur case;
2. maintain a parametric toolchain reapplicable to new locations
   (new GPX + `.hgt` tiles + bounding box).

---

## 2. Data and Environment

### Sources

| Data | Detail |
|---|---|
| DEM | SRTM 1 arcsecond tiles, `.hgt` format, ~30 m resolution |
| Required tiles | `N45E006.hgt`, `N45E007.hgt` (12,967,201 cells = 3601², big-endian int16) |
| Mirror | `https://raw.githubusercontent.com/danielementary/Alpano/master/N45E006.hgt` |
| Track | `activity_23561586194.gpx` — 41,932 points, user's personal file |

Tile elevations: N45E006 from 248 to **4805 m** (Mont Blanc), N45E007 from 164 to 4626 m.
Values `-32768` = void, must be converted to NaN.

### GPX Characteristics (verified)

- 41,932 points, 55.66 km, bbox lat 45.7428–45.8174 / lon 6.8071–6.9859
- GPX elevations 1025–2869 m (but **the model uses DEM elevations, not GPX ones**)
- **380 m signal gap** around km 33, above Lac Combal → must be filled by
  interpolation, otherwise the groove comes out split into two segments
- Start and finish are ~260–277 m apart: the loop **is not closed** in the GPX
- Average point spacing 1.33 m → model-scale 0.009 mm, i.e.
  **enormously denser than needed**: must be decimated, not densified

### Stack

Pure Python with `numpy`, `scipy`, `matplotlib`. **No CAD libraries**
(no trimesh, shapely, open3d, CGAL). Meshes are built triangle by triangle and
written as binary STL by hand. This is a deliberate design choice to maintain:
it makes the pipeline readable, reproducible, and free of opaque dependencies.

### Projection Conventions

```python
R = 6371000.0
latm = (LAT0 + LAT1) / 2
W = radians(LON1 - LON0) * R * cos(radians(latm))   # width in metres
H = radians(LAT1 - LAT0) * R                        # height in metres
s  = SIZE / max(W, H)          # mm per planimetric metre
kz = s * VEX                   # mm per elevation metre
z(x, y) = PLINTH + (Z(x, y) - Zmin) * kz
```

`Zmin` is the minimum of the DEM **filtered** over the bbox, not the raw minimum.
A `gaussian_filter(Z, 1.0)` is applied to the DEM to remove radar noise.

---

## 3. Approach A — Incised Track (original version, complete)

**Idea.** A single printed object. The track is a groove carved into the relief
surface, to be coloured afterwards with an acrylic marker drawn along the groove
and wiped clean on the surface with a slightly damp cloth.

**Pros.** One piece, one print, no fit tolerances required.
**Cons.** Colour is applied by hand, so the result depends on skill; the track is
not a physically distinct element.

### Version History

| Ver. | Area | Exaggeration | Plinth | Outcome |
|---|---|---|---|---|
| first build | 22×22 km | 1.0× | 6 mm | relief too flat; **wall and floor normals inverted** |
| v1 | 15×15 km | 1.0× | — | framing too tight, track runs edge to edge |
| v2 | 26×26 km | 1.0× | 12 mm | normals correct, but too much margin west and still flat |
| **v3 (final)** | **22×22 km** | **1.3×** | **12 mm** | accepted |

### Final v3 Parameters

| Parameter | Value |
|---|---|
| Bounding box | lat 45.7010–45.8988, lon 6.7880–7.0713 |
| Area | 22.0 × 22.0 km |
| Format | 179.7 × 180.0 mm |
| Planimetric scale | 1:122,191 |
| Vertical exaggeration | 1.3× |
| Plinth | 12.0 mm |
| Relief above plinth | 42.8 mm |
| Total height | 54.0 mm |
| Grid | 600 × 600 (cell 0.301 mm = 25 m of terrain) |
| Groove | width 1.4 mm (171 m on the ground), depth 0.8 mm, flat bottom 0.7 mm + 45° taper |
| Triangles | 723,586 |
| Volume | 921.5 cm³ (analytical 921.1) — ≈ 250 g PLA at 15% infill |
| Composition | Courmayeur at 64% from left / 45% from bottom; Mont Blanc 27%/67%; track 63% of width (from 7% to 70%), 21–59% vertically |
| Maximum surface slope | 80° — no undercut possible, **never needs supports** |

Command that generated the final model:

```bash
python3 rilievo3d.py \
  --gpx activity_23561586194.gpx --hgt-dir ./hgt \
  --bbox 45.7010 45.8988 6.7880 7.0713 \
  --size 180 --vex 1.3 --plinth 12 \
  --out courmayeur_GTC_180mm_v3.stl
```

`rilievo3d.py` was parametric, automatically mosaicked the `.hgt` tiles from the
bbox, and had a `--preview` flag to study the framing before generating the STL.
**Note: this script is saved in the repository as `rilievo3d_v1.py`.**
For the approach B pipeline, it was rewritten from scratch; regenerate from v1 if needed.

### Incision Method (Approach A)

The groove is obtained via **distance transform** on the raster: the track is
densified to fill signal gaps, the distance from each cell to the polyline is
computed, and the surface elevation is lowered where the distance is less than the
half-width. The groove bottom follows the terrain at constant depth. The surface
remains a height field, so the solid is printable without supports by construction.

---

## 4. Approach B — Inlay Track, Two Pieces (current version)

**Idea.** Two objects printed separately in different coloured filaments:

1. **relief** with a vertical-wall, flat-bottom recess;
2. **track**, a thin strip that slots into the recess and **protrudes** above the
   surface, forming a raised line of contrasting colour.

**Pros.** Clean and permanent colour, track physically readable by touch.
**Cons.** Requires real fit tolerances, and the track piece is very slender and fragile.

### 4.1 Basic Geometry

The recess **does not follow the terrain**: its bottom sits on a **horizontal plane
at constant elevation**. This is the central structural decision of approach B,
reached after discarding the alternative (constant depth below the terrain):

- the track piece has a flat base → prints lying on the bed, no supports needed;
- it is a continuous vertical wall, far more rigid than a wavy strip;
- the recess reduces to vertical walls + a plane → much simpler mesh;
- the track height becomes **the race elevation profile**, which is also an
  aesthetic value.

The user's constraint: at least **5 mm** of continuous material must remain below
the recess floor. **6.00 mm** was adopted.

This constraint is structural, not aesthetic: the track is a loop, and the recess
containing it isolates the inner portion of the loop from the rest of the model.
**The continuous base below the recess is the only thing holding the piece together.**

### 4.2 Why Level Sets Instead of a Sweep

The first instinct is to build the recess and track as prisms extruded along the
path (sweep). **This does not work**, for two measured reasons:

- real switchbacks on the trail have radii of ~10 m, which at 150 mm scale become
  **0.068 mm** against a recess half-width of 0.575 mm: offset curves self-intersect;
- where two passes come close (measured minimum centreline spacing **0.78 mm**)
  the two strips interpenetrate.

The adopted solution: **both pieces are level sets of the same distance field**
from the track polyline.

- recess = { distance ≤ 0.575 mm }
- track  = { distance ≤ 0.450 mm }

They are concentric by construction, the perpendicular clearance is the difference
between the two levels, and merges and switchbacks are handled without special cases:
where the corridor merges it becomes a lobe, and the track merges in exactly the
same way.

### 4.3 Bisection on True Distance

**This is the most delicate point in the entire pipeline.**

The contour is extracted from the distance field sampled on a grid. Computing the
crossing point by **linear interpolation** of the field values along a cell edge is
wrong: where two passes of the track come close, the distance field has a **ridge**
(medial axis between the two branches) and is not linear at all. The error reaches
half a cell.

Measured effect: the track contour came out at **0.547 mm** from the axis instead
of 0.450, reducing the clearance from 0.125 to **0.028 mm** → guaranteed interference.

Solution: the contour point is found by **bisection on the true distance**
(45 iterations of batched KD-tree queries on edges that change sign).
After the fix: track contour at exactly 0.4500, recess wall at 0.5750.

```python
# A = endpoint with smaller distance, B = larger
lo, hi = 0.0, 1.0
for _ in range(45):
    mid = (lo + hi) / 2
    P = A + mid * (B - A)
    inside = tree.query(P[:, :2])[0] < half
    lo, hi = np.where(inside, mid, lo), np.where(inside, hi, mid)
t = np.clip((lo + hi) / 2, 2e-4, 1 - 2e-4)   # never exactly on vertices
```

The final `clip` is not cosmetic: if the contour falls exactly on a grid vertex
the polygons degenerate and the walls remain open.

### 4.4 Final Parameters — Courmayeur GTC 150 mm

| Parameter | Value |
|---|---|
| Bounding box | lat 45.7010–45.8988, lon 6.7880–7.0713 (**identical to v3**) |
| Area | 21.96 × 21.99 km |
| Model format | 149.8 × 150.0 × 44.91 mm |
| Planimetric scale | 1:146,629 → 1 mm = 147 m |
| Vertical exaggeration | 1.3× → 1 mm = 113 m of elevation |
| Plinth (`PLINTH`) | 10.0 mm |
| Terrain elevations (filtered DEM) | 850 – 4,803 m |
| Grid (`GRID`) | 700 on the long side (cell 0.214 mm) |
| **Recess** (`GROOVE_W`) | **1.15 mm** — 169 m on the ground |
| **Track** (`TRACK_W`) | **0.90 mm** |
| **Nominal clearance** | **0.125 mm per side** |
| Recess floor elevation (`FLOOR_Z`) | 6.00 mm |
| Protrusion (`SPORG`) | 0.40 mm (= exactly 2 layers at 0.20) |
| Chamfers | **none** (see §4.7) |
| Track smoothing (`SMOOTH_MM`) | 0.10 mm (= 14.7 m on the ground) |
| Centreline step (`CL_STEP`) | 0.05 mm |
| Track elevation on model | 11.55 – 27.88 mm |
| Engagement depth in recess | 5.55 – 21.88 mm |
| Track piece height | 5.96 – 22.22 mm |
| Maximum slenderness | 24.7 (h/thickness) |
| Track development | 344.3 mm after smoothing (379.5 raw) |
| Track topology | **closed loop**, genus 1 (χ = 0) |
| Relief | 1,008,778 triangles, 50 MB, **527.58 cm³** (estimate 527.52) |
| Track | 50,804 triangles, 2.5 MB, **4.32 cm³** |

Command:

```bash
python3 rilievo3d_intarsio.py \
  --gpx activity_23561586194.gpx \
  --out .
# requires ./hgt/N45E006.hgt and ./hgt/N45E007.hgt
```

### 4.5 Why the Format Changed from 180 to 150 mm

User's request. Measured consequences, non-obvious:

- **improves** fragility: the track loses 76 mm of development and 3 mm of maximum
  height, slenderness drops from ~26.6 to 24.7;
- **worsens** self-proximity: at the same recess width, the minimum required
  centreline spacing between two passes rises from 232 to 279 m on the ground.
  Switchbacks that were separate at 180 mm merge at 150 mm.

Final corridor self-overlap: **4%** of the ideal area, localised at tight
switchbacks and valley bottom.

### 4.6 Why the Recess Is 1.15 and Not 1.10

The calibration test print showed that 1.10 (clearance 0.100) goes in "with a
little pressure" over **43 mm** of development. On the real model the development
is **344 mm**, eight times as long, and friction accumulates over the entire
contact: a comfortable fit on the test piece can become impossible to seat fully on
the real piece, or seat only by breaking it. Hence the choice of 1.15 (clearance
0.125), **keeping the track at 0.90**: the recess is widened, not the insert.

### 4.7 Chamfers: Present on the Test Piece, Absent on the Final Model

The test piece insert had a base chamfer of 0.20 × 0.10 mm (anti elephant foot)
and a top chamfer of 0.20 × 0.20 mm. On the final model **they were removed**:
with the arbitrary topology of level sets (merges, lobes) the ruled band between
two different contours is complicated to mesh reliably, and with 0.125 mm clearance
per side there is room for elephant foot.

If the piece does not seat fully: enable elephant foot compensation
(0.10–0.15 mm) **on the track object only** in the slicer.

This is a known technical debt and a natural candidate for improvement in Claude Code:
the chamfer can be reintroduced as a **two-level step** (region at level 0.35 from
z=6.0 to 6.2; region at level 0.45 from 6.2 upwards, with the flat crown between
the two levels at z=6.2), built with the same clipping machinery without ruled surfaces.

---

## 5. The Calibration Test Piece

A mandatory step before committing hours of printing. **Do not guess the clearance:
measure it.**

### Geometry

| Parameter | Value |
|---|---|
| Plate | 70 × 52 × 11 mm |
| Recess depth | 8.00 mm (floor at z = 3.00) |
| Wavy recesses | 5, widths 1.05 / 1.10 / 1.15 / 1.20 / 1.25 |
| Reference y | 46 / 39 / 32 / 25 / 18 |
| Blind-end x | 26 / 22 / 18 / 14 / 10 (staggered to identify width from length) |
| Sinusoid | `y = Y + 1.8 * cos(2π (x − 70) / 18)` |
| Switchback | R = 2 mm, centre (16, 8), width 1.10 |
| Inserts | width 0.90, height 8.40 mm |
| Insert chamfers | base 0.20 h × 0.10 setback; top 0.20 × 0.20 |
| Blind-end clearance | 0.50 mm |

**The sinusoid phase is anchored at x = 70** (`cos(2π(x−70)/λ)`) so that at
x = 70 the tangent is horizontal and the offsets end exactly at the plate edge:
avoids having to clip the offset polylines.

The recesses **open at the right edge**: so the top face is a simple comb polygon,
no holes, and triangulates with ear clipping. The switchback, opening with both
legs, leaves an **isolated tongue** in the centre — topologically identical to the
inner island of the real model, so it tests that condition too.

### Result

All inserts went in, at various levels of pressure.
**1.10 chosen as reference** ("a little pressure, but works and forms a good result")
→ hence 1.15 on the large model for the length factor.

### Wavy, Not Straight

In the first version the recesses were straight. On the user's request they became
sinusoids in phase, to test insertion **between curved walls** and not just the
nominal clearance. The switchback covers the opposite extreme case.

---

## 6. Errors Made and How They Were Found

This section is worth more than the parameters: all errors that recur.

### 6.1 Inverted Normals (Approach A, v1)

Wall and floor normals were inverted. The **signed volume** came out negative
(~198 cm³ instead of ~700). Found by the volume check, not visually.
→ **The signed volume compared with an independent analytical estimate is the
single most effective check on a hand-built mesh.**

### 6.2 Test Piece: Identical Inserts on Staggered Blind Ends

The blind ends were staggered by 4 mm to encode the width, but the wave period is
18 mm and **4 is not a divisor of it**. The inserts were all identical and phased
to one recess only: pushed home, the others were out of phase by 80°, 160°, 240°,
320°, up to **3.55 mm** of misalignment against a clearance of 0.10.

The user diagnosed it visually ("they look like waves of different wavelength")
before any measurement.

**Fix:** five distinct inserts, each phase-locked to its own recess and extending
to its own blind end (43 / 47 / 51 / 55 / 59 mm).

**General lesson:** when the geometry is periodic and the seating positions are
staggered, the stagger increments must be multiples of the period, or each piece
must be generated individually.

### 6.3 Linear Interpolation of the Distance Field

See §4.3. Would have reduced the clearance from 0.125 to 0.028 mm.

### 6.4 Node Exactly on the Threshold

A grid node with distance exactly equal to the recess radius collapses the
intersection point onto the vertex → zero-length edges → non-manifold mesh.
Fix: `D[abs(D) < 1e-3] = 1e-3` (1 µm, geometrically irrelevant) **plus** the
`t` clamp in §4.3.

### 6.5 T-Junctions on Composite Faces

On the test piece the right face of the plate was built as separate quads while
adjacent faces were whole quads: 22 non-manifold edges along the shared border.
Fix: build it as **a single comb polygon in the (y, z) plane** and triangulate it,
so the outer edges remain whole segments.

**Lesson:** whenever two faces share an edge, the subdivision of that edge must be
identical on both sides.

### 6.6 Wrong Self-Proximity Report

The first report excluded pairs with along-track separation greater than 10 mm,
and therefore missed **sequential switchbacks**. It reported a minimum centreline
spacing of 1.768 mm when the true value is **0.78 mm**. Consequence: the track
was concluded to be an open strip, when it is actually a closed loop.

### 6.7 Biased Median-Line Estimator

To compare two strips the median line was estimated as `(min y + max y)/2` for
each rounded x. At many x values the sample contained points from only one border,
and the estimate came out shifted by ~half the width. Replaced with a mean over
bins wide enough to contain both borders.

**Lesson:** before believing a measurement that contradicts the design geometry,
check the estimator.

### 6.8 Circular Validation

For a long time the recess and track were validated **against the distance field
that generated them**. This is a circular check: it confirms the internal consistency
of the generator, not the congruence of the produced files. The user asked for
validation on the STLs, and that is where it emerged that the clearance is not
constant (§7.2).

---

## 7. Validation

### 7.1 Mesh Checks (always run before delivering)

| Check | Criterion |
|---|---|
| Manifold | every shared edge has exactly 2 faces |
| Orientation | every directed edge appears exactly once |
| Euler | χ = V − E + F = 2 for a genus-0 single-component solid |
| Signed volume | positive, and matching an independent analytical estimate |
| Degenerate triangles | zero-area = 0 |

Current results:

- relief: χ = 2, 0 non-manifold, 0 inconsistent orientations, 527.58 cm³ vs 527.52 (0.01%)
- track: **χ = 0**, 1 connected component → **genus 1, closed loop**.
  This is not a defect: the track merges with itself in the valley where the
  centreline spacing drops below 0.90 mm. Structurally it is an advantage.

### 7.2 Congruence Verification Between the Two Pieces

Reads **only the two STLs**, without touching the distance field.
Script: `verifica_congruenza.py`.

1. **Footprint** — track inside the relief footprint.
2. **Seating** — minimum track elevation 6.0000 vs recess floor 6.0000: delta 0.0000.
3. **Lateral clearance** — horizontal sections of both solids at z = 6.5 / 8 / 10 /
   12 / 14 / 17 / 20 / 22; distance from each track section vertex to the relief
   section segments.
4. **Protrusion** — track/surface difference: median 0.3989 vs 0.4000.

Clearance distribution over 42,000 points:

| | mm |
|---|---|
| median | 0.1249 |
| 10th percentile | 0.1225 |
| 2nd percentile | 0.1188 |
| 0.5th percentile | 0.1153 |
| **absolute minimum** | **0.0896** |

Below 0.110 mm: 0.145% of points. Below 0.100: 0.029%.
**No interference at any point.**

**Why the minimum is not 0.125.** The contour *vertices* are at 0.4500 and 0.5750
from the axis to the ten-thousandth, but the *edges* between one vertex and the
next are chords: in narrow concavities the chord cuts the corner and brings material
slightly into the void. The minimum of 0.0896 is still at the level of the 0.100
clearance already physically validated on the test piece.

**Possible improvements** (not applied, user's decision):
- `GRID` from 700 to 1000 → chord error −40%, minimum ≈ 0.107, but STL ~100 MB;
- `TRACK_W` from 0.90 to 0.86 → shifts the whole distribution by +0.02 mm without
  touching the relief file and without any visible difference.

---

## 8. Printing

| | Relief | Track |
|---|---|---|
| Layer height | 0.20 mm | 0.20 mm |
| Perimeters | 3 | default (2 at 0.45 fill 0.90) |
| Infill | 10–15% gyroid, 4 top layers | solid |
| Brim | no | **4–5 mm mandatory** |
| Perimeter speed | default | ~25 mm/s |
| Supports | **never** | never |
| Orientation | on the flat bottom | on the flat bottom |

- The 0.40 mm protrusion is exactly 2 layers at 0.20: **do not change the layer
  height without realigning `SPORG` and `FLOOR_Z`** (both must remain integer
  multiples of the layer height, otherwise the slicer rounds in an uncontrolled way).
- The relief is a height field: maximum slope ~80°, no undercut possible, so
  supports are never needed by construction.
- The track is a 344 mm loop up to 22.2 mm tall and 0.90 mm thick:
  detach it from the bed patiently, starting from a tall section.
- Use the **same XY compensation** used for the test piece.
- Base can be glued onto a wooden board for the *alpen-werk* effect.

---

## 9. Code Architecture

```
rilievo3d_v1.py           approach A pipeline (incised track) — saved in repo
rilievo3d_intarsio.py     approach B main pipeline (inlay, two pieces)
dem.py                    .hgt tile reading/sampling
provino_taratura.py       calibration test piece generator
verifica_congruenza.py    independent congruence check between the two STLs
piante.py                 previews (framing, plan view, sections)
hgt/                      N45E006.hgt, N45E007.hgt
```

### `dem.py`

- `sample(lat, lon)` — bilinear sampling with tile cache, automatically handles
  mosaicking across adjacent tiles
- `grid(lat0, lat1, lon0, lon1, n)` — regular grid, also returns width/height in metres

### `rilievo3d_intarsio.py`

Key function `build(cl, part)` with `part ∈ {"rilievo", "traccia"}`.
Both pieces pass through the same machinery:

1. grid + filtered DEM + distance field from the centreline;
2. each cell split into **2 triangles** (never quads: a triangle with 3 signed
   values has no ambiguous cases, a quad does — saddle cells);
3. triangles entirely on one side → emitted in bulk, vectorised;
4. mixed triangles → collected, then **batch bisection** of contours, then
   Sutherland-Hodgman clipping and fan;
5. vertical walls between surface contour and floor contour;
6. for the relief: perimeter walls + fan floor.

Orientation convention: traversing the contour with **material on the left**,
the wall below edge A→B is built as
`quad(A_top, A_bottom, B_bottom, B_top)` → outward normal to the right of the
traversal direction, i.e. towards the void.

### Centreline Processing

```
GPX → projection into model coordinates
    → resampling at 0.02 mm
    → gaussian_filter1d with sigma = SMOOTH_MM
    → resampling at CL_STEP = 0.05 mm
```

Smoothing is necessary: the raw GPX has GPS jitter of ~5 m which at this scale
produces enormous curvatures. With sigma 0.10 mm (14.7 m on the ground, below
the DEM resolution) the development drops from 379.5 to 344.3 mm — 9% less,
which is the portion of length due to GPS noise, not the trail.

---

## 10. Status and Next Steps

### Done

- Approach A completed and printed (180 mm, incised track)
- Approach B completed and validated (150 mm, two pieces)
- Calibration test piece printed and interpreted → recess 1.15 / track 0.90
- Independent congruence verification on the STLs

### Open

1. **Physical print of the two-piece model** — not yet done. It is the only
   missing data point: everything else has been verified numerically only.
2. **Chamfers on the final model** — reintroduce as a two-level step (§4.7).
3. **Clearance margin** — evaluate `GRID` 1000 or `TRACK_W` 0.86 (§7.2).
4. **Loop closure** — the GPX has a 277 m gap between start and finish. In the
   model the two branches merge anyway, but it is worth deciding whether this is
   intentional or whether the track should be explicitly closed.
5. **Reapplication to new locations** — new GPX + tiles + bbox. Always redo §4.5
   (self-proximity at the new scale) before building.

### When Resuming in Claude Code

- Maintain the **no CAD libraries** constraint: it is a design choice.
- Do not touch `FLOOR_Z`, `SPORG`, `GROOVE_W`, `TRACK_W` without rerunning
  `verifica_congruenza.py`: they are coupled between the two files.
- Any mesh modification must be closed with checks §7.1 **and** §7.2.
  A χ different from 2 is not automatically an error (the track has χ = 0), but it
  must be explained topologically before accepting it.
- The user prefers to **see plan views and sections before** the files are generated.
  This preference was stated explicitly and proved useful: it caught the test piece
  phase error visually.
- The user identifies geometric anomalies visually with good precision: if something
  is flagged, **measure it** rather than explaining why it cannot be.
- Conversations are conducted in Italian.

---

*Elevation data: SRTM 1 arcsecond (NASA/USGS). Track: user's GPX file.*
