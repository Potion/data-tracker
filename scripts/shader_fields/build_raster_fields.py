#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

try:
    import tifffile  # type: ignore
except Exception:  # pragma: no cover
    tifffile = None

try:
    from export_timeseries_field import choose_candidate
    from export_timeseries_field import collect_candidates
    from export_timeseries_field import unwrap_payload
except Exception:  # pragma: no cover
    choose_candidate = None
    collect_candidates = None
    unwrap_payload = None


@dataclass
class PipelineArtifacts:
    sdf_field: np.ndarray
    influence_field: np.ndarray
    color_coord_field: np.ndarray | None
    metadata: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic offline raster fields (SDF + influence) for realtime shader sampling."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Input records file (.json or .csv).")
    source.add_argument(
        "--input-dir",
        type=Path,
        help="Existing raw JSON dataset folder (e.g. data/raw_json/35_years_s_p_500_daily).",
    )
    parser.add_argument("--config", type=Path, default=None, help="Pipeline config JSON.")
    parser.add_argument("--width", type=int, required=True, help="Output width in pixels.")
    parser.add_argument("--height", type=int, required=True, help="Output height in pixels.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory.")
    parser.add_argument("--prefix", default=None, help="Output prefix override.")
    parser.add_argument(
        "--series",
        default="auto",
        help="Candidate selector for --input-dir extraction (index/id/substr or auto).",
    )
    parser.add_argument("--quiet", action="store_true", help="Reduce output logging.")
    return parser.parse_args()


def log(message: str, quiet: bool) -> None:
    if not quiet:
        print(message)


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        v = float(value)
        return v if math.isfinite(v) else default
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return default
        try:
            v = float(s)
            return v if math.isfinite(v) else default
        except ValueError:
            return default
    return default


def load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = load_json(path)
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
            records = payload["records"]
        else:
            raise ValueError("JSON input must be a list or object with a 'records' list.")
        return [r for r in records if isinstance(r, dict)]

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    raise ValueError(f"Unsupported input extension for {path}. Use .json or .csv.")


def load_raw_series_points(input_dir: Path, selector: str = "auto") -> list[tuple[float, float]]:
    if collect_candidates is None or choose_candidate is None or unwrap_payload is None:
        raise RuntimeError(
            "Raw series extraction requires export_timeseries_field helpers to be importable."
        )
    files = [p for p in sorted(input_dir.rglob("*.json")) if not p.name.startswith("_")]
    if not files:
        raise ValueError(f"No JSON files found under {input_dir}")
    merged: dict[str, float] = {}
    for file_path in files:
        payload = load_json(file_path)
        root = unwrap_payload(payload)
        candidates = collect_candidates(root)
        if not candidates:
            continue
        chosen = choose_candidate(candidates, selector)
        for ts, value in chosen.points:
            merged[ts.isoformat()] = float(value)
    if not merged:
        raise ValueError(f"No valid time-series points found under {input_dir}")
    ordered = sorted(merged.items(), key=lambda kv: kv[0])
    return [(float(i), float(v)) for i, (_, v) in enumerate(ordered)]


def series_points_to_records(points: list[tuple[float, float]], config: dict[str, Any]) -> list[dict[str, Any]]:
    if not points:
        return []
    rm = config.get("series_mapping", {})
    base_radius = float(rm.get("base_radius_px", 8.0))
    radius_scale = float(rm.get("radius_from_abs_return_scale", 1400.0))
    base_weight = float(rm.get("base_weight", 1.0))
    weight_scale = float(rm.get("weight_from_abs_return_scale", 90.0))
    color_scale = float(rm.get("color_coord_from_abs_return_scale", 20.0))
    min_radius = float(rm.get("min_radius_px", 2.0))
    max_radius = float(rm.get("max_radius_px", 64.0))
    shape = str(rm.get("shape", config.get("raster", {}).get("default_shape", "circle")))

    records: list[dict[str, Any]] = []
    prev: float | None = None
    for x, y in points:
        if prev is None or abs(prev) < 1e-12:
            abs_ret = 0.0
        else:
            abs_ret = abs((y - prev) / prev)
        radius = float(np.clip(base_radius + abs_ret * radius_scale, min_radius, max_radius))
        weight = base_weight + abs_ret * weight_scale
        color_coord = float(np.clip(abs_ret * color_scale, 0.0, 1.0))
        records.append(
            {
                "x": float(x),
                "y": float(y),
                "radius": radius,
                "weight": float(weight),
                "shape": shape,
                "color_coord": color_coord,
            }
        )
        prev = y
    return records


