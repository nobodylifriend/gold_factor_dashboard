from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "visuals" / "gold_macro_dashboard" / "data" / "dashboard_data.json"

DASHBOARD_SERIES = {
    "xau": {
        "path": ROOT / "data" / "xau" / "xau_usd_daily_ohlc.csv",
        "value_column": "close",
        "label": "黄金价格走势",
    },
    "sp500": {
        "path": ROOT / "data" / "stock_index" / "SP500.csv",
        "value_column": "value",
        "label": "标普500价格走势",
    },
    "nasdaq100": {
        "path": ROOT / "data" / "stock_index" / "NASDAQ100.csv",
        "value_column": "value",
        "label": "纳斯达克100价格走势",
    },
    "tips10y": {
        "path": ROOT / "data" / "fred" / "名义利率" / "10年期TIPS实际收益率.csv",
        "value_column": "value",
        "label": "10年期TIPS实际收益率",
    },
    "dxy": {
        "path": ROOT / "data" / "fx" / "DXY.csv",
        "value_column": "close",
        "label": "DXY",
    },
    "nominal10y": {
        "path": ROOT / "data" / "fred" / "名义利率" / "10年期美债收益率.csv",
        "value_column": "value",
        "label": "10年期美债收益率",
    },
    "breakeven10y": {
        "path": ROOT / "data" / "fred" / "通胀_通胀预期" / "10年盈亏平衡通胀率.csv",
        "value_column": "value",
        "label": "10年盈亏平衡通胀率",
    },
    "credit_oas_hy": {
        "path": ROOT / "data" / "fred" / "信用利差" / "高收益信用利差_OAS.csv",
        "value_column": "value",
        "label": "高收益信用利差_OAS",
    },
    "sofr": {
        "path": ROOT / "data" / "fred" / "名义利率" / "SOFR.csv",
        "value_column": "value",
        "label": "SOFR",
    },
}

TREND_THRESHOLDS = {
    "tips10y": 0.03,
    "nominal10y": 0.03,
    "breakeven10y": 0.03,
    "credit_oas_hy": 0.03,
    "sofr": 0.03,
    "dxy": 0.20,
}


def compute_trend_label(series_id: str, start_value: float, end_value: float) -> str:
    delta = end_value - start_value
    threshold = TREND_THRESHOLDS.get(series_id, 0.0)
    if abs(delta) < threshold:
        return "横盘"
    return "上升" if delta > 0 else "下降"


def load_series_frame(path: Path, value_column: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    normalized = frame.loc[:, ["date", value_column]].rename(columns={value_column: "value"}).copy()
    normalized["date"] = pd.to_datetime(normalized["date"], utc=False).dt.strftime("%Y-%m-%d")
    normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce")
    normalized = normalized.dropna(subset=["date", "value"]).sort_values("date").reset_index(drop=True)
    return normalized


def build_dashboard_payload() -> dict:
    series = {}
    all_dates: list[str] = []
    series_order = list(DASHBOARD_SERIES.keys())

    for series_id, spec in DASHBOARD_SERIES.items():
        frame = load_series_frame(spec["path"], spec["value_column"])
        points = frame.to_dict(orient="records")
        series[series_id] = {
            "label": spec["label"],
            "points": points,
            "value_precision": 2,
        }
        all_dates.extend(point["date"] for point in points)

    unique_dates = sorted(set(all_dates))
    default_start_index = max(len(unique_dates) - 252, 0)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "title": "黄金 / 美元 / 利率 信号矩阵",
            "hero_chart_ids": ["xau", "sp500", "nasdaq100"],
            "detail_chart_ids": ["tips10y", "dxy", "nominal10y", "breakeven10y", "credit_oas_hy", "sofr"],
            "series_order": series_order,
            "quadrant_axes": {"x": "dxy", "y": "tips10y"},
            "default_range": {
                "start": unique_dates[default_start_index],
                "end": unique_dates[-1],
            },
            "trend_thresholds": TREND_THRESHOLDS,
        },
        "series": series,
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build_dashboard_payload(), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
