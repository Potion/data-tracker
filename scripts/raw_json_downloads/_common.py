import json
import os
import re
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from tenacity import Retrying
from tenacity import retry_if_exception_type
from tenacity import stop_after_attempt
from tenacity import wait_exponential_jitter

START_YEAR = 1995
END_YEAR = 2026
MAX_ATTEMPTS = 6

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
# Conservative pacing to avoid burst limits when running all datasets.
RATE_LIMIT_SECONDS = {
    "fred": 0.6,
    "bls": 0.8,
    "coingecko": 1.6,
    "oecd": 1.2,
    "ecb": 0.8,
    "census": 0.8,
    "imf": 1.0,
}
_LAST_REQUEST_TS: dict[str, float] = {}

HOUSE_PRICE_INDEX_STATE_SERIES: dict[str, str] = {
    "Alabama": "ALSTHPI",
    "Alaska": "AKSTHPI",
    "Arizona": "AZSTHPI",
    "Arkansas": "ARSTHPI",
    "California": "CASTHPI",
    "Colorado": "COSTHPI",
    "Connecticut": "CTSTHPI",
    "Delaware": "DESTHPI",
    "District of Columbia": "DCSTHPI",
    "Florida": "FLSTHPI",
    "Georgia": "GASTHPI",
    "Hawaii": "HISTHPI",
    "Idaho": "IDSTHPI",
    "Illinois": "ILSTHPI",
    "Indiana": "INSTHPI",
    "Iowa": "IASTHPI",
    "Kansas": "KSSTHPI",
    "Kentucky": "KYSTHPI",
    "Louisiana": "LASTHPI",
    "Maine": "MESTHPI",
    "Maryland": "MDSTHPI",
    "Massachusetts": "MASTHPI",
    "Michigan": "MISTHPI",
    "Minnesota": "MNSTHPI",
    "Mississippi": "MSSTHPI",
    "Missouri": "MOSTHPI",
    "Montana": "MTSTHPI",
    "Nebraska": "NESTHPI",
    "Nevada": "NVSTHPI",
    "New Hampshire": "NHSTHPI",
    "New Jersey": "NJSTHPI",
    "New Mexico": "NMSTHPI",
    "New York": "NYSTHPI",
    "North Carolina": "NCSTHPI",
    "North Dakota": "NDSTHPI",
    "Ohio": "OHSTHPI",
    "Oklahoma": "OKSTHPI",
    "Oregon": "ORSTHPI",
    "Pennsylvania": "PASTHPI",
    "Rhode Island": "RISTHPI",
    "South Carolina": "SCSTHPI",
    "South Dakota": "SDSTHPI",
    "Tennessee": "TNSTHPI",
    "Texas": "TXSTHPI",
    "Utah": "UTSTHPI",
    "Vermont": "VTSTHPI",
    "Virginia": "VASTHPI",
    "Washington": "WASTHPI",
    "West Virginia": "WVSTHPI",
    "Wisconsin": "WISTHPI",
    "Wyoming": "WYSTHPI",
}


class RetryableRequestError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@lru_cache(maxsize=1)
def _load_streamlit_secrets() -> dict[str, Any]:
    secrets_path = Path(__file__).resolve().parents[2] / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return {}

    try:
        import tomllib

        with secrets_path.open("rb") as fh:
            data = tomllib.load(fh)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_secret(key: str, default: str = "") -> str:
    env_value = os.getenv(key)
    if env_value:
        return env_value

    secrets = _load_streamlit_secrets()
    value = secrets.get(key, default)
    return value if isinstance(value, str) else default


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _ensure_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {
            "non_json_response": response.text,
            "content_type": response.headers.get("Content-Type", ""),
        }


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=True)


def _throttle(source_type: str) -> None:
    min_delay = RATE_LIMIT_SECONDS.get(source_type, 0.6)
    now = time.monotonic()
    last = _LAST_REQUEST_TS.get(source_type)
    if last is not None:
        elapsed = now - last
        if elapsed < min_delay:
            time.sleep(min_delay - elapsed)
    _LAST_REQUEST_TS[source_type] = time.monotonic()


def _request_with_retries(
    session: requests.Session,
    source_type: str,
    method: str,
    url: str,
    **kwargs: Any,
) -> requests.Response:
    for attempt in Retrying(
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((requests.RequestException, RetryableRequestError)),
        reraise=True,
    ):
        with attempt:
            _throttle(source_type)
            response = session.request(method=method, url=url, **kwargs)
            if response.status_code in RETRYABLE_STATUS_CODES:
                raise RetryableRequestError(
                    f"retryable status code {response.status_code}",
                    status_code=response.status_code,
                )
            return response

    raise RuntimeError("Unexpected retry loop termination")


