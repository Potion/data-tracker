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

