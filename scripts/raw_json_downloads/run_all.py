import sys
from datetime import datetime, timezone
from pathlib import Path

# Make project root importable when running this file directly.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.catalog import DATA_CATALOG

from _common import download_dataset
from _common import download_house_price_index_per_state
from _common import _slugify
from _common import _write_json

HOUSE_PRICE_INDEX_GROUP = "House Price Index Per State"


def main() -> None:
    total = 0
    run_started_at = datetime.now(timezone.utc).isoformat()
    run_report: dict[str, object] = {
        "run_started_at": run_started_at,
        "totals": {"datasets": 0, "ok_years": 0, "error_years": 0},
        "datasets": [],
    }

    for group_name, group_config in DATA_CATALOG.items():
        if group_name == HOUSE_PRICE_INDEX_GROUP:
            continue

        source_type = group_config.get("type")
        datasets = group_config.get("datasets", {})

        for dataset_name, dataset_id in datasets.items():
            total += 1
            print(f"[{total}] {group_name} :: {dataset_name}")
            summary = download_dataset(group_name, dataset_name, source_type, dataset_id)
            run_report["totals"]["datasets"] += 1
            run_report["totals"]["ok_years"] += summary["totals"]["ok"]
            run_report["totals"]["error_years"] += summary["totals"]["error"]
            run_report["datasets"].append(
                {
                    "group": group_name,
                    "dataset_name": dataset_name,
                    "source_type": source_type,
                    "summary_path": str(
                        Path("data")
                        / "raw_json"
                        / _slugify(f"{group_name}_{dataset_name}")
                        / "_summary.json"
                    ),
                    "totals": summary["totals"],
                    "errors": summary["errors"],
                }
            )

    total += 1
    print(f"[{total}] {HOUSE_PRICE_INDEX_GROUP} :: All States")
    hpi_summary = download_house_price_index_per_state()
    run_report["totals"]["datasets"] += 1
    run_report["totals"]["ok_years"] += hpi_summary["totals"]["ok"]
    run_report["totals"]["error_years"] += hpi_summary["totals"]["error"]
    run_report["datasets"].append(
        {
            "group": HOUSE_PRICE_INDEX_GROUP,
            "dataset_name": "All States",
            "source_type": "fred",
            "summary_path": str(Path("data") / "raw_json" / "house_price_index_per_state" / "_summary.json"),
            "totals": hpi_summary["totals"],
            "errors": hpi_summary["errors"],
        }
    )

    run_finished_at = datetime.now(timezone.utc).isoformat()
    run_report["run_finished_at"] = run_finished_at
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path("data") / "raw_json" / "_runs"
    run_path = run_dir / f"run_all_{run_id}.json"
    _write_json(run_path, run_report)

    print(f"Completed {total} dataset downloads.")
    print(f"Run report: {run_path}")


if __name__ == "__main__":
    main()