def default_config() -> dict[str, Any]:
    return {
        "coord_domain": {
            "auto": True,
            "padding_ratio": 0.05,
            "x_min": None,
            "x_max": None,
            "y_min": None,
            "y_max": None,
        },
        "raster": {
            "default_shape": "circle",
            "radius_scale": 1.0,
            "default_radius_px": 18.0,
            "max_stamp_radius_px": 256.0,
            "influence_falloff_sigma_px": 18.0,
        },
        "sdf": {
            "distance_units": "pixels",  # pixels | uv
            "normalize_mode": "clip_scale",  # none | clip_scale
            "clip_distance_px": 128.0,
        },
        "influence": {
            "post_blur_sigma_px": 2.0,
            "normalize_mode": "percentile_clip",  # none | minmax | percentile_clip
            "percentile_hi": 99.5,
        },
        "color_coord": {
            "enabled": False,
            "default_value": 0.5,
        },
        "output": {
            "format": "tiff-f16",  # tiff-f16 | npy-f32
            "include_hash_manifest": True,
        },
        "series_mapping": {
            "shape": "circle",
            "base_radius_px": 8.0,
            "radius_from_abs_return_scale": 1400.0,
            "base_weight": 1.0,
            "weight_from_abs_return_scale": 90.0,
            "color_coord_from_abs_return_scale": 20.0,
            "min_radius_px": 2.0,
            "max_radius_px": 64.0,
        },
    }


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def records_minmax(records: list[dict[str, Any]], key: str) -> tuple[float, float] | None:
    vals = [parse_float(r.get(key)) for r in records]
    good = [v for v in vals if v is not None]
    if not good:
        return None
    return (float(min(good)), float(max(good)))


def resolve_coord_domain(config: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, float]:
    cd = config["coord_domain"]
    auto = bool(cd.get("auto", True))
    if auto:
        xr = records_minmax(records, "x")
        yr = records_minmax(records, "y")
        if xr is None or yr is None:
            raise ValueError("Could not infer x/y domain; input records missing numeric x and y.")
        x_min, x_max = xr
        y_min, y_max = yr
        if abs(x_max - x_min) < 1e-9:
            x_max = x_min + 1.0
        if abs(y_max - y_min) < 1e-9:
            y_max = y_min + 1.0
        padding_ratio = float(cd.get("padding_ratio", 0.05))
        x_pad = (x_max - x_min) * padding_ratio
        y_pad = (y_max - y_min) * padding_ratio
        return {
            "x_min": x_min - x_pad,
            "x_max": x_max + x_pad,
            "y_min": y_min - y_pad,
            "y_max": y_max + y_pad,
        }

    keys = ("x_min", "x_max", "y_min", "y_max")
    resolved: dict[str, float] = {}
    for k in keys:
        v = parse_float(cd.get(k))
        if v is None:
            raise ValueError(f"coord_domain.{k} is required when auto=false.")
        resolved[k] = v
    if abs(resolved["x_max"] - resolved["x_min"]) < 1e-9:
        resolved["x_max"] = resolved["x_min"] + 1.0
    if abs(resolved["y_max"] - resolved["y_min"]) < 1e-9:
        resolved["y_max"] = resolved["y_min"] + 1.0
    return resolved


def map_to_pixel(
    x: float, y: float, width: int, height: int, domain: dict[str, float]
) -> tuple[float, float]:
    nx = (x - domain["x_min"]) / (domain["x_max"] - domain["x_min"])
    ny = (y - domain["y_min"]) / (domain["y_max"] - domain["y_min"])
    nx = float(np.clip(nx, 0.0, 1.0))
    ny = float(np.clip(ny, 0.0, 1.0))
    px = nx * (width - 1)
    py = (1.0 - ny) * (height - 1)
    return px, py


