#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

try:
    import tifffile  # type: ignore
except Exception:  # pragma: no cover
    tifffile = None


TIME_KEY_PRIORITY = (
    "date",
    "datetime",
    "timestamp",
    "time",
    "t",
    "year",
    "period",
)

VALUE_KEY_PRIORITY = (
    "value",
    "price",
    "close",
    "open",
    "high",
    "low",
    "amount",
    "index",
    "obs_value",
)

EMPTY_VALUE_MARKERS = {"", ".", "nan", "null", "none", "na", "n/a"}
MIN_POINTS = 3


@dataclass
class Candidate:
    id: str
    path: str
    source_kind: str
    time_key: str
    value_key: str
    points: list[tuple[datetime, float]]
    score: float
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect JSON time-series data and export shader-friendly single-channel "
            "float16 textures (1D signal and/or 2D chart-space field)."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Path to a single JSON file.")
    source.add_argument(
        "--input-dir",
        type=Path,
        help="Directory of JSON files (recursive) to merge into one series.",
    )
    parser.add_argument(
        "--mode",
        choices=("1d", "2d", "both"),
        default="both",
        help="Which outputs to write.",
    )
    parser.add_argument(
        "--series",
        default="auto",
        help="Candidate selection (index, candidate id, or substring match).",
    )
    parser.add_argument(
        "--list-candidates",
        action="store_true",
        help="List ranked candidates and exit.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data") / "shader_fields",
        help="Directory to write outputs.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Output basename. Defaults to input filename/folder name.",
    )
    parser.add_argument(
        "--normalize",
        choices=("minmax", "zscore", "none"),
        default="minmax",
        help="Normalization mode for 1D output.",
    )
    parser.add_argument(
        "--resample",
        default="none",
        help="Resample 1D output to N samples (integer) or 'none'.",
    )
    parser.add_argument(
        "--field-type",
        choices=("distance", "density", "blurred-proxy"),
        default="distance",
        help="2D field encoding mode.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=512,
        help="2D field height in pixels.",
    )
    parser.add_argument("--value-min", type=float, default=None, help="Manual y-domain minimum.")
    parser.add_argument("--value-max", type=float, default=None, help="Manual y-domain maximum.")
    parser.add_argument(
        "--distance-radius-px",
        type=float,
        default=24.0,
        help="Distance normalization radius for distance field.",
    )
    parser.add_argument(
        "--sigma-px",
        type=float,
        default=6.0,
        help="Gaussian sigma used by density/blurred-proxy field.",
    )
    parser.add_argument(
        "--thickness-px",
        type=int,
        default=2,
        help="Curve thickness used by blurred-proxy mode.",
    )
    parser.add_argument(
        "--flip-y",
        action="store_true",
        default=True,
        help="Flip y-axis so top row maps to higher values (default: true).",
    )
    parser.add_argument(
        "--no-flip-y",
        dest="flip_y",
        action="store_false",
        help="Disable y-axis flip.",
    )
    parser.add_argument(
        "--format",
        choices=("tiff-f16", "npy-f32"),
        default="tiff-f16",
        help="Texture output format.",
    )
    parser.add_argument("--quiet", action="store_true", help="Reduce output logging.")
    return parser.parse_args()


def log(message: str, quiet: bool) -> None:
    if not quiet:
        print(message)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def unwrap_payload(obj: Any) -> Any:
    if isinstance(obj, dict) and "response" in obj and obj.get("response") is not None:
        return obj["response"]
    return obj


def parse_numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        val = float(value)
        if math.isfinite(val):
            return val
        return None
    if isinstance(value, str):
        raw = value.strip()
        if raw.lower() in EMPTY_VALUE_MARKERS:
            return None
        try:
            val = float(raw)
            if math.isfinite(val):
                return val
        except ValueError:
            return None
    return None


def parse_period_time(year_value: Any, period_value: Any) -> datetime | None:
    year_num = parse_numeric(year_value)
    if year_num is None:
        return None
    year = int(year_num)
    period = str(period_value).strip().upper()
    month_match = re.fullmatch(r"M(\d{2})", period)
    if month_match:
        month = int(month_match.group(1))
        if 1 <= month <= 12:
            return datetime(year, month, 1, tzinfo=timezone.utc)
    quarter_match = re.fullmatch(r"Q([1-4])", period)
    if quarter_match:
        q = int(quarter_match.group(1))
        month = 1 + (q - 1) * 3
        return datetime(year, month, 1, tzinfo=timezone.utc)
    return None


def parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        v = float(value)
        if not math.isfinite(v):
            return None
        # Heuristic: >= 1e12 is likely milliseconds.
        ts = v / 1000.0 if abs(v) >= 1e12 else v
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}", text):
        return datetime(int(text), 1, 1, tzinfo=timezone.utc)
    quarter_match = re.fullmatch(r"(\d{4})[- ]?Q([1-4])", text, flags=re.IGNORECASE)
    if quarter_match:
        year = int(quarter_match.group(1))
        q = int(quarter_match.group(2))
        month = 1 + (q - 1) * 3
        return datetime(year, month, 1, tzinfo=timezone.utc)
    month_match = re.fullmatch(r"(\d{4})[-/]M?(\d{2})", text, flags=re.IGNORECASE)
    if month_match:
        year = int(month_match.group(1))
        month = int(month_match.group(2))
        if 1 <= month <= 12:
            return datetime(year, month, 1, tzinfo=timezone.utc)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def key_rank(name: str, keys: tuple[str, ...]) -> int:
    lower = name.lower()
    for idx, key in enumerate(keys):
        if lower == key:
            return idx
    return len(keys) + 5


def normalize_path(path: str) -> str:
    return re.sub(r"\[\d+\]", "[]", path)


def finalize_points(raw_points: list[tuple[datetime, float]]) -> list[tuple[datetime, float]]:
    latest_by_time: dict[datetime, float] = {}
    for ts, val in raw_points:
        latest_by_time[ts] = val
    return sorted(latest_by_time.items(), key=lambda item: item[0])


def detect_candidates_in_array_of_objects(items: list[Any], path: str, idx_base: int) -> list[Candidate]:
    if not items or not all(isinstance(item, dict) for item in items):
        return []

    all_keys: set[str] = set()
    for item in items:
        all_keys.update(str(k) for k in item.keys())

    if not all_keys:
        return []

    time_keys = sorted(all_keys, key=lambda k: key_rank(k, TIME_KEY_PRIORITY))
    value_keys = sorted(all_keys, key=lambda k: key_rank(k, VALUE_KEY_PRIORITY))

    candidates: list[Candidate] = []
    for tkey in time_keys[:6]:
        for vkey in value_keys[:8]:
            if tkey == vkey:
                continue
            points: list[tuple[datetime, float]] = []
            for row in items:
                ts = parse_time(row.get(tkey))
                if ts is None and {"year", "period"}.issubset(row.keys()):
                    ts = parse_period_time(row.get("year"), row.get("period"))
                val = parse_numeric(row.get(vkey))
                if ts is not None and val is not None:
                    points.append((ts, val))

            cleaned = finalize_points(points)
            if len(cleaned) < MIN_POINTS:
                continue

            time_bonus = 2.0 if tkey.lower() in TIME_KEY_PRIORITY else 0.0
            value_bonus = 2.0 if vkey.lower() in VALUE_KEY_PRIORITY else 0.0
            score = float(len(cleaned)) + time_bonus + value_bonus
            cid = f"c{idx_base + len(candidates)}"
            candidates.append(
                Candidate(
                    id=cid,
                    path=path,
                    source_kind="array-objects",
                    time_key=tkey,
                    value_key=vkey,
                    points=cleaned,
                    score=score,
                    notes=f"{len(cleaned)} points",
                )
            )
    return candidates


def detect_candidates_in_pair_array(items: list[Any], path: str, idx_base: int) -> list[Candidate]:
    if not items:
        return []
    if not all(isinstance(item, (list, tuple)) and len(item) >= 2 for item in items):
        return []
    points: list[tuple[datetime, float]] = []
    for item in items:
        ts = parse_time(item[0])
        val = parse_numeric(item[1])
        if ts is not None and val is not None:
            points.append((ts, val))
    cleaned = finalize_points(points)
    if len(cleaned) < MIN_POINTS:
        return []
    return [
        Candidate(
            id=f"c{idx_base}",
            path=path,
            source_kind="array-pairs",
            time_key="[0]",
            value_key="[1]",
            points=cleaned,
            score=float(len(cleaned)) + 1.5,
            notes=f"{len(cleaned)} points",
        )
    ]


