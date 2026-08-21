# 3D Trail Run

Generate printable 3D STL terrain models of trail running routes, in the style
of alpine relief plaques (*alpen-werk #RB60*). The GPS track is embedded into
the model either as an incised groove (approach A) or as a coloured inlay insert
printed separately (approach B).

## Reference case

**Gran Trail Courmayeur (GTC)** — 55.66 km, ~3,066 m elevation gain, Mont Blanc
massif, Valle d'Aosta.

## Approaches

| | Approach A — Incised track | Approach B — Inlay (two pieces) |
|---|---|---|
| Script | `rilievo3d_v1.py` | `rilievo3d_intarsio.py` *(in progress)* |
| Output | single STL, groove coloured by hand | relief STL + track STL, different filaments |
| Status | **completed and printed** (180 mm) | **validated numerically** (150 mm), not yet printed |

See [docs/project_handoff.md](docs/project_handoff.md) for the full design
history, parameters, known errors, and validation results.

## Quick start (Approach A)

```bash
# Preview framing
python3 rilievo3d_v1.py --gpx your_track.gpx --hgt-dir ./hgt --preview

# Generate STL
python3 rilievo3d_v1.py \
  --gpx your_track.gpx --hgt-dir ./hgt \
  --bbox 45.7010 45.8988 6.7880 7.0713 \
  --size 180 --vex 1.3 --plinth 12 \
  --out model.stl
```

## Data

SRTM 1 arcsecond `.hgt` tiles are required and are **not** included in the repo
(binary, ~25 MB each). Place them in `./hgt/`:

```
hgt/N45E006.hgt
hgt/N45E007.hgt
```

Mirror: `https://raw.githubusercontent.com/danielementary/Alpano/master/NxxEyyy.hgt`

## Dependencies

```
numpy scipy matplotlib
```

No CAD libraries (no trimesh, shapely, open3d, CGAL). Meshes are built and
validated entirely from scratch.

## License

MIT
