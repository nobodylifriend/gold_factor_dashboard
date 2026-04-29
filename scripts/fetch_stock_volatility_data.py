from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
import sys

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gold_data.catalog import refresh_indicator_directory

OUTPUT_DIR = ROOT / "data" / "stock_volatility"
START_DATE = pd.Timestamp("1990-01-01")
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
CBOE_HISTORY_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{symbol}_History.csv"
PERIOD1 = int(START_DATE.timestamp())

SERIES = (
    {
        "indicator_id": "VIX",
        "symbol": "^VIX",
        "file_name": "VIX.csv",
        "notes": "Daily close series merged with Cboe official history preferred and Yahoo Finance used only for older backfill if needed.",
    },
    {
        "indicator_id": "VIX1D",
        "symbol": "^VIX1D",
        "file_name": "VIX1D.csv",
        "notes": "Daily close series merged with Cboe official history preferred and Yahoo Finance used only for older backfill if needed.",
    },
    {
        "indicator_id": "VIX9D",
        "symbol": "^VIX9D",
        "file_name": "VIX9D.csv",
        "notes": "Daily close series merged with Cboe official history preferred and Yahoo Finance used only for older backfill if needed.",
    },
    {
        "indicator_id": "VIX3M",
        "symbol": "^VIX3M",
        "file_name": "VIX3M.csv",
        "notes": "Daily close series merged with Cboe official history preferred and Yahoo Finance used only for older backfill if needed.",
    },
    {
        "indicator_id": "VIX6M",
        "symbol": "^VIX6M",
        "file_name": "VIX6M.csv",
        "notes": "Daily close series merged with Cboe official history preferred and Yahoo Finance used only for older backfill if needed.",
    },
    {
        "indicator_id": "VIX1Y",
        "symbol": "^VIX1Y",
        "file_name": "VIX1Y.csv",
        "notes": "Daily close series merged with Cboe official history preferred and Yahoo Finance used only for older backfill if needed.",
    },
    {
        "indicator_id": "VXN",
        "symbol": "^VXN",
        "file_name": "VXN.csv",
        "notes": "Daily close series merged with Cboe official history preferred and Yahoo Finance used only for older backfill if needed.",
    },
    {
        "indicator_id": "VVIX",
        "symbol": "^VVIX",
        "file_name": "VVIX.csv",
        "notes": "Daily close series merged with Cboe official history preferred and Yahoo Finance used only for older backfill if needed.",
    },
    {
        "indicator_id": "SKEW",
        "symbol": "^SKEW",
        "file_name": "SKEW.csv",
        "notes": "Daily close series merged with Cboe official history preferred and Yahoo Finance used only for older backfill if needed.",
    },
)


@dataclass(frozen=True)
class ArtifactSummary:
    name: str
    file_name: str
    start_date: str
    end_date: str
    rows: int
    notes: str = ""


def fetch_chart(symbol: str) -> dict[str, object]:
    params = {
        "period1": PERIOD1,
        "period2": int(pd.Timestamp.utcnow().timestamp()) + 86400,
        "interval": "1d",
        "includePrePost": "false",
        "events": "div,splits",
    }
    response = requests.get(
        YAHOO_CHART_URL.format(symbol=symbol),
        params=params,
        headers=HTTP_HEADERS,
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("chart", {}).get("result") or []
    if not result:
        error = payload.get("chart", {}).get("error") or {}
        raise RuntimeError(f"No chart result returned for {symbol}: {error}")
    return result[0]


def fetch_cboe_history(symbol: str) -> pd.DataFrame:
    response = requests.get(
        CBOE_HISTORY_URL.format(symbol=symbol),
        headers=HTTP_HEADERS,
        timeout=60,
    )
    response.raise_for_status()
    frame = pd.read_csv(StringIO(response.text))
    frame.columns = [str(column).strip().upper() for column in frame.columns]
    if "DATE" not in frame.columns:
        raise RuntimeError(f"Cboe history is missing DATE column for {symbol}")

    value_column = "CLOSE" if "CLOSE" in frame.columns else next(
        (column for column in frame.columns if column != "DATE"),
        "",
    )
    if not value_column:
        raise RuntimeError(f"Cboe history is missing value column for {symbol}")

    normalized = pd.DataFrame(
        {
            "date": pd.to_datetime(frame["DATE"], format="%m/%d/%Y", errors="coerce"),
            "value": pd.to_numeric(frame[value_column], errors="coerce"),
            "source": f"cboe:{symbol}_History.csv",
        }
    )
    normalized = normalized.dropna(subset=["date", "value"])
    normalized = normalized.loc[normalized["date"] >= START_DATE]
    normalized["date"] = normalized["date"].dt.strftime("%Y-%m-%d")
    normalized = normalized.drop_duplicates(subset=["date"], keep="last")
    normalized = normalized.sort_values("date").reset_index(drop=True)
    return normalized


def normalize_yahoo_close(result: dict[str, object], source: str) -> pd.DataFrame:
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators", {})
    quotes = indicators.get("quote") or []
    adjclose_items = indicators.get("adjclose") or []
    if not timestamps or not quotes:
        raise RuntimeError(f"Missing daily data for {source}")

    quote = quotes[0]
    adjclose = adjclose_items[0].get("adjclose", []) if adjclose_items else []
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(timestamps, unit="s"),
            "value": adjclose if adjclose else quote.get("close", []),
        }
    )
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame["source"] = source
    frame = frame.dropna(subset=["value"])
    frame = frame.loc[frame["date"] >= START_DATE]
    frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
    frame = frame.drop_duplicates(subset=["date"], keep="last")
    frame = frame.sort_values("date").reset_index(drop=True)
    return frame[["date", "value", "source"]]


def merge_prefer_official(frames: list[pd.DataFrame]) -> pd.DataFrame:
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["date"], keep="last")
    combined = combined.sort_values("date").reset_index(drop=True)
    return combined


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def summarize(frame: pd.DataFrame, indicator_id: str, file_name: str, notes: str) -> ArtifactSummary:
    return ArtifactSummary(
        name=indicator_id,
        file_name=file_name,
        start_date=str(frame["date"].iloc[0]),
        end_date=str(frame["date"].iloc[-1]),
        rows=len(frame),
        notes=notes,
    )


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    artifacts: list[dict[str, object]] = []
    for item in SERIES:
        yahoo_frame = normalize_yahoo_close(fetch_chart(item["symbol"]), source=f"yahoo:{item['symbol']}")
        cboe_frame = fetch_cboe_history(item["indicator_id"])
        frame = merge_prefer_official([yahoo_frame, cboe_frame])
        write_csv(OUTPUT_DIR / item["file_name"], frame)
        artifacts.append(summarize(frame, item["indicator_id"], item["file_name"], item["notes"]).__dict__)

    manifest = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "base_start_date": str(START_DATE.date()),
        "artifacts": artifacts,
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    refresh_indicator_directory(ROOT)

    for artifact in artifacts:
        print(f"Wrote {OUTPUT_DIR / artifact['file_name']}")
    print(f"Wrote {OUTPUT_DIR / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