def detect_candidates_in_time_map(obj: dict[str, Any], path: str, idx_base: int) -> list[Candidate]:
    if not obj:
        return []
    points: list[tuple[datetime, float]] = []
    for key, value in obj.items():
        ts = parse_time(key)
        if ts is None:
            continue
        val = parse_numeric(value)
        if val is None and isinstance(value, (list, tuple)) and value:
            val = parse_numeric(value[0])
        if ts is not None and val is not None:
            points.append((ts, val))
    cleaned = finalize_points(points)
    if len(cleaned) < MIN_POINTS:
        return []
    return [
        Candidate(
            id=f"c{idx_base}",
            path=path,
            source_kind="time-map",
            time_key="<dict-key>",
            value_key="<dict-value>",
            points=cleaned,
            score=float(len(cleaned)),
            notes=f"{len(cleaned)} points",
        )
    ]


def collect_candidates(root: Any) -> list[Candidate]:
    candidates: list[Candidate] = []

    def walk(node: Any, path: str) -> None:
        idx_base = len(candidates)
        if isinstance(node, dict):
            candidates.extend(detect_candidates_in_time_map(node, path, idx_base))
            for key, value in node.items():
                walk(value, f"{path}.{key}")
            return
        if isinstance(node, list):
            candidates.extend(detect_candidates_in_array_of_objects(node, path, len(candidates)))
            candidates.extend(detect_candidates_in_pair_array(node, path, len(candidates)))
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")

    walk(root, "$")
    # De-dupe by (path,time_key,value_key,count)
    deduped: dict[tuple[str, str, str, int], Candidate] = {}
    for candidate in candidates:
        key = (candidate.path, candidate.time_key, candidate.value_key, len(candidate.points))
        prev = deduped.get(key)
        if prev is None or candidate.score > prev.score:
            deduped[key] = candidate
    ranked = sorted(deduped.values(), key=lambda c: (-c.score, c.path, c.time_key, c.value_key))
    for idx, candidate in enumerate(ranked):
        candidate.id = f"c{idx}"
    return ranked


def merge_candidates_from_directory(files: list[Path], quiet: bool) -> list[Candidate]:
    grouped: dict[tuple[str, str, str, str], list[tuple[datetime, float]]] = {}
    grouped_meta: dict[tuple[str, str, str, str], tuple[str, str]] = {}
    for file_path in files:
        try:
            raw = load_json(file_path)
        except Exception as exc:
            log(f"Skipping {file_path}: {exc}", quiet)
            continue
        payload = unwrap_payload(raw)
        per_file = collect_candidates(payload)
        if not per_file:
            continue
        top = per_file[0]
        signature = (normalize_path(top.path), top.source_kind, top.time_key, top.value_key)
        grouped.setdefault(signature, []).extend(top.points)
        grouped_meta[signature] = (top.path, f"{top.source_kind}:{top.time_key}->{top.value_key}")

    merged: list[Candidate] = []
    for idx, (signature, points) in enumerate(grouped.items()):
        cleaned = finalize_points(points)
        if len(cleaned) < MIN_POINTS:
            continue
        path, notes = grouped_meta[signature]
        merged.append(
            Candidate(
                id=f"c{idx}",
                path=path,
                source_kind=signature[1],
                time_key=signature[2],
                value_key=signature[3],
                points=cleaned,
                score=float(len(cleaned)),
                notes=f"{len(cleaned)} merged points ({notes})",
            )
        )
    merged.sort(key=lambda c: (-c.score, c.path, c.time_key, c.value_key))
    for idx, candidate in enumerate(merged):
        candidate.id = f"c{idx}"
    return merged


def choose_candidate(candidates: list[Candidate], selector: str) -> Candidate:
    if not candidates:
        raise ValueError("No candidate time series found in input JSON.")
    if selector == "auto":
        return candidates[0]
    if selector.isdigit():
        idx = int(selector)
        if 0 <= idx < len(candidates):
            return candidates[idx]
        raise ValueError(f"Series index out of range: {idx}")
    for candidate in candidates:
        if candidate.id == selector:
            return candidate
    lowered = selector.lower()
    for candidate in candidates:
        hay = f"{candidate.path} {candidate.time_key} {candidate.value_key}".lower()
        if lowered in hay:
            return candidate
    raise ValueError(f"Could not resolve --series selector: {selector}")


def normalize_1d(values: np.ndarray, mode: str) -> np.ndarray:
    if mode == "none":
        return values.astype(np.float32)
    if mode == "zscore":
        std = float(np.std(values))
        if std <= 1e-12:
            return np.zeros_like(values, dtype=np.float32)
        return ((values - float(np.mean(values))) / std).astype(np.float32)
    # minmax
    vmin = float(np.min(values))
    vmax = float(np.max(values))
    if abs(vmax - vmin) <= 1e-12:
        return np.zeros_like(values, dtype=np.float32)
    return ((values - vmin) / (vmax - vmin)).astype(np.float32)


