#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from build_raster_fields import build_artifacts
from build_raster_fields import default_config
from build_raster_fields import load_records
from build_raster_fields import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic validation for raster field preprocessing pipeline.")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).resolve().parent / "fixtures" / "overlap_points.json",
        help="Fixture records JSON.",
    )
    parser.add_argument("--width", type=int, default=320, help="Validation width.")
    parser.add_argument("--height", type=int, default=180, help="Validation height.")
    parser.add_argument("--quiet", action="store_true", help="Reduce output.")
    return parser.parse_args()


def assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def build_validation_config() -> dict:
    cfg = default_config()
    cfg["coord_domain"]["auto"] = False
    cfg["coord_domain"]["x_min"] = 0.0
    cfg["coord_domain"]["x_max"] = 1.0
    cfg["coord_domain"]["y_min"] = 0.0
    cfg["coord_domain"]["y_max"] = 1.0
    cfg["raster"]["default_radius_px"] = 26.0
    cfg["raster"]["radius_scale"] = 1.0
    cfg["raster"]["influence_falloff_sigma_px"] = 18.0
    cfg["influence"]["post_blur_sigma_px"] = 2.0
    cfg["color_coord"]["enabled"] = True
    cfg["output"]["format"] = "npy-f32"
    cfg["output"]["include_hash_manifest"] = True
    return cfg


def verify_overlap_sdf_union(records: list[dict], width: int, height: int, cfg: dict) -> None:
    # Use two circles only for this specific overlap check.
    circles = [r for r in records if str(r.get("shape", "circle")).lower() == "circle"][:2]
    assert_true(len(circles) == 2, "Fixture must include at least two circle records for overlap test.")
    arts = build_artifacts(records=circles, width=width, height=height, config=cfg, prefix="overlap_check")
    sdf = arts.sdf_field
    # Midpoint between circle centers should be inside (negative SDF before normalization clip still negative).
    mx = int(round((0.28 + 0.40) * 0.5 * (width - 1)))
    my = int(round((1.0 - 0.55) * (height - 1)))
    assert_true(sdf[my, mx] < 0.0, "Overlapping circles should create merged union interior at midpoint.")


def verify_influence_overlap_gain(records: list[dict], width: int, height: int, cfg: dict) -> None:
    circles = [r for r in records if str(r.get("shape", "circle")).lower() == "circle"][:2]
    arts = build_artifacts(records=circles, width=width, height=height, config=cfg, prefix="influence_check")
    inf = arts.influence_field
    overlap_x = int(round((0.28 + 0.40) * 0.5 * (width - 1)))
    overlap_y = int(round((1.0 - 0.55) * (height - 1)))
    shoulder_x = int(round(0.28 * (width - 1)))
    shoulder_y = overlap_y
    assert_true(
        inf[overlap_y, overlap_x] > inf[shoulder_y, shoulder_x],
        "Influence should increase in overlap region versus single-stamp shoulder.",
    )


def verify_shape_extension_path(records: list[dict], width: int, height: int, cfg: dict) -> None:
    # Includes square + unknown shape fallback.
    arts = build_artifacts(records=records, width=width, height=height, config=cfg, prefix="shape_check")
    stats = arts.metadata.get("raster_stats", {})
    assert_true(int(stats.get("unknown_shape_fallbacks", 0)) >= 1, "Unknown shape fallback should be tracked.")
    assert_true(int(stats.get("valid_records", 0)) >= 3, "Most fixture records should remain valid.")


def main() -> None:
    args = parse_args()
    cfg = build_validation_config()
    records = load_records(args.fixture)
    width = int(args.width)
    height = int(args.height)
    assert_true(width > 0 and height > 0, "Width/height must be positive.")

    with TemporaryDirectory(prefix="shader_fields_validate_") as td:
        out_dir = Path(td)
        first = run_pipeline(
            input_path=args.fixture,
            input_dir=None,
            out_dir=out_dir,
            width=width,
            height=height,
            config=cfg,
            prefix_override="validate",
            quiet=True,
        )
        second = run_pipeline(
            input_path=args.fixture,
            input_dir=None,
            out_dir=out_dir,
            width=width,
            height=height,
            config=cfg,
            prefix_override="validate",
            quiet=True,
        )

        # Deterministic signatures + hashes.
        assert_true(first["build_signature"] == second["build_signature"], "Build signature must be deterministic.")
        assert_true(first["hashes"] == second["hashes"], "Output hashes must be deterministic.")

        # Dimension checks.
        sdf = np.load(first["paths"]["sdf_field"])
        influence = np.load(first["paths"]["influence_field"])
        assert_true(sdf.shape == (height, width), "SDF field dimensions must match WIDTHxHEIGHT.")
        assert_true(influence.shape == (height, width), "Influence field dimensions must match WIDTHxHEIGHT.")

        # Metadata sanity.
        meta = json.loads(Path(first["paths"]["meta"]).read_text(encoding="utf-8"))
        assert_true(meta["width"] == width and meta["height"] == height, "Metadata dimensions must match.")

    verify_overlap_sdf_union(records=records, width=width, height=height, cfg=cfg)
    verify_influence_overlap_gain(records=records, width=width, height=height, cfg=cfg)
    verify_shape_extension_path(records=records, width=width, height=height, cfg=cfg)

    if not args.quiet:
        print("Validation passed:")
        print("- dimensions exact")
        print("- deterministic hashes")
        print("- overlap SDF union behavior")
        print("- overlap influence gain")
        print("- shape extension/fallback path")


if __name__ == "__main__":
    main()
