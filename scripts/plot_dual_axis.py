from __future__ import annotations

import argparse
from dataclasses import dataclass
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


DEFAULT_OUTPUT_DIR = ROOT / "reports" / "figures" / "dual_axis"
LEFT_COLOR = "#C99700"
RIGHT_COLOR = "#2E5BFF"
TITLE_COLOR = "#1F2937"
GRID_COLOR = "#D7DCE5"
SPINE_COLOR = "#C8CED8"
BACKGROUND_COLOR = "#FCFCFD"
METADATA_COLUMNS = {"date", "indicator_id", "category", "indicator_name", "frequency", "source"}


@dataclass(frozen=True)
class IndicatorSeries:
    indicator_id: str
    indicator_name: str
    frequency: str
    source: str
    category: str
    value_column: str
    frame: pd.DataFrame


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plot a dual-axis chart for two indicators.")
    parser.add_argument("--left-id", required=True, help="Indicator ID for the left axis.")
    parser.add_argument("--right-id", required=True, help="Indicator ID for the right axis.")
    parser.add_argument("--start-date", default=None, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", default=None, help="End date in YYYY-MM-DD format.")
    parser.add_argument("--output", default=None, help="Optional output file path.")
    parser.add_argument("--base-dir", default=".", help="Project root directory.")
    return parser


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


def load_indicator_series(
    store: IndicatorStore,
    indicator_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> IndicatorSeries:
    frame = store.get_one(
        indicator_id=indicator_id,
        start_date=start_date,
        end_date=end_date,
        include_metadata=True,
    ).copy()
    if frame.empty:
        raise ValueError(f"No data found for indicator_id={indicator_id}")

    frame["date"] = pd.to_datetime(frame["date"])
    value_column = resolve_value_column(frame)
    frame = frame.sort_values("date").reset_index(drop=True)
    row = frame.iloc[0]
    return IndicatorSeries(
        indicator_id=str(row["indicator_id"]),
        indicator_name=str(row["indicator_name"]),
        frequency=str(row["frequency"]),
        source=str(row["source"]),
        category=str(row["category"]),
        value_column=value_column,
        frame=frame,
    )


def resolve_value_column(frame: pd.DataFrame) -> str:
    if "value" in frame.columns:
        return "value"

    numeric_candidates: list[str] = []
    for column in frame.columns:
        if column in METADATA_COLUMNS:
            continue
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if numeric.notna().any():
            numeric_candidates.append(column)

    if "close" in numeric_candidates:
        return "close"
    if len(numeric_candidates) == 1:
        return numeric_candidates[0]
    if not numeric_candidates:
        raise ValueError("No numeric value column found for plotting")
    raise ValueError(f"Ambiguous numeric columns for plotting: {', '.join(numeric_candidates)}")


def build_output_path(
    left_indicator_id: str,
    right_indicator_id: str,
    output: str | None = None,
) -> Path:
    if output:
        return Path(output).resolve()
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"{left_indicator_id}_vs_{right_indicator_id}.png"
    return DEFAULT_OUTPUT_DIR / file_name


def clip_to_overlap(left: IndicatorSeries, right: IndicatorSeries) -> tuple[pd.DataFrame, pd.DataFrame]:
    overlap_start = max(left.frame["date"].min(), right.frame["date"].min())
    overlap_end = min(left.frame["date"].max(), right.frame["date"].max())
    if overlap_start > overlap_end:
        raise ValueError("The two indicators do not have overlapping dates in the requested range")

    left_frame = left.frame.loc[(left.frame["date"] >= overlap_start) & (left.frame["date"] <= overlap_end)].copy()
    right_frame = right.frame.loc[(right.frame["date"] >= overlap_start) & (right.frame["date"] <= overlap_end)].copy()
    return left_frame, right_frame


def build_legend_label(series: IndicatorSeries) -> str:
    frequency = series.frequency.upper()
    return f"{series.indicator_name} ({frequency})"


def choose_marker(frequency: str) -> str | None:
    return "o" if str(frequency).casefold() in {"m", "q"} else None


def plot_dual_axis_by_ids(
    left_indicator_id: str,
    right_indicator_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    output: str | None = None,
    base_dir: Path | None = None,
) -> Path:
    configure_matplotlib()
    root = (base_dir or ROOT).resolve()
    store = IndicatorStore(root)
    left = load_indicator_series(store, left_indicator_id, start_date=start_date, end_date=end_date)
    right = load_indicator_series(store, right_indicator_id, start_date=start_date, end_date=end_date)
    left_frame, right_frame = clip_to_overlap(left, right)

    output_path = build_output_path(left.indicator_id, right.indicator_id, output=output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax_left = plt.subplots(figsize=(14.5, 7.8), dpi=220)
    ax_right = ax_left.twinx()

    left_marker = choose_marker(left.frequency)
    right_marker = choose_marker(right.frequency)

    ax_left.plot(
        left_frame["date"],
        left_frame[left.value_column],
        color=LEFT_COLOR,
        linewidth=2.2,
        marker=left_marker,
        markersize=3.2 if left_marker else 0.0,
        alpha=0.95,
        zorder=2,
    )
    ax_right.plot(
        right_frame["date"],
        right_frame[right.value_column],
        color=RIGHT_COLOR,
        linewidth=2.0,
        marker=right_marker,
        markersize=3.2 if right_marker else 0.0,
        alpha=0.95,
        zorder=3,
    )

    overlap_start = left_frame["date"].min().date()
    overlap_end = left_frame["date"].max().date()
    ax_left.set_title(
        f"{left.indicator_name} vs {right.indicator_name}",
        loc="left",
        fontsize=18,
        fontweight="bold",
        color=TITLE_COLOR,
        pad=16,
    )
    ax_left.text(
        0.0,
        1.02,
        f"区间: {overlap_start} 至 {overlap_end}   左轴: {build_legend_label(left)}   右轴: {build_legend_label(right)}",
        transform=ax_left.transAxes,
        fontsize=10.5,
        color="#586174",
    )

    ax_left.set_xlabel("日期", fontsize=11.5, color=TITLE_COLOR, labelpad=10)
    ax_left.set_ylabel(left.indicator_name, fontsize=11.5, color=LEFT_COLOR, labelpad=12)
    ax_right.set_ylabel(right.indicator_name, fontsize=11.5, color=RIGHT_COLOR, labelpad=12)

    ax_left.tick_params(axis="y", colors=LEFT_COLOR, labelsize=10.5)
    ax_right.tick_params(axis="y", colors=RIGHT_COLOR, labelsize=10.5)
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
        Line2D(
            [0],
            [0],
            color=LEFT_COLOR,
            linewidth=2.2,
            marker=left_marker,
            markersize=4.0,
            label=build_legend_label(left),
        ),
        Line2D(
            [0],
            [0],
            color=RIGHT_COLOR,
            linewidth=2.0,
            marker=right_marker,
            markersize=4.0,
            label=build_legend_label(right),
        ),
    ]
    ax_left.legend(
        handles=handles,
        loc="upper left",
        frameon=False,
        fontsize=10.5,
        ncol=2,
        bbox_to_anchor=(0.0, 0.965),
    )

    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output_path = plot_dual_axis_by_ids(
        left_indicator_id=args.left_id,
        right_indicator_id=args.right_id,
        start_date=args.start_date,
        end_date=args.end_date,
        output=args.output,
        base_dir=Path(args.base_dir),
    )
    print(f"Wrote chart to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