def gaussian_kernel_1d(sigma: float) -> np.ndarray:
    if sigma <= 0.0:
        return np.array([1.0], dtype=np.float32)
    radius = max(1, int(math.ceil(3.0 * sigma)))
    x = np.arange(-radius, radius + 1, dtype=np.float32)
    k = np.exp(-0.5 * (x / float(sigma)) ** 2).astype(np.float32)
    k /= np.sum(k)
    return k


def convolve1d_axis(arr: np.ndarray, kernel: np.ndarray, axis: int) -> np.ndarray:
    pad = len(kernel) // 2
    if axis == 0:
        padded = np.pad(arr, ((pad, pad), (0, 0)), mode="edge")
        out = np.empty_like(arr, dtype=np.float32)
        for y in range(arr.shape[0]):
            out[y, :] = np.tensordot(kernel, padded[y : y + len(kernel), :], axes=(0, 0))
        return out
    padded = np.pad(arr, ((0, 0), (pad, pad)), mode="edge")
    out = np.empty_like(arr, dtype=np.float32)
    for x in range(arr.shape[1]):
        out[:, x] = np.tensordot(kernel, padded[:, x : x + len(kernel)], axes=(0, 1))
    return out


def gaussian_blur(arr: np.ndarray, sigma: float) -> np.ndarray:
    k = gaussian_kernel_1d(sigma)
    if len(k) == 1:
        return arr.astype(np.float32)
    tmp = convolve1d_axis(arr.astype(np.float32), k, axis=1)
    return convolve1d_axis(tmp, k, axis=0)


def dt_chamfer(binary_mask: np.ndarray) -> np.ndarray:
    # Approximate Euclidean distance transform with deterministic 3-4 chamfer passes.
    inf = np.float32(1e9)
    dist = np.where(binary_mask > 0, 0.0, inf).astype(np.float32)
    h, w = dist.shape
    w_ortho = np.float32(1.0)
    w_diag = np.float32(math.sqrt(2.0))

    # Forward pass
    for y in range(h):
        for x in range(w):
            v = dist[y, x]
            if y > 0:
                v = min(v, dist[y - 1, x] + w_ortho)
                if x > 0:
                    v = min(v, dist[y - 1, x - 1] + w_diag)
                if x + 1 < w:
                    v = min(v, dist[y - 1, x + 1] + w_diag)
            if x > 0:
                v = min(v, dist[y, x - 1] + w_ortho)
            dist[y, x] = v

    # Backward pass
    for y in range(h - 1, -1, -1):
        for x in range(w - 1, -1, -1):
            v = dist[y, x]
            if y + 1 < h:
                v = min(v, dist[y + 1, x] + w_ortho)
                if x > 0:
                    v = min(v, dist[y + 1, x - 1] + w_diag)
                if x + 1 < w:
                    v = min(v, dist[y + 1, x + 1] + w_diag)
            if x + 1 < w:
                v = min(v, dist[y, x + 1] + w_ortho)
            dist[y, x] = v

    return dist


def compute_signed_distance(inside_mask: np.ndarray) -> np.ndarray:
    inside = inside_mask.astype(bool)
    outside_dist = dt_chamfer(inside.astype(np.uint8))
    inside_dist = dt_chamfer((~inside).astype(np.uint8))
    return outside_dist - inside_dist


def normalize_sdf(sdf_px: np.ndarray, config: dict[str, Any], width: int, height: int) -> tuple[np.ndarray, str, dict[str, float]]:
    sdf_cfg = config["sdf"]
    units = str(sdf_cfg.get("distance_units", "pixels"))
    sdf = sdf_px.astype(np.float32)
    if units == "uv":
        scale = float(max(width, height))
        sdf = sdf / scale
    mode = str(sdf_cfg.get("normalize_mode", "clip_scale"))
    if mode == "none":
        return sdf, units, {"min": float(np.min(sdf)), "max": float(np.max(sdf))}
    clip_px = float(sdf_cfg.get("clip_distance_px", 128.0))
    clip = clip_px / float(max(width, height)) if units == "uv" else clip_px
    clip = max(1e-6, float(clip))
    sdf = np.clip(sdf / clip, -1.0, 1.0).astype(np.float32)
    return sdf, units, {"min": -1.0, "max": 1.0}


