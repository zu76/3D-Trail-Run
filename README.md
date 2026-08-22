# 3D Trail Run

Generate printable 3D STL terrain models of trail running routes, in the style of
alpine relief plaques (*alpen-werk #RB60*). A GPS track is embedded into the
terrain, and a name label is generated to go with it.

## Read this first: the project assumes a single-filament printer

Everything here is designed around an **FDM printer with one extruder and one
filament at a time**. That constraint is not incidental — it is the reason for
most of the engineering in this repository:

- The coloured track is a **separate physical part**, printed on its own in a
  second filament and pressed into a recess, because the relief and the track
  cannot be printed in two colours in one pass. That is where the whole
  distance-field clearance problem comes from.
- The label is **individual letters plus a snap-off runner**, glued on by hand,
  rather than lettering printed directly into the base in a contrasting colour.

**If you have a multi-material printer** (AMS, MMU, IDEX, or a toolchanger), the
sensible approach is probably a different one: print the relief and the track as
a single object with a filament change, and put the lettering straight into the
model. You would not need the recess, the 0.150 mm clearance, the congruence
check, or the snap-off runner. Much of this repository would be solving a problem
you do not have.

## Results

![Finished piece: white relief with the red track inlay, mounted on a wooden base with the 3D printed label letters glued below](docs/images/final-product.jpeg)

*Finished piece — approach B. The GPS track is a separately printed red insert
seated in a recess in the white relief, and the label letters are glued to the
oak base with the runner snapped off and discarded.*

![Side view showing the relief block standing on the wooden base, with the label letters in the foreground](docs/images/final-product-side.jpeg)

*Side view. The vertical exaggeration is 1.3, and the flat plinth under the
terrain is what the model stands on.*

| Two pieces off the bed | Insert seated in the recess |
|---|---|
| ![The white relief and the red track insert printed separately, lying on the printer bed](docs/images/print-two-pieces.jpeg) | ![The red insert pressed into the groove in the white relief](docs/images/print-assembly.jpeg) |

The recess and the insert are level sets of the same distance field, which is why
the insert drops in along its whole length, including the switchbacks, at a
uniform clearance. The piece photographed was built at 0.125 mm per side and was
stiff to assemble; the current default is 0.150 mm.

## Current setup

These are the values the code uses today. The reasoning is under
[Key decisions](#key-decisions); the history is in [CHANGELOG.md](CHANGELOG.md).

### Relief and track — `rilievo3d_intarsio.py`

| Parameter | Value | Note |
|---|---|---|
| Frame | **150 x 150 mm square** | squared on the track bbox centre, 12 % margin |
| Vertical exaggeration | 1.3 | |
| Plinth | 10 mm | flat base the model stands on |
| Recess floor `FLOOR_Z` | 6.0 mm | |
| Groove width `GROOVE_W` | **1.20 mm** | |
| Track width `TRACK_W` | 0.90 mm | |
| Clearance | **0.150 mm per side** | `(GROOVE_W - TRACK_W) / 2` |
| Protrusion `SPORG` | 0.40 mm | how far the insert stands above the terrain |
| Distance-field grid | 700, or 1000 when clearance is tight | |

`FLOOR_Z`, `SPORG`, `GROOVE_W` and `TRACK_W` are coupled — change any one and
re-run `verifica_congruenza.py`.

### Label — `etichetta3d.py`

| Parameter | Value | Note |
|---|---|---|
| Font | Impact | chosen on counter size, see below |
| Depth | 2.00 mm | back face on the bed, chamfer facing up |
| Front chamfer | 0.40 mm | built as a distance-field roof |
| Min air gap between letters | 0.50 mm | enforced by adding tracking |
| Spine | 1.0 mm tall x 1.0 mm deep | |
| Post | 0.80 mm wide | length varies per letter |
| Snap notch | 0.45 mm wide x 0.35 mm long | the deliberate break point |
| Bridge for split glyphs | 0.45 x 0.60 mm | joins an `i` dot to its stem |

### Projects built so far

| Project | Route | Relief | Label |
|---|---|---|---|
| `GTC55-2026` | Gran Trail Courmayeur, 55.66 km, ~3066 m D+ | 150 mm, printed | 180 mm, printed |
| `Valgrosina-2026` | Trail Valgrosina 38k, 37.70 km, ~2518 m D+ | 150 mm, generated | 180 mm, generated |

## Key decisions

**Two pieces derived from one distance field.** The recess and the insert are
level sets of the *same* field, so they are concentric by construction and the
perpendicular clearance is exactly `(GROOVE_W - TRACK_W) / 2` everywhere. A
sweep-and-offset construction self-intersects at tight switchbacks, where the
turn radius is smaller than the corridor half-width. This also means merging is
safe: where two legs of a route run close enough that their grooves fuse, the
insert fuses identically and still fits.

**Contours by bisection on the true distance, not by interpolating the field.**
Linear interpolation of a sampled distance field is wrong by up to half a cell
near the medial axis. Forty-five bisection steps against the real KD-tree
distance put the track at 0.4500 and the recess at 0.5750 exactly.

**Clearance is 0.150 mm per side because of how the part felt, not what it
measured.** At 0.125 the GTC55 insert did seat and the piece was completed, but
it was stiff and awkward to do safely — and every numerical check had passed.
Feedback from a printed part outranks a passing validation. The step size comes
off the calibration ladder in `provino_taratura.py` (1.05 / 1.10 / 1.15 / 1.20 /
1.25); 1.15 was the rung in use, 1.20 is one further.

**Relief frames are square, even for routes that are not.** Trail Valgrosina is a
2.28 x 11.18 km sliver; cropped to its own proportions it would be a 37 x 180 mm
ribbon with a label five times wider than the relief. In a 150 mm square it fills
89 % of the height, the valley reads properly, and the pieces form a consistent
set.

**The label is letters only, held by a removable runner.** No plate, no band,
nothing behind or between the letters — you can see through every gap. A straight
rail above the text reaches each letter through a post ending in a thin notch;
glue the letters, then break the runner off and discard it. The rail is straight
rather than stepped because stiffness along the label is its entire purpose, and
because the notch, not the post, sets the break force.

**Font choice is driven by the counters, not by stroke width.** Below roughly
0.45 mm an enclosed hole (`a e o B 0 6`) closes up while printing and the letter
reads as a solid blob. Arial Narrow Bold was rejected for measuring 0.22 mm at
the curve terminals of `a c e`. This constraint, not stroke thickness, is what
sets the minimum readable label size.

**The chamfer is a distance-field roof, not an inward offset.** A 0.40 mm chamfer
needs 0.80 mm of material and the narrowest neck in the GTC55 text is 0.39 mm, so
an offset collapses the front face and self-intersects. As
`z = min(depth, depth - chamfer + d)` it degrades into a ridge where the glyph is
narrow instead of failing.

**Print orientation is forced, not chosen.** Back face on the bed, chamfer facing
up: printing chamfer-down would make the first layer of the `l` stem only 0.3 mm
wide. That in turn puts the runner flush with the back face so it prints without
supports.

**No CAD libraries, and validation that can actually fail.** Meshes are built
triangle by triangle and checked for manifoldness, Euler characteristic and
signed volume against an independent analytical estimate. The label's `chi = 158`
is a worked-out prediction from shell count and glyph genus, so a filled-in
counter or an open shell breaks it — "it looks fine in the slicer" would not have.

## Approaches

| | Approach A — Incised track | Approach B — Inlay (two pieces) |
|---|---|---|
| Script | `rilievo3d_v1.py` | `rilievo3d_intarsio.py` |
| Output | single STL, groove coloured by hand | relief STL + track STL, two filaments |
| Status | **completed and printed** (180 mm) | **completed and printed** (150 mm) |

Approach B is the one in current use.

## Usage

### Relief and track

```bash
python3 rilievo3d_intarsio.py --gpx your_track.gpx --name Project-2026 \
  --bbox 46.2854 46.3981 10.1826 10.3457 --size 150

# tighten the contour discretisation if the fit check complains
python3 rilievo3d_intarsio.py --gpx your_track.gpx --name Project-2026 \
  --bbox 46.2854 46.3981 10.1826 10.3457 --size 150 --grid 1000

# independent fit check, reading only the two STLs
python3 verifica_congruenza.py \
  --rel 3d-outputs/Project-2026/Project-2026_150mm_rilievo.stl \
  --trk 3d-outputs/Project-2026/Project-2026_150mm_traccia.stl
```

If the fit check reports `DA CONTROLLARE`, look at the *mean* clearance before
assuming a design fault. A mean sitting on nominal with a low minimum means the
contour discretisation is pinching where the corridor merges, and the first lever
is `--grid 1000` rather than changing `TRACK_W`.

### Label

```bash
python3 etichetta3d.py --name Project-2026 --text "2026 My Race 38k" \
  --fit --max-len 180
python3 etichetta3d.py --name Project-2026 --part letters   # letters only
```

`--fit` solves for the largest cap height that fits the budget. It is not a
ratio: `MIN_GAP` is absolute, so the air gaps take a growing share of the width as
the letters shrink — 0.47 mm of added tracking at 180 mm against 3.35 mm at
100 mm.

Feature sizes scale linearly with cap height, so they never need re-measuring:

| Cap height | Narrowest neck | Narrowest counter | Bulk stroke |
|---|---|---|---|
| 6.50 mm | 0.39 mm | 0.48 mm | 1.6–2.3 mm |
| 9.32 mm | 0.56 mm | 0.69 mm | 2.3–3.3 mm |

## Output convention

Generated STLs go in a per-project subfolder of `3d-outputs/`, with the key
dimension in the filename so several sizes coexist:

```
3d-outputs/GTC55-2026/GTC55-2026_label_180mm.stl
```

STL files are build artefacts (10–100 MB each) and are not tracked in git.

## Data

SRTM 1 arcsecond `.hgt` tiles are required and are **not** included in the repo
(binary, ~25 MB each). Place them in `./hgt/`, which is also untracked:

```
hgt/N45E006.hgt      # GTC55
hgt/N45E007.hgt      # GTC55
hgt/N46E010.hgt      # Valgrosina
```

Mirror: `https://raw.githubusercontent.com/danielementary/Alpano/master/NxxEyyy.hgt`

## Dependencies

```
numpy scipy matplotlib
```

No CAD libraries — no trimesh, shapely, open3d or CGAL. Meshes are built and
validated entirely from scratch.

## Documentation map

| File | What it is |
|---|---|
| `README.md` | **current setup and decisions** — start here |
| [CHANGELOG.md](CHANGELOG.md) | running log of changes, decisions and rejected approaches |
| [CLAUDE.md](CLAUDE.md) | working conventions for contributors |
| [docs/project_handoff.md](docs/project_handoff.md) | **historical** — the original design record, deliberately not updated |

## License

MIT
