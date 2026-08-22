# Working conventions

## Changelog is mandatory

Every change to this project gets an entry in `CHANGELOG.md`, including attempts
that did not work. Log the decision and its reasoning, not just the diff — a
rejected approach and the measurement that rejected it is often worth more later
than the approach that was kept.

Add entries under `## [Unreleased]` as work happens, then move them into a dated
section when the work concludes. Use the Keep a Changelog headings (`Added`,
`Changed`, `Fixed`, `Removed`), plus these project-specific ones where relevant:

- `Generated` — printable artefacts produced, with dimensions and validation results.
- `Decisions` — a choice made, with the reason it beat the alternative.
- `Measurement methods that gave wrong answers` — techniques that silently
  produced plausible but false numbers. This project has already been burned
  three times by such methods.
- `Open` — known-unresolved items, so they are not silently forgotten.
- `Environment` — toolchain changes such as installed dependencies.

## Geometry is not done until it is validated

Any change touching printable geometry must be re-validated before it counts as
finished: manifold check, Euler characteristic, and signed volume against an
independent analytical estimate. Record the numbers in the changelog. State
plainly if validation was not run.

Prefer a validation that would actually fail. The label's `chi = 158` is a
worked-out prediction from shell count and glyph genus, so a filled-in counter or
an open shell breaks it; "the mesh looks fine in the slicer" would not have.

`FLOOR_Z`, `SPORG`, `GROOVE_W` and `TRACK_W` are coupled. Changing any of them
requires re-running `verifica_congruenza.py`.

Numbers that pass every check can still be wrong in the hand. The GTC55 insert
validated cleanly at 0.125 mm per side and was still stiff to assemble, so the
clearance is now 0.150 (`GROOVE_W` 1.20 against `TRACK_W` 0.90). Feedback from a
printed part outranks a passing validation.

If `verifica_congruenza.py` reports DA CONTROLLARE on clearance, check the mean
before assuming a design fault. A mean sitting on the 0.125 mm nominal with a low
minimum means contour discretisation is pinching where the corridor merges, and
the first lever is `--grid 1000` rather than changing `TRACK_W`. On Trail
Valgrosina that moved the minimum from 0.0844 to 0.1007 mm and flipped the
verdict, at four times the relief facet count.

## No CAD libraries

No trimesh, shapely, open3d or CGAL. Meshes are built triangle by triangle and
validated from scratch. Distance fields and level sets are the house idiom for
offsets, clearances and chamfers — see `rilievo3d_intarsio.py` and the chamfer
roof in `etichetta3d.py`.

## Standard frame

Relief models are **150 x 150 mm square** unless the request says otherwise.
Frame the square on the centre of the track bounding box with a 12 % margin on
its longest dimension. Elongated routes therefore sit as a ribbon inside a
square of terrain rather than being cropped to their own proportions.

## Output convention

Generated STLs go in `3d-outputs/<project-name>/`, with the key dimension in the
filename so several versions coexist:

```
3d-outputs/GTC55-2026/GTC55-2026_label_180mm.stl
```

STLs are build artefacts and are not tracked in git.

## Previews before printable files

Show a preview and agree the design before generating an STL. When previewing
type, draw real font outlines — never filled rectangles standing in for glyphs,
which has caused several rounds of misunderstanding.

## Documentation is English

The original handoff document was Italian; English is the standard for everything
in the repository. Conversation may be in Italian.
