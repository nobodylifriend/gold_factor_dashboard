from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
import sys
from typing import Iterable

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gold_data.catalog import refresh_indicator_directory

OUTPUT_DIR = ROOT / "data" / "xau"
START_DATE = pd.Timestamp("2006-04-25")
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}
INVESTING_XAU_PAGE = "https://www.investing.com/currencies/xau-usd-historical-data"


@dataclass(frozen=True)
class SourceSummary:
    name: str
    file_name: str
    start_date: str
    end_date: str
    rows: int
    notes: str = ""


def fetch_text(url: str) -> str:
    response = requests.get(url, headers=HTTP_HEADERS, timeout=60)
    response.raise_for_status()
    return response.text


def fetch_json(url: str) -> dict:
    response = requests.get(url, headers=HTTP_HEADERS, timeout=60)
    response.raise_for_status()
    return response.json()


def extract_next_data_build_id(html: str) -> str:
    start = '<script id="__NEXT_DATA__" type="application/json">'
    end = "</script>"
    start_index = html.find(start)
    if start_index == -1:
        raise RuntimeError("Could not locate __NEXT_DATA__ payload on Investing page")
    end_index = html.find(end, start_index)
    if end_index == -1:
        raise RuntimeError("Could not find end of __NEXT_DATA__ payload on Investing page")
    payload = json.loads(html[start_index + len(start) : end_index])
    build_id = str(payload.get("buildId", "")).strip()
    if not build_id:
        raise RuntimeError("Investing __NEXT_DATA__ payload is missing buildId")
    return build_id


def normalize_daily_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.strftime("%Y-%m-%d")
    for column in ["open", "high", "low", "close"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    if "volume" in normalized.columns:
        normalized["volume"] = pd.to_numeric(normalized["volume"], errors="coerce").fillna(0)
    normalized = normalized.dropna(subset=["open", "high", "low", "close"])
    normalized = normalized.drop_duplicates(subset=["date"], keep="last")
    normalized = normalized.sort_values("date").reset_index(drop=True)
    return normalized


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def fetch_kafka7_daily() -> pd.DataFrame:
    text = fetch_text(
        "https://huggingface.co/datasets/kafka7/xauusd-gold-price-historical-data-2004-2025/resolve/main/XAU_1d_data.jsonl"
    )
    records = [json.loads(line) for line in text.splitlines() if line.strip()]
    frame = pd.DataFrame(records)
    frame = frame.rename(
        columns={
            "Date": "raw_date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    frame["date"] = pd.to_datetime(frame["raw_date"], format="%Y.%m.%d %H:%M")
    frame["source"] = "huggingface:kafka7:1d"
    frame = frame.loc[frame["date"] >= START_DATE, ["date", "open", "high", "low", "close", "volume", "source"]]
    return normalize_daily_frame(frame)


def fetch_fokan_m1(file_name: str) -> pd.DataFrame:
    csv_text = fetch_text(f"https://huggingface.co/datasets/fokan/xauusd-2009-2026/resolve/main/{file_name}")
    minute = pd.read_csv(
        StringIO(csv_text),
        header=None,
        names=["raw_date", "raw_time", "open", "high", "low", "close", "volume"],
    )
    minute["date"] = pd.to_datetime(minute["raw_date"], format="%Y.%m.%d")
    daily = (
        minute.groupby("date", as_index=False)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    daily["source"] = f"huggingface:fokan:{file_name}"
    return normalize_daily_frame(daily)


def fetch_investing_recent_daily() -> pd.DataFrame:
    build_id = extract_next_data_build_id(fetch_text(INVESTING_XAU_PAGE))
    payload = fetch_json(
        f"https://www.investing.com/_next/data/{build_id}/currencies/xau-usd-historical-data.json"
    )
    rows = payload["pageProps"]["state"]["historicalDataStore"]["historicalData"]["data"]
    frame = pd.DataFrame(
        {
            "date": [row["rowDateTimestamp"] for row in rows],
            "open": [row["last_openRaw"] for row in rows],
            "high": [row["last_maxRaw"] for row in rows],
            "low": [row["last_minRaw"] for row in rows],
            "close": [row["last_closeRaw"] for row in rows],
            "volume": [row.get("volumeRaw", 0) for row in rows],
        }
    )
    frame["date"] = pd.to_datetime(frame["date"])
    frame["source"] = "investing:next-data:recent-window"
    return normalize_daily_frame(frame)


def fetch_macrotrends_monthly() -> pd.DataFrame:
    payload = fetch_json("https://www.macrotrends.net/economic-data/1333/5/D")
    frame = pd.DataFrame(payload["data"], columns=["timestamp_ms", "close"])
    frame["date"] = pd.to_datetime(frame["timestamp_ms"], unit="ms").dt.strftime("%Y-%m-%d")
    frame["source"] = "macrotrends:monthly"
    frame = frame.loc[pd.to_datetime(frame["date"]) >= START_DATE, ["date", "close", "source"]]
    return frame.reset_index(drop=True)


def merge_prefer_latest(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    combined = pd.concat(list(frames), ignore_index=True)
    combined = combined.drop_duplicates(subset=["date"], keep="last")
    combined = combined.sort_values("date").reset_index(drop=True)
    return combined


def summarize(frame: pd.DataFrame, name: str, file_name: str, notes: str = "") -> SourceSummary:
    return SourceSummary(
        name=name,
        file_name=file_name,
        start_date=str(frame["date"].iloc[0]),
        end_date=str(frame["date"].iloc[-1]),
        rows=len(frame),
        notes=notes,
    )


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    kafka_daily = fetch_kafka7_daily()
    fokan_2025 = fetch_fokan_m1("DAT_MT_XAUUSD_M1_2025.csv")
    fokan_202601 = fetch_fokan_m1("DAT_MT_XAUUSD_M1_202601.csv")
    investing_recent = fetch_investing_recent_daily()
    monthly_close = fetch_macrotrends_monthly()

    daily_ohlc = merge_prefer_latest([kafka_daily, fokan_2025, fokan_202601, investing_recent])
    daily_ohlc = daily_ohlc.loc[pd.to_datetime(daily_ohlc["date"]) >= START_DATE].reset_index(drop=True)

    daily_path = OUTPUT_DIR / "xau_usd_daily_ohlc.csv"
    monthly_path = OUTPUT_DIR / "xau_usd_monthly_close.csv"
    manifest_path = OUTPUT_DIR / "manifest.json"

    write_csv(daily_path, daily_ohlc)
    write_csv(monthly_path, monthly_close)

    manifest = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "base_start_date": str(START_DATE.date()),
        "artifacts": [
            summarize(
                daily_ohlc,
                "xau_usd_daily_ohlc",
                daily_path.name,
                notes=(
                    "Daily OHLC merged from multiple public sources. "
                    "Coverage is strongest from 2006-04-25 to 2026-01-09 and 2026-03-25 to the latest recent window. "
                    "See source column for provenance."
                ),
            ).__dict__,
            summarize(
                monthly_close,
                "xau_usd_monthly_close",
                monthly_path.name,
                notes="Complete monthly close series from Macrotrends through the latest published month.",
            ).__dict__,
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    refresh_indicator_directory(ROOT)

    print(f"Wrote {daily_path}")
    print(f"Wrote {monthly_path}")
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