def _set_period_params(url: str, year: int) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)

    start_template = query.get("startPeriod", ["YYYY"])[0]

    if "-Q" in start_template:
        query["startPeriod"] = [f"{year}-Q1"]
        query["endPeriod"] = [f"{year}-Q4"]
    elif "-M" in start_template:
        query["startPeriod"] = [f"{year}-M01"]
        query["endPeriod"] = [f"{year}-M12"]
    else:
        query["startPeriod"] = [str(year)]
        query["endPeriod"] = [str(year)]

    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _ecb_resource_path(dataset_id: str) -> str:
    if "." in dataset_id and "/" not in dataset_id:
        flow_ref, key = dataset_id.split(".", 1)
        return f"{flow_ref}/{key}"
    return dataset_id


def _census_url_for_year(dataset_id: str, year: int) -> str:
    url = re.sub(r"/data/\d{4}/", f"/data/{year}/", dataset_id)
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if "time" in query:
        query["time"] = [str(year)]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _fred_request(session: requests.Session, dataset_id: str, year: int) -> tuple[Any, dict[str, Any], int | None]:
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": dataset_id,
        "api_key": _get_secret("FRED_API_KEY"),
        "file_type": "json",
        "observation_start": f"{year}-01-01",
        "observation_end": f"{year}-12-31",
    }
    response = _request_with_retries(session, "fred", "GET", url, params=params, timeout=30)
    return _ensure_json(response), {"url": response.url, "status_code": response.status_code}, response.status_code


