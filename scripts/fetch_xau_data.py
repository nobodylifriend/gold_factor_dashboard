from __future__ import annotations

import json
import re
from dataclasses import dataclass
from io import BytesIO, StringIO
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
XAU_START_DATE = pd.Timestamp("2006-04-25")
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}
INVESTING_XAU_PAGE = "https://www.investing.com/currencies/xau-usd-historical-data"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
CBOE_HISTORY_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{symbol}_History.csv"
WGC_ETF_PAGE = "https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows"
WGC_ETF_FLOWS_URL = "https://fsapi.gold.org/api/v11/charts/etfv2/revised/flows-chart2?break-cache=27Apr26"
WGC_ETF_HOLDINGS_URL = "https://fsapi.gold.org/api/v11/charts/etfv2/revised/holdings-chart2?break-cache=27Apr2026"
WGC_SUPPLY_AND_DEMAND_PAGE = "https://www.gold.org/goldhub/data/gold-demand-by-country"
WGC_SUPPLY_AND_DEMAND_URL = "https://fsapi.gold.org/api/v11/charts/supply-and-demand/42"
WGC_AISC_PAGE = "https://www.gold.org/goldhub/data/aisc-gold"
WGC_AISC_URL = "https://fsapi.gold.org/api/productioncosts/v11/charts/aisc?break-cache=25-04-25"
SPDR_GLD_PAGE = "https://www.spdrgoldshares.com/usa/gld/"
SPDR_GLD_HISTORICAL_ARCHIVE_URL = (
    "https://api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en"
)
YAHOO_PERIOD1 = int(XAU_START_DATE.timestamp())


@dataclass(frozen=True)
class SourceSummary:
    name: str
    file_name: str
    start_date: str
    end_date: str
    rows: int
    notes: str = ""


