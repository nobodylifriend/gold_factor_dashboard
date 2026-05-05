import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_gold_macro_dashboard_data import (
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

    assert sorted(payload.keys()) == ["generated_at", "metadata", "series"]
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
    assert data["metadata"]["quadrant_axes"] == {"x": "dxy", "y": "tips10y"}