def normalize_influence(influence: np.ndarray, config: dict[str, Any]) -> tuple[np.ndarray, dict[str, float]]:
    infl_cfg = config["influence"]
    mode = str(infl_cfg.get("normalize_mode", "percentile_clip"))
    arr = influence.astype(np.float32)
    if mode == "none":
        return arr, {"min": float(np.min(arr)), "max": float(np.max(arr))}
    if mode == "minmax":
        lo = float(np.min(arr))
        hi = float(np.max(arr))
        if hi - lo <= 1e-9:
            return np.zeros_like(arr), {"min": 0.0, "max": 1.0}
        out = (arr - lo) / (hi - lo)
        return out.astype(np.float32), {"min": 0.0, "max": 1.0}
    hi_pct = float(infl_cfg.get("percentile_hi", 99.5))
    hi = float(np.percentile(arr, hi_pct))
    hi = max(1e-6, hi)
    out = np.clip(arr / hi, 0.0, 1.0)
    return out.astype(np.float32), {"min": 0.0, "max": 1.0}


def shape_circle(
    dx: np.ndarray, dy: np.ndarray, radius_px: float, sigma_px: float, weight: float
) -> tuple[np.ndarray, np.ndarray]:
    d = np.sqrt(dx * dx + dy * dy)
    occ = (d <= radius_px).astype(np.float32)
    sigma = max(1e-6, float(sigma_px))
    inf = float(weight) * np.exp(-0.5 * (d / sigma) ** 2).astype(np.float32)
    return occ, inf


def shape_square(
    dx: np.ndarray, dy: np.ndarray, radius_px: float, sigma_px: float, weight: float
) -> tuple[np.ndarray, np.ndarray]:
    d_inf = np.maximum(np.abs(dx), np.abs(dy))
    occ = (d_inf <= radius_px).astype(np.float32)
    sigma = max(1e-6, float(sigma_px))
    inf = float(weight) * np.exp(-0.5 * (d_inf / sigma) ** 2).astype(np.float32)
    return occ, inf


SHAPE_REGISTRY: dict[str, Callable[[np.ndarray, np.ndarray, float, float, float], tuple[np.ndarray, np.ndarray]]] = {
    "circle": shape_circle,
    "square": shape_square,
}