def fetch_yahoo_chart(symbol: str) -> dict[str, object]:
    params = {
        "period1": YAHOO_PERIOD1,
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


def fetch_text(url: str, referer: str | None = None) -> str:
    headers = dict(HTTP_HEADERS)
    if referer:
        headers["Referer"] = referer
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()
    return response.text


def fetch_json(url: str, referer: str | None = None) -> dict:
    headers = dict(HTTP_HEADERS)
    if referer:
        headers["Referer"] = referer
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()


def fetch_binary(url: str, referer: str | None = None) -> bytes:
    headers = dict(HTTP_HEADERS)
    if referer:
        headers["Referer"] = referer
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()
    return response.content


def normalize_yahoo_close(
    result: dict[str, object],
    source: str,
    min_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
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
    frame = frame.dropna(subset=["value"])
    if min_date is not None:
        frame = frame.loc[frame["date"] >= min_date]
    frame["source"] = source
    return normalize_value_frame(frame)


def fetch_cboe_history(symbol: str, min_date: pd.Timestamp | None = None) -> pd.DataFrame:
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
    if min_date is not None:
        normalized = normalized.loc[normalized["date"] >= min_date]
    return normalize_value_frame(normalized)


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


def normalize_value_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.strftime("%Y-%m-%d")
    normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce")
    if "source" not in normalized.columns:
        normalized["source"] = ""
    normalized = normalized.dropna(subset=["value"])
    normalized = normalized.drop_duplicates(subset=["date"], keep="last")
    normalized = normalized.sort_values("date").reset_index(drop=True)
    return normalized[["date", "value", "source"]]


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
    frame = frame.loc[
        frame["date"] >= XAU_START_DATE,
        ["date", "open", "high", "low", "close", "volume", "source"],
    ]
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
    frame = frame.loc[pd.to_datetime(frame["date"]) >= XAU_START_DATE, ["date", "close", "source"]]
    return frame.reset_index(drop=True)


def merge_prefer_latest(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    combined = pd.concat(list(frames), ignore_index=True)
    combined = combined.drop_duplicates(subset=["date"], keep="last")
    combined = combined.sort_values("date").reset_index(drop=True)
    return combined


def quarter_label_to_timestamp(label: object) -> pd.Timestamp:
    normalized = str(label).replace("’", "'").strip()
    match = re.fullmatch(r"Q([1-4])\s*'?(?:(\d{2})|(\d{4}))", normalized)
    if not match:
        raise ValueError(f"Unsupported quarter label: {label}")
    quarter = int(match.group(1))
    year_text = match.group(3) or match.group(2)
    year = int(year_text)
    if len(year_text) == 2:
        year += 2000
    return pd.Period(f"{year}Q{quarter}", freq="Q").end_time.normalize()


def annual_label_to_timestamp(label: object) -> pd.Timestamp:
    year = int(label)
    return pd.Timestamp(year=year, month=12, day=31)


def fetch_wgc_etf_holdings(frequency: str) -> pd.DataFrame:
    payload = fetch_json(WGC_ETF_HOLDINGS_URL, referer=WGC_ETF_PAGE)["chartData"]["data"][frequency]["tonnes"]
    columns = [str(column) for column in payload["columns"]]
    value_indexes = [
        index
        for index, column in enumerate(columns)
        if index > 0 and "gold" not in column.lower()
    ]
    records = []
    for row in payload["set"]:
        total = sum(float(row[index]) for index in value_indexes if pd.notna(row[index]))
        records.append(
            {
                "date": pd.to_datetime(row[0], unit="ms"),
                "value": total,
                "source": f"wgc_fsapi:etf_holdings:{frequency.lower()}",
            }
        )
    return normalize_value_frame(pd.DataFrame(records))


def fetch_wgc_etf_flows(frequency: str) -> pd.DataFrame:
    payload = fetch_json(WGC_ETF_FLOWS_URL, referer=WGC_ETF_PAGE)["chartData"]["data"][frequency]["series"]["tonnes"]
    totals: dict[int, float] = {}
    for series in payload:
        if "gold price" in str(series.get("name", "")).lower():
            continue
        for timestamp_ms, value in series.get("data", []):
            if value is None:
                continue
            totals[int(timestamp_ms)] = totals.get(int(timestamp_ms), 0.0) + float(value)
    records = [
        {
            "date": pd.to_datetime(timestamp_ms, unit="ms"),
            "value": value,
            "source": f"wgc_fsapi:etf_flows:{frequency.lower()}",
        }
        for timestamp_ms, value in sorted(totals.items())
    ]
    return normalize_value_frame(pd.DataFrame(records))


def fetch_spdr_gld_historical_archive() -> pd.DataFrame:
    content = fetch_binary(SPDR_GLD_HISTORICAL_ARCHIVE_URL, referer=SPDR_GLD_PAGE)
    frame = pd.read_excel(BytesIO(content), sheet_name="US GLD Historical Archive")
    frame = frame.rename(
        columns={
            "Date": "date",
            "Daily Share Volume": "daily_share_volume",
            "Tonnes of Gold": "tonnes_of_gold",
        }
    )
    frame["date"] = pd.to_datetime(frame["date"], format="%d-%b-%Y", errors="coerce")
    frame = frame.dropna(subset=["date"]).reset_index(drop=True)
    return frame


def build_spdr_value_series(frame: pd.DataFrame, column: str, source: str) -> pd.DataFrame:
    normalized = frame[["date", column]].rename(columns={column: "value"}).copy()
    normalized["source"] = source
    return normalize_value_frame(normalized)


def fetch_wgc_supply_and_demand_series(section: str, series_name: str, source: str) -> pd.DataFrame:
    payload = fetch_json(WGC_SUPPLY_AND_DEMAND_URL, referer=WGC_SUPPLY_AND_DEMAND_PAGE)["chartData"][section]
    series = next(item for item in payload["series"] if item["name"] == series_name)
    categories = payload["categories"]
    date_parser = annual_label_to_timestamp if "Annually" in section else quarter_label_to_timestamp
    frame = pd.DataFrame(
        {
            "date": [date_parser(label) for label in categories],
            "value": series["data"],
            "source": source,
        }
    )
    return normalize_value_frame(frame)


def fetch_wgc_aisc_quarterly() -> pd.DataFrame:
    payload = fetch_json(WGC_AISC_URL, referer=WGC_AISC_PAGE)["chartData"]
    frame = pd.DataFrame(
        {
            "date": [quarter_label_to_timestamp(label) for label in payload["categories"]],
            "value": payload["data"],
            "source": "wgc_fsapi:gold_aisc:quarterly",
        }
    )
    return normalize_value_frame(frame)


def derive_full_year_average(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    working = frame.copy()
    working["date"] = pd.to_datetime(working["date"])
    working["year"] = working["date"].dt.year
    annual = (
        working.groupby("year", as_index=False)
        .agg(value=("value", "mean"), periods=("value", "size"))
        .loc[lambda data: data["periods"] == 4, ["year", "value"]]
        .reset_index(drop=True)
    )
    annual["date"] = annual["year"].map(lambda year: pd.Timestamp(year=int(year), month=12, day=31))
    annual["source"] = source
    return normalize_value_frame(annual[["date", "value", "source"]])


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
    gvz = merge_prefer_latest(
        [
            normalize_yahoo_close(fetch_yahoo_chart("^GVZ"), source="yahoo:^GVZ", min_date=XAU_START_DATE),
            fetch_cboe_history("GVZ", min_date=XAU_START_DATE),
        ]
    )

    daily_ohlc = merge_prefer_latest([kafka_daily, fokan_2025, fokan_202601, investing_recent])
    daily_ohlc = daily_ohlc.loc[pd.to_datetime(daily_ohlc["date"]) >= XAU_START_DATE].reset_index(drop=True)

    global_gold_etf_holdings_weekly = fetch_wgc_etf_holdings("Weekly")
    global_gold_etf_holdings_monthly = fetch_wgc_etf_holdings("Monthly")
    global_gold_etf_net_flows_weekly = fetch_wgc_etf_flows("Weekly")
    global_gold_etf_net_flows_monthly = fetch_wgc_etf_flows("Monthly")

    gld_archive = fetch_spdr_gld_historical_archive()
    gld_total_holdings_tonnes = build_spdr_value_series(
        gld_archive,
        "tonnes_of_gold",
        "spdr_api:gld_historical_archive",
    )
    gld_share_volume = build_spdr_value_series(
        gld_archive,
        "daily_share_volume",
        "spdr_api:gld_historical_archive",
    )

    global_gold_mine_production_quarterly = fetch_wgc_supply_and_demand_series(
        "Supply_Quarterly",
        "Mine production",
        "wgc_fsapi:supply_and_demand:quarterly",
    )
    global_gold_mine_production_annual = fetch_wgc_supply_and_demand_series(
        "Supply_Annually",
        "Mine production",
        "wgc_fsapi:supply_and_demand:annual",
    )
    global_gold_aisc_quarterly = fetch_wgc_aisc_quarterly()
    global_gold_aisc_annual = derive_full_year_average(
        global_gold_aisc_quarterly,
        "wgc_fsapi:gold_aisc:annual_mean",
    )

    artifacts = [
        (
            "xau_usd_daily_ohlc",
            "xau_usd_daily_ohlc.csv",
            daily_ohlc,
            (
                "Daily OHLC merged from multiple public sources. "
                "Coverage is strongest from 2006-04-25 to 2026-01-09 and 2026-03-25 to the latest recent window. "
                "See source column for provenance."
            ),
        ),
        (
            "xau_usd_monthly_close",
            "xau_usd_monthly_close.csv",
            monthly_close,
            "Complete monthly close series from Macrotrends through the latest published month.",
        ),
        (
            "GVZ",
            "GVZ.csv",
            gvz,
            "Daily close series merged with Cboe official history preferred and Yahoo Finance used only for older backfill if needed.",
        ),
        (
            "GLOBAL_GOLD_ETF_HOLDINGS_WEEKLY",
            "global_gold_etf_holdings_weekly.csv",
            global_gold_etf_holdings_weekly,
            "Weekly global physically backed gold ETF holdings aggregated across North America, Europe, Asia, and Other; units are tonnes.",
        ),
        (
            "GLOBAL_GOLD_ETF_HOLDINGS_MONTHLY",
            "global_gold_etf_holdings_monthly.csv",
            global_gold_etf_holdings_monthly,
            "Monthly global physically backed gold ETF holdings aggregated across North America, Europe, Asia, and Other; units are tonnes.",
        ),
        (
            "GLOBAL_GOLD_ETF_NET_FLOWS_WEEKLY",
            "global_gold_etf_net_flows_weekly.csv",
            global_gold_etf_net_flows_weekly,
            "Weekly global gold ETF net flows aggregated across regions using WGC tonnage flow series.",
        ),
        (
            "GLOBAL_GOLD_ETF_NET_FLOWS_MONTHLY",
            "global_gold_etf_net_flows_monthly.csv",
            global_gold_etf_net_flows_monthly,
            "Monthly global gold ETF net flows aggregated across regions using WGC tonnage flow series.",
        ),
        (
            "GLD_TOTAL_HOLDINGS_TONNES",
            "GLD_total_holdings_tonnes.csv",
            gld_total_holdings_tonnes,
            "Daily GLD trust gold holdings in tonnes from the official SPDR Gold Shares historical archive.",
        ),
        (
            "GLD_DAILY_SHARE_VOLUME",
            "GLD_share_volume.csv",
            gld_share_volume,
            "Daily GLD exchange share volume from the official SPDR Gold Shares historical archive.",
        ),
        (
            "GLOBAL_GOLD_MINE_PRODUCTION_QUARTERLY",
            "global_gold_mine_production_quarterly.csv",
            global_gold_mine_production_quarterly,
            "Quarterly global mine production from the World Gold Council supply and demand dataset; units are tonnes.",
        ),
        (
            "GLOBAL_GOLD_MINE_PRODUCTION_ANNUAL",
            "global_gold_mine_production_annual.csv",
            global_gold_mine_production_annual,
            "Annual global mine production from the World Gold Council supply and demand dataset; units are tonnes.",
        ),
        (
            "GLOBAL_GOLD_AISC_QUARTERLY",
            "global_gold_aisc_quarterly.csv",
            global_gold_aisc_quarterly,
            "Quarterly global average all-in sustaining cost (AISC) from the World Gold Council production costs dataset; units are US$/oz.",
        ),
        (
            "GLOBAL_GOLD_AISC_ANNUAL",
            "global_gold_aisc_annual.csv",
            global_gold_aisc_annual,
            "Annual average AISC derived as the simple mean of complete quarterly WGC AISC observations within each calendar year; units are US$/oz.",
        ),
    ]

    manifest = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "base_start_date": str(XAU_START_DATE.date()),
        "artifacts": [],
    }

    for name, file_name, frame, notes in artifacts:
        path = OUTPUT_DIR / file_name
        write_csv(path, frame)
        manifest["artifacts"].append(summarize(frame, name, file_name, notes=notes).__dict__)
        print(f"Wrote {path}")

    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    refresh_indicator_directory(ROOT)

    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