def _bls_request(session: requests.Session, dataset_id: str, year: int) -> tuple[Any, dict[str, Any], int | None]:
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    payload = {
        "seriesid": [dataset_id],
        "startyear": str(year),
        "endyear": str(year),
    }
    bls_api_key = _get_secret("BLS_API_KEY")
    if bls_api_key:
        payload["registrationkey"] = bls_api_key

    response = _request_with_retries(
        session,
        "bls",
        "POST",
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    return _ensure_json(response), {"url": url, "status_code": response.status_code, "payload": payload}, response.status_code


def _coingecko_request(
    session: requests.Session, dataset_id: str, year: int
) -> tuple[Any, dict[str, Any], int | None]:
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    url = f"https://api.coingecko.com/api/v3/coins/{dataset_id}/market_chart/range"
    params = {
        "vs_currency": "usd",
        "from": int(start.timestamp()),
        "to": int(end.timestamp()),
    }
    response = _request_with_retries(
        session,
        "coingecko",
        "GET",
        url,
        params=params,
        headers={"User-Agent": "FCAT_Validator"},
        timeout=30,
    )
    return _ensure_json(response), {"url": response.url, "status_code": response.status_code}, response.status_code


def _oecd_request(session: requests.Session, dataset_id: str, year: int) -> tuple[Any, dict[str, Any], int | None]:
    url = _set_period_params(dataset_id, year)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/csv;q=0.9, */*;q=0.8",
        "Referer": "https://data-explorer.oecd.org/",
    }
    response = _request_with_retries(
        session,
        "oecd",
        "GET",
        url,
        headers=headers,
        timeout=45,
        verify=False,
    )
    return _ensure_json(response), {"url": response.url, "status_code": response.status_code}, response.status_code


def _ecb_request(session: requests.Session, dataset_id: str, year: int) -> tuple[Any, dict[str, Any], int | None]:
    path = _ecb_resource_path(dataset_id)
    url = f"https://data-api.ecb.europa.eu/service/data/{path}"
    params = {
        "startPeriod": f"{year}-01-01",
        "endPeriod": f"{year}-12-31",
    }
    headers = {"Accept": "application/json", "User-Agent": "FCAT_Validator"}
    response = _request_with_retries(
        session,
        "ecb",
        "GET",
        url,
        params=params,
        headers=headers,
        timeout=30,
    )
    return _ensure_json(response), {"url": response.url, "status_code": response.status_code}, response.status_code


def _census_request(session: requests.Session, dataset_id: str, year: int) -> tuple[Any, dict[str, Any], int | None]:
    url = _census_url_for_year(dataset_id, year)
    response = _request_with_retries(session, "census", "GET", url, timeout=30)
    return _ensure_json(response), {"url": response.url, "status_code": response.status_code}, response.status_code


def _imf_request(_: requests.Session, dataset_id: str, year: int) -> tuple[Any, dict[str, Any], int | None]:
    if not dataset_id.strip():
        return {
            "error": "Dataset URL is empty. Update DATASET_ID with a valid IMF API URL.",
            "year": year,
        }, {"url": dataset_id, "status_code": None}, None
    return {
        "error": "IMF raw downloader expects a concrete IMF URL in the dataset slot.",
        "year": year,
    }, {"url": dataset_id, "status_code": None}, None


def _is_no_data_response(source_type: str, payload: Any) -> bool:
    if source_type == "fred" and isinstance(payload, dict):
        obs = payload.get("observations")
        return isinstance(obs, list) and len(obs) == 0

    if source_type == "bls" and isinstance(payload, dict):
        series = payload.get("Results", {}).get("series", [])
        if not series:
            return True
        data = series[0].get("data", [])
        return isinstance(data, list) and len(data) == 0

    if source_type == "coingecko" and isinstance(payload, dict):
        prices = payload.get("prices")
        return isinstance(prices, list) and len(prices) == 0

    if source_type == "census" and isinstance(payload, list):
        return len(payload) <= 1

    return False


def _classify_result(
    source_type: str,
    status_code: int | None,
    payload: Any,
    exception: Exception | None,
) -> dict[str, str]:
    if exception is not None:
        if isinstance(exception, RetryableRequestError):
            if exception.status_code == 429:
                return {
                    "status": "error",
                    "error_type": "rate_limited",
                    "recommended_action": "retry_later",
                    "message": "Rate limit persisted after retries.",
                }
            if exception.status_code in {500, 502, 503, 504}:
                return {
                    "status": "error",
                    "error_type": "upstream_server_error",
                    "recommended_action": "retry_later",
                    "message": "Upstream server errors persisted after retries.",
                }
        return {
            "status": "error",
            "error_type": "transient_retries_exhausted",
            "recommended_action": "retry_later",
            "message": str(exception),
        }

    if status_code is None:
        return {
            "status": "error",
            "error_type": "malformed_or_missing_config",
            "recommended_action": "fix_request",
            "message": "Missing required dataset URL or configuration.",
        }

    if 200 <= status_code < 300:
        if _is_no_data_response(source_type, payload):
            return {
                "status": "error",
                "error_type": "no_data_in_range",
                "recommended_action": "accept_or_change_time_range",
                "message": "Request succeeded but the API returned no data for this year.",
            }
        return {
            "status": "ok",
            "error_type": "",
            "recommended_action": "none",
            "message": "Success",
        }

    if status_code == 400:
        return {
            "status": "error",
            "error_type": "malformed_request",
            "recommended_action": "fix_request",
            "message": "API rejected request format or parameters.",
        }

    if status_code in {401, 403}:
        return {
            "status": "error",
            "error_type": "auth_or_access",
            "recommended_action": "check_api_key_or_permissions",
            "message": "Authentication/authorization failed.",
        }

    if status_code == 404:
        return {
            "status": "error",
            "error_type": "dataset_not_found",
            "recommended_action": "fix_request",
            "message": "Dataset endpoint or series was not found.",
        }

    if status_code == 429:
        return {
            "status": "error",
            "error_type": "rate_limited",
            "recommended_action": "retry_later",
            "message": "Rate limit hit after retries.",
        }

    if 500 <= status_code < 600:
        return {
            "status": "error",
            "error_type": "upstream_server_error",
            "recommended_action": "retry_later",
            "message": "Upstream server error after retries.",
        }

    return {
        "status": "error",
        "error_type": "unexpected_status",
        "recommended_action": "inspect_response",
        "message": f"Unexpected status code {status_code}",
    }


def download_dataset(group: str, dataset_name: str, source_type: str, dataset_id: str) -> dict[str, Any]:
    slug = _slugify(f"{group}_{dataset_name}")
    base_dir = Path("data") / "raw_json" / slug
    metadata = {
        "group": group,
        "dataset_name": dataset_name,
        "source_type": source_type,
        "dataset_id": dataset_id,
        "start_year": START_YEAR,
        "end_year": END_YEAR,
    }

    handlers = {
        "fred": _fred_request,
        "bls": _bls_request,
        "coingecko": _coingecko_request,
        "oecd": _oecd_request,
        "ecb": _ecb_request,
        "census": _census_request,
        "imf": _imf_request,
    }

    handler = handlers.get(source_type)
    if handler is None:
        raise ValueError(f"Unsupported source_type: {source_type}")

    print(f"Downloading {dataset_name} ({source_type}) from {START_YEAR} to {END_YEAR}")

    summary: dict[str, Any] = {
        "metadata": metadata,
        "totals": {"ok": 0, "error": 0},
        "errors": [],
        "years": [],
    }

    session = requests.Session()

    for year in range(START_YEAR, END_YEAR + 1):
        payload: Any = None
        request_meta: dict[str, Any] = {}
        status_code: int | None = None
        captured_error: Exception | None = None

        try:
            payload, request_meta, status_code = handler(session, dataset_id, year)
        except Exception as exc:
            captured_error = exc

        result = _classify_result(source_type, status_code, payload, captured_error)

        year_path = base_dir / f"{year}.json"
        _write_json(
            year_path,
            {
                "metadata": metadata,
                "year": year,
                "request": request_meta,
                "status": result["status"],
                "error_type": result["error_type"],
                "recommended_action": result["recommended_action"],
                "message": result["message"],
                "response": payload,
            },
        )

        if result["status"] == "ok":
            summary["totals"]["ok"] += 1
            print(f"  saved {year_path}")
        else:
            summary["totals"]["error"] += 1
            entry = {
                "year": year,
                "error_type": result["error_type"],
                "recommended_action": result["recommended_action"],
                "message": result["message"],
                "request": request_meta,
            }
            summary["errors"].append(entry)
            print(f"  failed {year}: {result['error_type']} ({result['recommended_action']})")

        summary["years"].append(
            {
                "year": year,
                "status": result["status"],
                "error_type": result["error_type"],
                "recommended_action": result["recommended_action"],
            }
        )

    summary_path = base_dir / "_summary.json"
    _write_json(summary_path, summary)
    print(f"Summary: {summary_path}")

    return summary


def download_house_price_index_per_state(
    group: str = "House Price Index Per State",
    dataset_name: str = "All States",
) -> dict[str, Any]:
    base_dir = Path("data") / "raw_json" / "house_price_index_per_state"
    metadata = {
        "group": group,
        "dataset_name": dataset_name,
        "source_type": "fred",
        "dataset_id": "per_state",
        "start_year": START_YEAR,
        "end_year": END_YEAR,
        "state_count": len(HOUSE_PRICE_INDEX_STATE_SERIES),
    }

    aggregate_summary: dict[str, Any] = {
        "metadata": metadata,
        "totals": {"ok": 0, "error": 0},
        "errors": [],
        "states": [],
    }

    print(f"Downloading {dataset_name} (fred) from {START_YEAR} to {END_YEAR}")
    session = requests.Session()

    for state_name, series_id in HOUSE_PRICE_INDEX_STATE_SERIES.items():
        state_slug = _slugify(state_name)
        state_dir = base_dir / state_slug
        state_meta = {
            **metadata,
            "state_name": state_name,
            "state_slug": state_slug,
            "series_id": series_id,
        }
        state_summary: dict[str, Any] = {
            "metadata": state_meta,
            "totals": {"ok": 0, "error": 0},
            "errors": [],
            "years": [],
        }

        print(f"  {state_name} ({series_id})")
        for year in range(START_YEAR, END_YEAR + 1):
            payload: Any = None
            request_meta: dict[str, Any] = {}
            status_code: int | None = None
            captured_error: Exception | None = None

            try:
                payload, request_meta, status_code = _fred_request(session, series_id, year)
            except Exception as exc:
                captured_error = exc

            result = _classify_result("fred", status_code, payload, captured_error)
            year_path = state_dir / f"{year}.json"
            _write_json(
                year_path,
                {
                    "metadata": state_meta,
                    "year": year,
                    "request": request_meta,
                    "status": result["status"],
                    "error_type": result["error_type"],
                    "recommended_action": result["recommended_action"],
                    "message": result["message"],
                    "response": payload,
                },
            )

            if result["status"] == "ok":
                state_summary["totals"]["ok"] += 1
                aggregate_summary["totals"]["ok"] += 1
            else:
                state_summary["totals"]["error"] += 1
                aggregate_summary["totals"]["error"] += 1
                error_entry = {
                    "year": year,
                    "error_type": result["error_type"],
                    "recommended_action": result["recommended_action"],
                    "message": result["message"],
                    "request": request_meta,
                }
                state_summary["errors"].append(error_entry)
                aggregate_summary["errors"].append(
                    {
                        "state": state_name,
                        "state_slug": state_slug,
                        "series_id": series_id,
                        **error_entry,
                    }
                )

            state_summary["years"].append(
                {
                    "year": year,
                    "status": result["status"],
                    "error_type": result["error_type"],
                    "recommended_action": result["recommended_action"],
                }
            )

        state_summary_path = state_dir / "_summary.json"
        _write_json(state_summary_path, state_summary)
        aggregate_summary["states"].append(
            {
                "state_name": state_name,
                "state_slug": state_slug,
                "series_id": series_id,
                "summary_path": str(state_summary_path),
                "totals": state_summary["totals"],
                "errors": state_summary["errors"],
            }
        )
        print(f"    Summary: {state_summary_path}")

    aggregate_summary_path = base_dir / "_summary.json"
    _write_json(aggregate_summary_path, aggregate_summary)
    print(f"Summary: {aggregate_summary_path}")
    return aggregate_summary