def rasterize_fields(
    records: list[dict[str, Any]],
    width: int,
    height: int,
    config: dict[str, Any],
    domain: dict[str, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, dict[str, int]]:
    raster_cfg = config["raster"]
    color_cfg = config["color_coord"]
    default_shape = str(raster_cfg.get("default_shape", "circle"))
    default_radius = float(raster_cfg.get("default_radius_px", 18.0))
    radius_scale = float(raster_cfg.get("radius_scale", 1.0))
    max_radius = float(raster_cfg.get("max_stamp_radius_px", 256.0))
    sigma_px = float(raster_cfg.get("influence_falloff_sigma_px", 18.0))
    color_enabled = bool(color_cfg.get("enabled", False))
    color_default = float(color_cfg.get("default_value", 0.5))

    occupancy_seed = np.zeros((height, width), dtype=np.float32)
    influence_seed = np.zeros((height, width), dtype=np.float32)
    color_acc = np.zeros((height, width), dtype=np.float32) if color_enabled else None
    color_w = np.zeros((height, width), dtype=np.float32) if color_enabled else None
    yy, xx = np.mgrid[0:height, 0:width]

    stats = {"input_records": len(records), "valid_records": 0, "unknown_shape_fallbacks": 0}
    sorted_records = sorted(records, key=lambda r: canonical_json_bytes(r))

    for rec in sorted_records:
        x = parse_float(rec.get("x"))
        y = parse_float(rec.get("y"))
        if x is None or y is None:
            continue
        px, py = map_to_pixel(x, y, width, height, domain)
        r = parse_float(rec.get("radius"), default_radius)
        assert r is not None
        radius_px = float(np.clip(r * radius_scale, 1.0, max_radius))
        weight = parse_float(rec.get("weight"), None)
        if weight is None:
            weight = parse_float(rec.get("intensity"), 1.0)
        weight = float(weight if weight is not None else 1.0)
        shape_name = str(rec.get("shape", default_shape)).strip().lower()
        fn = SHAPE_REGISTRY.get(shape_name)
        if fn is None:
            fn = SHAPE_REGISTRY.get(default_shape, shape_circle)
            stats["unknown_shape_fallbacks"] += 1
        dx = xx.astype(np.float32) - np.float32(px)
        dy = yy.astype(np.float32) - np.float32(py)
        occ, inf = fn(dx, dy, radius_px, sigma_px, weight)
        occupancy_seed = np.maximum(occupancy_seed, occ)
        influence_seed += inf
        if color_enabled and color_acc is not None and color_w is not None:
            color_value = parse_float(rec.get("color_coord"), color_default)
            color_value = float(color_value if color_value is not None else color_default)
            color_acc += inf * color_value
            color_w += inf
        stats["valid_records"] += 1

    color_field: np.ndarray | None = None
    if color_enabled and color_acc is not None and color_w is not None:
        safe_w = np.where(color_w > 1e-8, color_w, 1.0)
        color_field = (color_acc / safe_w).astype(np.float32)
    return occupancy_seed, influence_seed, color_field, stats


def save_array(array: np.ndarray, path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "tiff-f16":
        if tifffile is None:
            raise RuntimeError("TIFF export requires 'tifffile'. Install with: pip install tifffile")
        tifffile.imwrite(path, array.astype(np.float16), photometric="minisblack")
        return
    np.save(path, array.astype(np.float32))


def load_config(path: Path | None) -> dict[str, Any]:
    cfg = default_config()
    if path is None:
        return cfg
    user_cfg = load_json(path)
    if not isinstance(user_cfg, dict):
        raise ValueError("Config must be a JSON object.")
    return deep_merge(cfg, user_cfg)


def build_artifacts(
    records: list[dict[str, Any]],
    width: int,
    height: int,
    config: dict[str, Any],
    prefix: str,
) -> PipelineArtifacts:
    domain = resolve_coord_domain(config, records)
    occupancy_seed, influence_seed, color_field, raster_stats = rasterize_fields(
        records=records, width=width, height=height, config=config, domain=domain
    )

    inside_mask = occupancy_seed >= 0.5
    sdf_px = compute_signed_distance(inside_mask)
    sdf_field, sdf_units, sdf_range = normalize_sdf(sdf_px, config, width, height)

    post_blur_sigma = float(config["influence"].get("post_blur_sigma_px", 2.0))
    influence_blurred = gaussian_blur(influence_seed, post_blur_sigma)
    influence_field, infl_range = normalize_influence(influence_blurred, config)

    if color_field is not None:
        color_field = np.clip(color_field, 0.0, 1.0).astype(np.float32)

    meta = {
        "prefix": prefix,
        "width": width,
        "height": height,
        "coord_domain": domain,
        "raster_stats": raster_stats,
        "sdf": {
            "units": sdf_units,
            "range": sdf_range,
            "sign_convention": "negative_inside_positive_outside",
        },
        "influence": {
            "range": infl_range,
        },
        "color_coord": {
            "enabled": bool(config["color_coord"].get("enabled", False)),
            "range": {"min": 0.0, "max": 1.0} if color_field is not None else None,
        },
        "config_snapshot": config,
    }
    return PipelineArtifacts(
        sdf_field=sdf_field,
        influence_field=influence_field,
        color_coord_field=color_field,
        metadata=meta,
    )


def artifact_hash(path: Path) -> str:
    with path.open("rb") as fh:
        return sha256_hex(fh.read())


def run_pipeline(
    input_path: Path | None,
    input_dir: Path | None,
    out_dir: Path,
    width: int,
    height: int,
    config: dict[str, Any],
    series_selector: str = "auto",
    prefix_override: str | None = None,
    quiet: bool = False,
) -> dict[str, Any]:
    if input_path is not None:
        records = load_records(input_path)
        inferred_name = input_path.stem
        input_descriptor = str(input_path)
    else:
        assert input_dir is not None
        points = load_raw_series_points(input_dir, selector=series_selector)
        records = series_points_to_records(points, config)
        inferred_name = input_dir.name
        input_descriptor = str(input_dir)

    prefix = prefix_override or config.get("output", {}).get("prefix") or inferred_name
    out_dir.mkdir(parents=True, exist_ok=True)

    record_sig = sha256_hex(canonical_json_bytes(sorted(records, key=lambda r: canonical_json_bytes(r))))
    config_sig = sha256_hex(canonical_json_bytes(config))
    sig = sha256_hex(f"{record_sig}:{config_sig}:{width}:{height}".encode("utf-8"))[:12]
    stem = f"{prefix}_{width}x{height}_{sig}"

    artifacts = build_artifacts(records=records, width=width, height=height, config=config, prefix=prefix)
    fmt = str(config.get("output", {}).get("format", "tiff-f16"))
    ext = ".tiff" if fmt == "tiff-f16" else ".npy"

    sdf_path = out_dir / f"{stem}_sdf{ext}"
    influence_path = out_dir / f"{stem}_influence{ext}"
    save_array(artifacts.sdf_field, sdf_path, fmt)
    save_array(artifacts.influence_field, influence_path, fmt)
    output_paths: dict[str, str] = {
        "sdf_field": str(sdf_path),
        "influence_field": str(influence_path),
    }
    log(f"Wrote {sdf_path}", quiet)
    log(f"Wrote {influence_path}", quiet)

    color_path: Path | None = None
    if artifacts.color_coord_field is not None:
        color_path = out_dir / f"{stem}_colorcoord{ext}"
        save_array(artifacts.color_coord_field, color_path, fmt)
        output_paths["color_coord_field"] = str(color_path)
        log(f"Wrote {color_path}", quiet)

    metadata = dict(artifacts.metadata)
    metadata.update(
        {
            "input_path": input_descriptor,
            "source_mode": "records_file" if input_path is not None else "raw_series_dir",
            "record_signature": record_sig,
            "config_signature": config_sig,
            "build_signature": sig,
            "outputs": output_paths,
        }
    )
    meta_path = out_dir / f"{stem}_meta.json"
    with meta_path.open("w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2, ensure_ascii=True)
    log(f"Wrote {meta_path}", quiet)

    hashes = {
        "sdf_field": artifact_hash(sdf_path),
        "influence_field": artifact_hash(influence_path),
        "meta": artifact_hash(meta_path),
    }
    if color_path is not None:
        hashes["color_coord_field"] = artifact_hash(color_path)

    hash_manifest_path: Path | None = None
    if bool(config.get("output", {}).get("include_hash_manifest", True)):
        hash_manifest_path = out_dir / f"{stem}_hashes.json"
        payload = {
            "build_signature": sig,
            "hashes": hashes,
            "files": {
                "sdf_field": str(sdf_path),
                "influence_field": str(influence_path),
                "meta": str(meta_path),
                **({"color_coord_field": str(color_path)} if color_path else {}),
            },
        }
        with hash_manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=True)
        log(f"Wrote {hash_manifest_path}", quiet)

    return {
        "build_signature": sig,
        "paths": {
            "sdf_field": str(sdf_path),
            "influence_field": str(influence_path),
            "meta": str(meta_path),
            **({"color_coord_field": str(color_path)} if color_path else {}),
            **({"hash_manifest": str(hash_manifest_path)} if hash_manifest_path else {}),
        },
        "hashes": hashes,
        "width": width,
        "height": height,
    }


def main() -> None:
    args = parse_args()
    if args.width <= 0 or args.height <= 0:
        raise ValueError("--width and --height must be > 0.")
    cfg = load_config(args.config)
    run_pipeline(
        input_path=args.input,
        input_dir=args.input_dir,
        out_dir=args.out_dir,
        width=int(args.width),
        height=int(args.height),
        config=cfg,
        series_selector=args.series,
        prefix_override=args.prefix,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    main()
