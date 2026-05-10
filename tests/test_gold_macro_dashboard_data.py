from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_gold_macro_dashboard_data import (  # noqa: E402
    DASHBOARD_SERIES,
    OUTPUT,
    build_dashboard_payload,
    compute_trend_label,
    load_series_frame,
    main,
)


def test_compute_trend_label_respects_per_series_thresholds():
    assert compute_trend_label("tips10y", 1.50, 1.52) == "横盘"
    assert compute_trend_label("tips10y", 1.50, 1.56) == "上升"
    assert compute_trend_label("dxy", 103.0, 102.85) == "横盘"
    assert compute_trend_label("dxy", 103.0, 102.6) == "下降"


def test_load_series_frame_normalizes_close_and_value_columns():
    xau = load_series_frame(Path("data/xau/xau_usd_daily_ohlc.csv"), value_column="close")
    spx = load_series_frame(Path("data/stock_index/SP500.csv"), value_column="value")

    assert list(xau.columns) == ["date", "value"]
    assert list(spx.columns) == ["date", "value"]
    assert xau["date"].is_monotonic_increasing
    assert spx["date"].is_monotonic_increasing


def test_build_dashboard_payload_contains_all_required_sections():
    payload = build_dashboard_payload()

    assert sorted(payload.keys()) == ["generated_at", "metadata", "series", "tab_layouts"]
    assert sorted(payload["series"].keys()) == sorted(DASHBOARD_SERIES.keys())
    assert payload["metadata"]["hero_chart_ids"] == ["xau", "sp500", "nasdaq100"]
    assert payload["metadata"]["detail_chart_ids"] == [
        "tips10y",
        "dxy",
        "nominal10y",
        "breakeven10y",
        "credit_oas_hy",
        "sofr",
    ]


def test_build_dashboard_payload_exposes_default_date_bounds():
    payload = build_dashboard_payload()

    assert payload["metadata"]["default_range"]["start"]
    assert payload["metadata"]["default_range"]["end"]
    assert payload["metadata"]["series_order"] == [
        "xau",
        "sp500",
        "nasdaq100",
        "tips10y",
        "dxy",
        "nominal10y",
        "breakeven10y",
        "credit_oas_hy",
        "sofr",
    ]


def test_main_writes_dashboard_json_file():
    main()

    assert OUTPUT.exists()
    data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert data["series"]["xau"]["label"] == "黄金价格走势"
    assert data["series"]["xau"]["frequency_label"] == "日频"
    assert data["series"]["xau"]["description_zh"]
    assert data["series"]["xau_monthly"]["frequency_label"] == "月频"
    assert data["series"]["total_debt_to_gdp"]["frequency_label"] == "季频"
    assert data["series"]["xau"]["latest_date"]
    assert data["metadata"]["quadrant_axes"] == {"x": "dxy", "y": "tips10y"}


def test_build_dashboard_payload_exposes_tab_layouts_and_insights():
    payload = build_dashboard_payload()
    tabs = payload["metadata"]["tabs"]
    tab_ids = [tab["id"] for tab in tabs]

    assert tab_ids == ["overview", "gold", "rates", "inflation", "usd", "risk", "fiscal"]
    assert payload["metadata"]["tab_order"] == tab_ids
    assert payload["tab_layouts"]["overview"]["hero_chart_ids"] == ["xau", "sp500", "nasdaq100"]
    assert "gold_summary" in payload["tab_layouts"]["overview"]["summary_cards"]
    assert payload["tab_layouts"]["gold"]["sections"][0]["series_ids"] == ["xau", "xau_monthly", "gvz"]
    assert payload["tab_layouts"]["gold"]["sections"][1]["series_ids"] == [
        "gld_holdings",
        "global_gold_etf_holdings_weekly",
        "gold_etf_flows",
        "global_gold_etf_flows_weekly",
        "gld_volume",
    ]
    assert payload["tab_layouts"]["gold"]["sections"][2]["series_ids"] == [
        "global_gold_mine_production_quarterly",
        "global_gold_aisc_quarterly",
        "official_gold_reserve_change_quarterly",
    ]
    assert payload["tab_layouts"]["rates"]["sections"][0]["series_ids"] == ["tips10y", "tips5y", "tips30y"]
    assert payload["tab_layouts"]["rates"]["sections"][1]["series_ids"] == ["sofr", "fedfunds", "tbill3m", "m2"]
    assert payload["tab_layouts"]["inflation"]["sections"][0]["series_ids"] == [
        "breakeven10y",
        "breakeven5y",
        "forward5y5y",
    ]
    assert payload["tab_layouts"]["inflation"]["sections"][1]["series_ids"] == [
        "cpi_yoy",
        "core_cpi_yoy",
        "pce_yoy",
        "core_pce_yoy",
        "michigan_1y_inflation_expectation",
    ]
    assert payload["tab_layouts"]["usd"]["sections"][0]["series_ids"] == ["dxy", "broad_dollar", "eurusd"]
    assert payload["tab_layouts"]["usd"]["sections"][1]["series_ids"] == ["usdjpy", "gbpusd", "audusd", "usdchf"]
    assert payload["tab_layouts"]["risk"]["sections"][0]["series_ids"] == ["sp500", "nasdaq100", "vix", "vxn"]
    assert payload["tab_layouts"]["risk"]["sections"][1]["series_ids"] == [
        "hy_oas",
        "ig_oas",
        "vvix",
        "vix3m",
        "skew",
        "stlfsi",
        "copper",
        "wti",
    ]
    assert payload["tab_layouts"]["fiscal"]["sections"][0]["series_ids"] == [
        "total_debt_to_gdp",
        "debt_held_by_public_to_gdp",
        "interest_payments_to_gdp",
        "average_interest_rate_on_debt",
    ]
    assert payload["tab_layouts"]["usd"]["insights"][0]["series_id"] == "dxy"
    assert payload["tab_layouts"]["risk"]["insights"][1]["series_id"] == "vix"
    assert payload["tab_layouts"]["fiscal"]["insights"][2]["series_id"] == "treasury_borrowing_estimate"


def test_series_payload_includes_frequency_latest_date_and_chinese_description():
    payload = build_dashboard_payload()
    xau = payload["series"]["xau"]
    dxy = payload["series"]["dxy"]

    assert xau["frequency_label"] == "日频"
    assert xau["latest_date"]
    assert "金价" in xau["description_zh"]
    assert "美元" in dxy["description_zh"]


def test_build_dashboard_payload_includes_new_factor_series():
    payload = build_dashboard_payload()

    expected_series_ids = [
        "global_gold_etf_holdings_weekly",
        "global_gold_etf_flows_weekly",
        "gld_volume",
        "global_gold_mine_production_quarterly",
        "global_gold_aisc_quarterly",
        "official_gold_reserve_change_quarterly",
        "tbill3m",
        "michigan_1y_inflation_expectation",
        "vxn",
        "vix3m",
        "skew",
        "gbpusd",
        "audusd",
        "usdchf",
        "average_interest_rate_on_debt",
    ]

    for series_id in expected_series_ids:
        assert series_id in payload["series"]
        assert payload["series"][series_id]["description_zh"]
        assert payload["series"][series_id]["latest_date"]
