from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import sys

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gold_data.catalog import refresh_indicator_directory

OUTPUT_DIR = ROOT / "data" / "stock_index"
START_DATE = pd.Timestamp("1985-01-01")
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
PERIOD1 = int(START_DATE.timestamp())

SERIES = (
    {
        "indicator_id": "SP500",
        "symbol": "^GSPC",
        "file_name": "SP500.csv",
        "notes": "S&P 500 Index daily close series from Yahoo Finance chart API.",
    },
    {
        "indicator_id": "NASDAQ100",
        "symbol": "^NDX",
        "file_name": "NASDAQ100.csv",
        "notes": "Nasdaq-100 Index daily close series from Yahoo Finance chart API.",
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


def normalize_daily_close(result: dict[str, object], source: str) -> pd.DataFrame:
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators", {})
    quotes = indicators.get("quote") or []
    if not timestamps or not quotes:
        raise RuntimeError(f"Missing daily close data for {source}")

    quote = quotes[0]
    close_values = quote.get("close", [])
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(timestamps, unit="s"),
            "value": close_values,
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
        chart = fetch_chart(item["symbol"])
        frame = normalize_daily_close(chart, source=f"yahoo:{item['symbol']}")
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