def maybe_resample(values: np.ndarray, count: str) -> np.ndarray:
    if count == "none":
        return values
    n = int(count)
    if n <= 1:
        raise ValueError("--resample must be > 1 or 'none'.")
    if len(values) == n:
        return values
    x_old = np.linspace(0.0, 1.0, len(values), dtype=np.float32)
    x_new = np.linspace(0.0, 1.0, n, dtype=np.float32)
    return np.interp(x_new, x_old, values).astype(np.float32)


def compute_value_domain(values: np.ndarray, vmin: float | None, vmax: float | None) -> tuple[float, float]:
    if vmin is not None and vmax is not None:
        low, high = (vmin, vmax) if vmin <= vmax else (vmax, vmin)
    elif vmin is not None:
        low = vmin
        high = float(np.max(values))
    elif vmax is not None:
        low = float(np.min(values))
        high = vmax
    else:
        p01 = float(np.percentile(values, 1))
        p99 = float(np.percentile(values, 99))
        if abs(p99 - p01) <= 1e-12:
            p01 = float(np.min(values))
            p99 = float(np.max(values))
        span = max(1e-6, p99 - p01)
        low = p01 - 0.05 * span
        high = p99 + 0.05 * span
    if abs(high - low) <= 1e-12:
        high = low + 1.0
    return float(low), float(high)


def values_to_rows(values: np.ndarray, height: int, vmin: float, vmax: float, flip_y: bool) -> np.ndarray:
    norm = np.clip((values - vmin) / (vmax - vmin), 0.0, 1.0)
    rows = norm * float(height - 1)
    if flip_y:
        rows = float(height - 1) - rows
    return rows.astype(np.float32)


def box_blur_2d(image: np.ndarray, iterations: int = 3) -> np.ndarray:
    kernel = np.array([1.0, 1.0, 1.0], dtype=np.float32) / 3.0
    out = image.astype(np.float32)
    for _ in range(iterations):
        out = np.apply_along_axis(lambda m: np.convolve(m, kernel, mode="same"), axis=1, arr=out)
        out = np.apply_along_axis(lambda m: np.convolve(m, kernel, mode="same"), axis=0, arr=out)
    return out


def build_field(
    values: np.ndarray,
    height: int,
    field_type: str,
    vmin: float,
    vmax: float,
    distance_radius_px: float,
    sigma_px: float,
    thickness_px: int,
    flip_y: bool,
) -> np.ndarray:
    width = int(values.shape[0])
    rows = values_to_rows(values, height, vmin, vmax, flip_y)
    yy = np.arange(height, dtype=np.float32)[:, None]
    curve = rows[None, :]
    dist = np.abs(yy - curve).astype(np.float32)

    if field_type == "distance":
        radius = max(1e-6, float(distance_radius_px))
        field = np.clip(dist / radius, 0.0, 1.0)
        return field.astype(np.float32)

    if field_type == "density":
        sigma = max(1e-6, float(sigma_px))
        field = np.exp(-0.5 * (dist / sigma) ** 2)
        return field.astype(np.float32)

    # blurred-proxy: thick curve mask then blur.
    mask = np.zeros((height, width), dtype=np.float32)
    for x in range(width):
        r = int(round(float(rows[x])))
        r0 = max(0, r - thickness_px)
        r1 = min(height, r + thickness_px + 1)
        mask[r0:r1, x] = 1.0
    blurred = box_blur_2d(mask, iterations=5)
    if blurred.max() > 0:
        blurred = blurred / blurred.max()
    return blurred.astype(np.float32)


