from __future__ import annotations

import json
import re
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
import sys
from typing import Iterable
from urllib.parse import urlencode

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
WGC_CBD_PAGE = "https://www.gold.org/goldhub/data/monthly-central-bank-statistics"
WGC_CBD_API_BASE = "https://fsapi.gold.org/api/cbd/v11/charts"
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


def fetch_wgc_cbd_page(page: str, **params: str) -> dict:
    query = {"page": page}
    query.update({key: value for key, value in params.items() if value})
    return fetch_json(f"{WGC_CBD_API_BASE}/getPage?{urlencode(query)}", referer=WGC_CBD_PAGE)["chartData"]


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


def flatten_wgc_cbd_snapshot(chart_data: dict, source: str) -> pd.DataFrame:
    latest_date = str(chart_data["options"]["maxDateAvailable"])
    countries = chart_data.get("countries", {})
    table_root = chart_data["table"]
    if latest_date in table_root:
        table = table_root[latest_date]
    else:
        periodicity = str(chart_data["options"].get("selectedPeriodicity", ""))
        table = table_root[periodicity][latest_date]
    headers = [cell.get("filterId", "") for cell in table["headers"][0]]
    column_map = {
        "countryNameDefault": "country",
        "regionGroup": "region_group",
        "economicGroup": "economic_group",
        "fx_reserves": "fx_reserves_usd_mn",
        "total_reserves": "total_reserves_usd_mn",
        "gold_reserves": "gold_reserves_usd_mn",
        "gold_reserves_tns": "gold_reserves_tonnes",
        "holdings_pct": "gold_holdings_pct",
    }

    records: list[dict[str, object]] = []
    for row in table["rows"]:
        iso3 = str(row[0].get("rowId", "")).strip()
        metadata = countries.get(iso3, {})
        record: dict[str, object] = {
            "date": latest_date,
            "iso3": iso3,
            "country": metadata.get("countryNameDefault", ""),
            "country_wgc": metadata.get("countryWGC", ""),
            "region_group": metadata.get("regionGroup", ""),
            "economic_group": metadata.get("economicGroup", ""),
            "source": source,
        }
        for header, cell in zip(headers, row):
            target = column_map.get(header)
            if not target:
                continue
            if target in {"country", "region_group", "economic_group"}:
                record[target] = cell.get("val", "")
            else:
                record[target] = pd.to_numeric(cell.get("val"), errors="coerce")
        records.append(record)

    frame = pd.DataFrame(records)
    frame = frame.sort_values(["date", "gold_reserves_tonnes", "country"], ascending=[True, False, True])
    return frame.reset_index(drop=True)


