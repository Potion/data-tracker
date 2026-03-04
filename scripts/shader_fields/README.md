# Shader Field Exporter

Export JSON time-series data into single-channel textures for shader experimentation.

The tool treats data as a field (not geometry):
- 1D texture for value-over-time signal sampling
- 2D chart-space field for distance/density-style shading operations

## File

`scripts/shader_fields/export_timeseries_field.py`

## Install note

TIFF float16 output requires:

```bash
pip install tifffile
```

If `tifffile` is unavailable, use `--format npy-f32` as a fallback.

## Quick start

Single JSON file, export both textures:

```bash
python scripts/shader_fields/export_timeseries_field.py \
  --input data/raw_json/fred_us_gdp/2024.json \
  --mode both \
  --out-dir data/shader_fields
```

Directory mode (merge year files), 2D field only:

```bash
python scripts/shader_fields/export_timeseries_field.py \
  --input-dir data/raw_json/fred_us_gdp \
  --mode 2d \
  --field-type distance \
  --height 768 \
  --out-dir data/shader_fields
```

List candidates without writing outputs:

```bash
python scripts/shader_fields/export_timeseries_field.py \
  --input data/raw_json/bls_us_cpi_inflation/2024.json \
  --list-candidates
```

Select candidate explicitly:

```bash
python scripts/shader_fields/export_timeseries_field.py \
  --input some_api_response.json \
  --series 1 \
  --mode both
```

## Output files

By default:

- `<name>_1d_f16.tiff`
- `<name>_2d_field_f16.tiff`
- `<name>_meta.json`

Where:
- `name` defaults to input filename (or input directory name)
- `_meta.json` records inferred keys, selected candidate, ranges, and output paths

## Texture semantics

### 1D texture

- Shape: `H=1, W=N`
- Single channel float16
- Encodes the series after `--normalize` (`minmax`, `zscore`, or `none`)
- Use in shader as a signal texture for modulation/noise/animation mappings

### 2D field texture

- Shape: `H=height, W=N`
- Single channel float16
- `x` is time index; `y` is value domain
- `--field-type distance` (default): lower near the curve, higher farther away
- `--field-type density`: high near curve, gaussian falloff away from it
- `--field-type blurred-proxy`: thick-curve raster blurred into a soft field

This is meant for pragmatic visual exploration: strokes, glow masks, layered blending, and refraction-style distortion from gradients.

## Common options

- `--mode 1d|2d|both`
- `--normalize minmax|zscore|none`
- `--resample N|none`
- `--height <int>`
- `--value-min`, `--value-max`
- `--distance-radius-px <float>`
- `--sigma-px <float>`
- `--flip-y` / `--no-flip-y`

## Raster Field Preprocessor (SDF + Influence)

For dataset-driven shape stamping and offline field generation (to avoid realtime per-shape loops), use:

`scripts/shader_fields/build_raster_fields.py`

### Input schema

Input can be `.json` (array of records or `{ "records": [...] }`) or `.csv`.

Each record:

- required: `x`, `y`
- optional: `radius`, `weight`, `intensity`, `shape`, `color_coord`

`shape` currently supports:
- `circle` (default)
- `square` (example extension path)

Unknown shapes fall back to the configured default shape and are counted in metadata.

### Processing stages

1. Raster stage (fixed `WIDTH x HEIGHT`)
- map dataset coordinates to pixel domain
- stamp occupancy seeds (union behavior for shape silhouette)
- stamp additive influence seeds (weighted accumulation for glow/body)
- optional color coordinate accumulation

2. Distance stage
- build signed distance from occupancy mask
- sign convention: **negative inside**, **positive outside**
- configurable units (`pixels` or normalized `uv`) and optional clipping normalization

### Output files and ranges

With explicit width/height and deterministic build signature:

- `<prefix>_<WIDTH>x<HEIGHT>_<sig>_sdf.tiff|npy`
- `<prefix>_<WIDTH>x<HEIGHT>_<sig>_influence.tiff|npy`
- optional `<prefix>_<WIDTH>x<HEIGHT>_<sig>_colorcoord.tiff|npy`
- `<prefix>_<WIDTH>x<HEIGHT>_<sig>_meta.json`
- optional `<prefix>_<WIDTH>x<HEIGHT>_<sig>_hashes.json`

Field semantics:

- `sdfField`: signed distance field; union-like merged silhouettes from overlaps
- `influenceField`: additive soft energy; overlap regions rise in intensity
- `colorCoordField` (optional): weighted scalar coordinate for palette mapping

### Example invocation (explicit WIDTH/HEIGHT)

```bash
python scripts/shader_fields/build_raster_fields.py \
  --input scripts/shader_fields/fixtures/overlap_points.json \
  --config scripts/shader_fields/pipeline_config.example.json \
  --width 1920 \
  --height 1080 \
  --out-dir data/shader_fields/raster \
  --prefix bubbles
```

Directly from existing raw dataset folder (no intermediate record conversion):

```bash
python scripts/shader_fields/build_raster_fields.py \
  --input-dir data/raw_json/35_years_s_p_500_daily \
  --config scripts/shader_fields/pipeline_config.example.json \
  --width 1920 \
  --height 1080 \
  --out-dir data/shader_fields/raster \
  --prefix sp500_bubbles
```

### Deterministic validation script

```bash
python scripts/shader_fields/validate_raster_fields.py
```

Validation checks:
- output dimensions exactly match `WIDTH`/`HEIGHT`
- deterministic hashes for same input + params
- overlapping circles merge in SDF silhouette
- influence increases in overlap regions
- arbitrary shape path works (square + unknown-shape fallback scaffold)