def save_texture(array: np.ndarray, path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "tiff-f16":
        if tifffile is None:
            raise RuntimeError(
                "TIFF export requires 'tifffile'. Install with: pip install tifffile"
            )
        tifffile.imwrite(path, array.astype(np.float16), photometric="minisblack")
        return
    np.save(path, array.astype(np.float32))


def find_json_files(input_dir: Path) -> list[Path]:
    files = [p for p in sorted(input_dir.rglob("*.json")) if not p.name.startswith("_")]
    return files


def print_candidates(candidates: list[Candidate]) -> None:
    print("Candidates:")
    for idx, candidate in enumerate(candidates):
        print(
            f"  [{idx}] id={candidate.id} score={candidate.score:.1f} "
            f"points={len(candidate.points)} kind={candidate.source_kind} "
            f"path={candidate.path} time={candidate.time_key} value={candidate.value_key}"
        )


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    args = parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.input is not None:
        raw = load_json(args.input)
        payload = unwrap_payload(raw)
        candidates = collect_candidates(payload)
        source_info = {"mode": "file", "input": str(args.input)}
        default_name = args.input.stem
    else:
        json_files = find_json_files(args.input_dir)
        if not json_files:
            raise ValueError(f"No JSON files found under {args.input_dir}")
        candidates = merge_candidates_from_directory(json_files, args.quiet)
        source_info = {
            "mode": "dir",
            "input_dir": str(args.input_dir),
            "json_file_count": len(json_files),
        }
        default_name = args.input_dir.name

    if not candidates:
        raise ValueError("No candidate time series found.")

    print_candidates(candidates)
    if args.list_candidates:
        return

    chosen = choose_candidate(candidates, args.series)
    log(f"Selected candidate: {chosen.id} ({chosen.path} :: {chosen.time_key}->{chosen.value_key})", args.quiet)

    times = [t for t, _ in chosen.points]
    values_raw = np.array([v for _, v in chosen.points], dtype=np.float32)
    values_1d = maybe_resample(values_raw, args.resample)
    values_1d = normalize_1d(values_1d, args.normalize)

    basename = args.name or default_name
    outputs: dict[str, str] = {}

    if args.mode in ("1d", "both"):
        tex_1d = values_1d[None, :]
        ext = ".tiff" if args.format == "tiff-f16" else ".npy"
        out_path = out_dir / f"{basename}_1d_{'f16' if args.format == 'tiff-f16' else 'f32'}{ext}"
        save_texture(tex_1d, out_path, args.format)
        outputs["texture_1d"] = str(out_path)
        log(f"Wrote {out_path}", args.quiet)

    field_vmin, field_vmax = compute_value_domain(values_raw, args.value_min, args.value_max)
    if args.mode in ("2d", "both"):
        field = build_field(
            values=values_raw,
            height=args.height,
            field_type=args.field_type,
            vmin=field_vmin,
            vmax=field_vmax,
            distance_radius_px=args.distance_radius_px,
            sigma_px=args.sigma_px,
            thickness_px=max(1, int(args.thickness_px)),
            flip_y=args.flip_y,
        )
        ext = ".tiff" if args.format == "tiff-f16" else ".npy"
        out_path = out_dir / f"{basename}_2d_field_{'f16' if args.format == 'tiff-f16' else 'f32'}{ext}"
        save_texture(field, out_path, args.format)
        outputs["texture_2d"] = str(out_path)
        log(f"Wrote {out_path}", args.quiet)

    meta = {
        "created_at": iso_z(datetime.now(tz=timezone.utc)),
        "source": source_info,
        "selected_candidate": {
            "id": chosen.id,
            "path": chosen.path,
            "source_kind": chosen.source_kind,
            "time_key": chosen.time_key,
            "value_key": chosen.value_key,
            "points": len(chosen.points),
            "score": chosen.score,
        },
        "series": {
            "sample_count": int(values_raw.shape[0]),
            "time_start": iso_z(min(times)),
            "time_end": iso_z(max(times)),
            "value_min_raw": float(np.min(values_raw)),
            "value_max_raw": float(np.max(values_raw)),
        },
        "settings": {
            "mode": args.mode,
            "format": args.format,
            "normalize": args.normalize,
            "resample": args.resample,
            "field_type": args.field_type,
            "height": args.height,
            "value_domain": {"min": field_vmin, "max": field_vmax},
            "distance_radius_px": args.distance_radius_px,
            "sigma_px": args.sigma_px,
            "thickness_px": args.thickness_px,
            "flip_y": args.flip_y,
        },
        "outputs": outputs,
        "candidate_count": len(candidates),
        "candidate_preview": [
            {
                "id": c.id,
                "score": c.score,
                "points": len(c.points),
                "path": c.path,
                "time_key": c.time_key,
                "value_key": c.value_key,
            }
            for c in candidates[:10]
        ],
    }
    meta_path = out_dir / f"{basename}_meta.json"
    with meta_path.open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=True)
    log(f"Wrote {meta_path}", args.quiet)


if __name__ == "__main__":
    main()
