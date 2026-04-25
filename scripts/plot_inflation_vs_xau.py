from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

from src.gold_data.access import IndicatorStore


OUTPUT_DIR = ROOT / "reports" / "figures" / "inflation_vs_xau"
XAU_PATH = ROOT / "data" / "xau" / "xau_usd_daily_ohlc.csv"
INFLATION_CATEGORY = "\u901a\u80c0 / \u901a\u80c0\u9884\u671f"
GOLD_COLOR = "#C99700"
INDICATOR_COLOR = "#2E5BFF"
TITLE_COLOR = "#1F2937"
GRID_COLOR = "#D7DCE5"
SPINE_COLOR = "#C8CED8"
BACKGROUND_COLOR = "#FCFCFD"


def configure_matplotlib() -> None:
    preferred_fonts = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "PingFang SC",
        "WenQuanYi Zen Hei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    available = {font.name for font in fm.fontManager.ttflist}
    selected = [font for font in preferred_fonts if font in available]
    plt.rcParams["font.family"] = selected or ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = BACKGROUND_COLOR
    plt.rcParams["axes.facecolor"] = BACKGROUND_COLOR
    plt.rcParams["savefig.facecolor"] = BACKGROUND_COLOR


def load_xau() -> pd.DataFrame:
    frame = pd.read_csv(XAU_PATH)
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.rename(columns={"close": "xau_close"})
    return frame[["date", "xau_close"]].sort_values("date").reset_index(drop=True)


def load_inflation_catalog() -> pd.DataFrame:
    store = IndicatorStore(ROOT)
    catalog = store.list_indicators(category=INFLATION_CATEGORY)
    catalog = catalog.loc[catalog["enabled"].astype(str).str.casefold() == "true"].copy()
    catalog = catalog.sort_values(["frequency", "indicator_name"]).reset_index(drop=True)
    return catalog


def load_indicator_data(file_path: str) -> pd.DataFrame:
    frame = pd.read_csv(file_path)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.sort_values("date").reset_index(drop=True)


def plot_one_indicator(xau: pd.DataFrame, row: dict[str, str]) -> Path:
    indicator = load_indicator_data(row["file_path"])
    overlap_start = max(xau["date"].min(), indicator["date"].min())
    overlap_end = min(xau["date"].max(), indicator["date"].max())
    xau_slice = xau.loc[(xau["date"] >= overlap_start) & (xau["date"] <= overlap_end)].copy()
    indicator_slice = indicator.loc[
        (indicator["date"] >= overlap_start) & (indicator["date"] <= overlap_end)
    ].copy()

    fig, ax_left = plt.subplots(figsize=(14.5, 7.8), dpi=220)
    ax_right = ax_left.twinx()

    ax_left.plot(
        xau_slice["date"],
        xau_slice["xau_close"],
        color=GOLD_COLOR,
        linewidth=2.2,
        alpha=0.95,
        zorder=2,
    )

    freq = str(row["frequency"]).lower()
    marker = "o" if freq in {"m", "q"} else None
    marker_size = 3.2 if marker else 0
    ax_right.plot(
        indicator_slice["date"],
        indicator_slice["value"],
        color=INDICATOR_COLOR,
        linewidth=2.0,
        marker=marker,
        markersize=marker_size,
        alpha=0.95,
        zorder=3,
    )

    ax_left.set_title(
        f"{row['indicator_name']} 与 XAU/USD 价格",
        loc="left",
        fontsize=18,
        fontweight="bold",
        color=TITLE_COLOR,
        pad=16,
    )
    ax_left.text(
        0.0,
        1.02,
        f"左轴：XAU/USD 日线收盘价    右轴：{row['indicator_name']}（{str(row['frequency']).upper()}）    区间：{overlap_start.date()} 至 {overlap_end.date()}",
        transform=ax_left.transAxes,
        fontsize=10.5,
        color="#586174",
    )

    ax_left.set_xlabel("日期", fontsize=11.5, color=TITLE_COLOR, labelpad=10)
    ax_left.set_ylabel("XAU/USD 收盘价", fontsize=11.5, color=GOLD_COLOR, labelpad=12)
    ax_right.set_ylabel(row["indicator_name"], fontsize=11.5, color=INDICATOR_COLOR, labelpad=12)

    ax_left.tick_params(axis="y", colors=GOLD_COLOR, labelsize=10.5)
    ax_right.tick_params(axis="y", colors=INDICATOR_COLOR, labelsize=10.5)
    ax_left.tick_params(axis="x", labelsize=10.5, colors=TITLE_COLOR)

    ax_left.grid(axis="y", color=GRID_COLOR, linewidth=0.8, alpha=0.75)
    ax_left.grid(axis="x", color=GRID_COLOR, linewidth=0.5, alpha=0.25)
    ax_left.set_axisbelow(True)

    for axis in (ax_left, ax_right):
        axis.spines["top"].set_visible(False)
        for side in ("left", "right", "bottom"):
            axis.spines[side].set_color(SPINE_COLOR)
            axis.spines[side].set_linewidth(0.8)

    ax_left.xaxis.set_major_locator(mdates.YearLocator(base=2))
    ax_left.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax_left.xaxis.set_minor_locator(mdates.YearLocator())
    ax_left.margins(x=0.01)

    handles = [
        Line2D([0], [0], color=GOLD_COLOR, linewidth=2.2, label="XAU/USD 日线收盘价"),
        Line2D([0], [0], color=INDICATOR_COLOR, linewidth=2.0, marker=marker, markersize=4.0, label=row["indicator_name"]),
    ]
    ax_left.legend(
        handles=handles,
        loc="upper left",
        frameon=False,
        fontsize=10.5,
        ncol=2,
        bbox_to_anchor=(0.0, 0.965),
    )

    definition = str(row.get("definition", "") or "")
    if definition:
        ax_left.text(
            0.0,
            -0.16,
            f"指标说明：{definition}",
            transform=ax_left.transAxes,
            fontsize=9.6,
            color="#6B7280",
            wrap=True,
        )

    fig.tight_layout(rect=(0, 0.04, 1, 1))

    output_path = OUTPUT_DIR / f"{row['indicator_name']}_vs_XAU_USD.png"
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return output_path


def write_index(catalog: pd.DataFrame, output_paths: list[Path]) -> None:
    lines = [
        "# 通胀指标与 XAU/USD 双轴图",
        "",
        f"输出目录：`{OUTPUT_DIR}`",
        "",
        "| 指标名称 | 频率 | 图片文件 |",
        "| --- | --- | --- |",
    ]
    for row, path in zip(catalog.to_dict(orient="records"), output_paths):
        lines.append(f"| {row['indicator_name']} | {str(row['frequency']).upper()} | {path.name} |")
    lines.append("")
    (OUTPUT_DIR / "index.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    configure_matplotlib()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    xau = load_xau()
    catalog = load_inflation_catalog()

    output_paths: list[Path] = []
    for row in catalog.to_dict(orient="records"):
        output_paths.append(plot_one_indicator(xau, row))

    write_index(catalog, output_paths)
    print(f"Wrote {len(output_paths)} charts to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
