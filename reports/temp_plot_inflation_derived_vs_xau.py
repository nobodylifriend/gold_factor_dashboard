from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from plot_dual_axis import plot_dual_axis_by_ids


XAU_INDICATOR_ID = "XAU_USD_DAILY_OHLC"
OUTPUT_DIR = ROOT / "reports" / "figures" / "inflation_derived_vs_xau"
START_DATE = "2006-04-25"
END_DATE = None

DERIVED_INDICATOR_IDS = (
    "CPIAUCSL_YOY",
    "CPIAUCSL_MOM",
    "CPIAUCSL_MOM_ANNUALIZED",
    "CPILFESL_YOY",
    "CPILFESL_MOM",
    "CPILFESL_MOM_ANNUALIZED",
    "PCEPI_YOY",
    "PCEPI_MOM",
    "PCEPI_MOM_ANNUALIZED",
    "PCEPILFE_YOY",
    "PCEPILFE_MOM",
    "PCEPILFE_MOM_ANNUALIZED",
    "PPIACO_YOY",
    "PPIACO_MOM",
    "PPIACO_MOM_ANNUALIZED",
    "GDPDEF_YOY",
    "GDPDEF_QOQ",
    "GDPDEF_QOQ_ANNUALIZED",
)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_paths: list[Path] = []
    for indicator_id in DERIVED_INDICATOR_IDS:
        output_path = OUTPUT_DIR / f"{XAU_INDICATOR_ID}_vs_{indicator_id}.png"
        plot_dual_axis_by_ids(
            left_indicator_id=XAU_INDICATOR_ID,
            right_indicator_id=indicator_id,
            start_date=START_DATE,
            end_date=END_DATE,
            output=str(output_path),
            base_dir=ROOT,
        )
        output_paths.append(output_path)

    index_lines = [
        "# Inflation Derived Indicators vs XAU/USD",
        "",
        f"Output directory: `{OUTPUT_DIR}`",
        "",
        "| Indicator ID | Output File |",
        "| --- | --- |",
    ]
    for indicator_id, output_path in zip(DERIVED_INDICATOR_IDS, output_paths):
        index_lines.append(f"| {indicator_id} | {output_path.name} |")
    index_lines.append("")
    (OUTPUT_DIR / "index.md").write_text("\n".join(index_lines), encoding="utf-8")

    print(f"Wrote {len(output_paths)} charts to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