def flatten_wgc_cbd_linechart(chart_data: dict, periodicity: str, source: str) -> pd.DataFrame:
    countries = chart_data.get("countries", {})
    metric_map = {
        "gold_reserves": "gold_reserves_usd_mn",
        "gold_reserves_pct_chng": "gold_reserves_usd_pct_change",
        "total_reserves": "total_reserves_usd_mn",
        "total_reserves_pct_chng": "total_reserves_usd_pct_change",
        "fx_reserves": "fx_reserves_usd_mn",
        "fx_reserves_pct_chng": "fx_reserves_usd_pct_change",
        "gold_reserves_tns": "gold_reserves_tonnes",
        "gold_reserves_tns_pct_chng": "gold_reserves_tonnes_pct_change",
        "holdings_pct": "gold_holdings_pct",
        "holdings_pct_pct_chng": "gold_holdings_pct_change",
    }
    records_by_key: dict[tuple[str, str], dict[str, object]] = {}

    for metric_key, payload in chart_data["linechart"][periodicity].items():
        target = metric_map.get(metric_key)
        if not target:
            continue
        for series in payload.get("data", []):
            iso3 = str(series.get("name", "")).strip()
            metadata = countries.get(iso3, {})
            for timestamp_ms, value in series.get("data", []):
                if value is None:
                    continue
                date = pd.to_datetime(timestamp_ms, unit="ms").strftime("%Y-%m-%d")
                record = records_by_key.setdefault(
                    (iso3, date),
                    {
                        "date": date,
                        "iso3": iso3,
                        "country": metadata.get("countryNameDefault", ""),
                        "country_wgc": metadata.get("countryWGC", ""),
                        "region_group": metadata.get("regionGroup", ""),
                        "economic_group": metadata.get("economicGroup", ""),
                        "source": source,
                    },
                )
                record[target] = float(value)

    frame = pd.DataFrame(records_by_key.values())
    frame = frame.sort_values(["iso3", "date"]).reset_index(drop=True)
    numeric_columns = [column for column in frame.columns if column.endswith(("_mn", "_pct", "_change", "_tonnes"))]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def derive_wgc_cbd_change(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    working = frame.copy()
    working["date"] = pd.to_datetime(working["date"])
    working = working.sort_values(["iso3", "date"]).reset_index(drop=True)
    working["value"] = working.groupby("iso3")["gold_reserves_tonnes"].diff().round(2)
    working = working.dropna(subset=["value"])
    working = working.loc[working["value"] != 0].copy()
    working["direction"] = working["value"].map(lambda value: "purchase" if value > 0 else "sale")
    working["source"] = source
    return working[
        [
            "date",
            "country",
            "iso3",
            "region_group",
            "economic_group",
            "value",
            "direction",
            "source",
        ]
    ].reset_index(drop=True)


def build_country_metric_series(
    frame: pd.DataFrame,
    value_column: str,
    source: str,
    extra_columns: Iterable[str] = (),
) -> pd.DataFrame:
    columns = ["date", "country", "iso3", *extra_columns]
    normalized = frame[columns].copy()
    normalized["value"] = pd.to_numeric(frame[value_column], errors="coerce")
    normalized["source"] = source
    normalized = normalized.dropna(subset=["value"])
    normalized = normalized.sort_values(["date", "country", "iso3"]).reset_index(drop=True)
    return normalized


def enrich_country_metadata(frame: pd.DataFrame, countries: dict[str, dict[str, object]]) -> pd.DataFrame:
    enriched = frame.copy()
    for column, source_key in [
        ("country", "countryNameDefault"),
        ("country_wgc", "countryWGC"),
        ("region_group", "regionGroup"),
        ("economic_group", "economicGroup"),
    ]:
        if column not in enriched.columns:
            continue
        enriched[column] = enriched.apply(
            lambda row: row[column] if str(row[column] or "").strip() else countries.get(str(row["iso3"]), {}).get(source_key, ""),
            axis=1,
        )
    return enriched


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
    cbd_snapshot_page = fetch_wgc_cbd_page("snapshot")
    cbd_quarterly_page = fetch_wgc_cbd_page(
            "date_range",
            periodicity="QTD_FULL",
            startDate="2000-03-31",
            endDate=str(cbd_snapshot_page["options"]["maxDateAvailable"]),
        )
    country_metadata = {**cbd_snapshot_page.get("countries", {}), **cbd_quarterly_page.get("countries", {})}
    official_gold_reserves_latest = flatten_wgc_cbd_snapshot(
        cbd_snapshot_page,
        "wgc_fsapi:cbd_v11:snapshot_latest",
    )
    official_gold_reserves_quarterly = enrich_country_metadata(
        flatten_wgc_cbd_linechart(
            cbd_quarterly_page,
            "QTD_FULL",
            "wgc_fsapi:cbd_v11:quarterly",
        ),
        country_metadata,
    )
    official_gold_reserves_change_quarterly = derive_wgc_cbd_change(
        official_gold_reserves_quarterly,
        "wgc_fsapi:cbd_v11:quarterly_change",
    )
    official_gold_reserves_tonnes_quarterly = build_country_metric_series(
        official_gold_reserves_quarterly,
        "gold_reserves_tonnes",
        "wgc_fsapi:cbd_v11:quarterly",
        extra_columns=("region_group", "economic_group"),
    )
    gold_as_percent_of_total_reserves_quarterly = build_country_metric_series(
        official_gold_reserves_quarterly,
        "gold_holdings_pct",
        "wgc_fsapi:cbd_v11:quarterly",
        extra_columns=("region_group", "economic_group"),
    )
    reported_central_bank_gold_purchases_sales_quarterly = official_gold_reserves_change_quarterly.copy()

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
        (
            "OFFICIAL_GOLD_RESERVES_LATEST",
            "official_gold_reserves_latest.csv",
            official_gold_reserves_latest,
            (
                "Latest reported official gold reserve snapshot by country from the World Gold Council central bank dashboard. "
                "Fields include gold reserves in tonnes and US$ millions, FX reserves, total reserves, and gold holdings as a percent of total reserves. "
                "Data are monthly in source but represented here as the latest available cross-section."
            ),
        ),
        (
            "OFFICIAL_GOLD_RESERVES_QUARTERLY",
            "official_gold_reserves_quarterly.csv",
            official_gold_reserves_quarterly,
            (
                "Quarterly country-level official gold reserve history from the public World Gold Council central bank dashboard API, "
                "including gold reserves in tonnes and US$ millions, FX reserves, total reserves, and gold holdings percent. "
                "The public API exposes quarterly and year-end history; monthly history is not publicly downloadable without login."
            ),
        ),
        (
            "CHANGE_IN_OFFICIAL_GOLD_RESERVES_QUARTERLY",
            "change_in_official_gold_reserves_quarterly.csv",
            official_gold_reserves_change_quarterly,
            (
                "Quarterly change in reported official gold reserves by country, derived as the difference in tonnes from consecutive public WGC quarterly observations. "
                "Positive values indicate reported purchases and negative values indicate reported sales."
            ),
        ),
        (
            "GOLD_AS_PERCENT_OF_TOTAL_RESERVES_QUARTERLY",
            "gold_as_percent_of_total_reserves_quarterly.csv",
            gold_as_percent_of_total_reserves_quarterly,
            (
                "Quarterly gold holdings as a percent of total reserves by country from the World Gold Council central bank dashboard API."
            ),
        ),
        (
            "REPORTED_CENTRAL_BANK_GOLD_PURCHASES_SALES_QUARTERLY",
            "reported_central_bank_gold_purchases_sales_quarterly.csv",
            reported_central_bank_gold_purchases_sales_quarterly,
            (
                "Quarterly reported central bank gold purchases or sales by country, based on non-zero changes in official gold reserve tonnes between public WGC quarterly observations."
            ),
        ),
        (
            "OFFICIAL_GOLD_RESERVES_TONNES_QUARTERLY",
            "official_gold_reserves_tonnes_quarterly.csv",
            official_gold_reserves_tonnes_quarterly,
            "Quarterly reported official gold reserves by country in tonnes from the World Gold Council central bank dashboard API.",
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
