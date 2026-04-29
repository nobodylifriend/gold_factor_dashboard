from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from .config import IndicatorConfig, indicator_path, load_indicators
from .metadata import (
    FX_INDICATORS,
    INDICATOR_DEFINITIONS,
    STOCK_VOLATILITY_INDICATORS,
    US_DEBT_INDICATORS,
    XAU_INDICATORS,
)

CATALOG_COLUMNS = [
    "indicator_id",
    "category",
    "indicator_name",
    "chinese_name",
    "english_code",
    "source",
    "frequency",
    "file_path",
    "definition",
    "status",
    "enabled",
]


def build_indicator_directory(base_dir: Path, config_path: Path | None = None) -> pd.DataFrame:
    config_file = config_path or (base_dir / "config" / "indicators.yml")
    indicators = load_indicators(config_file)
    fred_catalog = _read_csv_if_exists(base_dir / "data" / "fred" / "_catalog.csv")
    xau_manifest = _read_manifest(base_dir / "data" / "xau" / "manifest.json")
    fx_manifest = _read_manifest(base_dir / "data" / "fx" / "manifest.json")
    stock_volatility_manifest = _read_manifest(base_dir / "data" / "stock_volatility" / "manifest.json")
    us_debt_manifest = _read_manifest(base_dir / "data" / "us_debt" / "manifest.json")

    rows = _build_fred_rows(base_dir, indicators, fred_catalog)
    rows.extend(_build_external_rows(base_dir, "xau", XAU_INDICATORS, xau_manifest))
    rows.extend(_build_external_rows(base_dir, "fx", FX_INDICATORS, fx_manifest))
    rows.extend(
        _build_external_rows(
            base_dir,
            "stock_volatility",
            STOCK_VOLATILITY_INDICATORS,
            stock_volatility_manifest,
        )
    )
    rows.extend(_build_external_rows(base_dir, "us_debt", US_DEBT_INDICATORS, us_debt_manifest))

    frame = pd.DataFrame(rows, columns=CATALOG_COLUMNS)
    if frame.empty:
        return pd.DataFrame(columns=CATALOG_COLUMNS)
    frame = frame.sort_values(["category", "indicator_name"]).reset_index(drop=True)
    return frame


def write_indicator_directory(base_dir: Path, frame: pd.DataFrame) -> None:
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    csv_path = data_dir / "indicator_catalog.csv"
    md_path = data_dir / "indicator_catalog.md"

    ordered = frame.reindex(columns=CATALOG_COLUMNS)
    ordered.to_csv(csv_path, index=False)
    md_path.write_text(render_indicator_directory_markdown(ordered), encoding="utf-8")


def refresh_indicator_directory(base_dir: Path, config_path: Path | None = None) -> pd.DataFrame:
    frame = build_indicator_directory(base_dir=base_dir, config_path=config_path)
    write_indicator_directory(base_dir, frame)
    return frame


def load_indicator_directory(base_dir: Path, config_path: Path | None = None) -> pd.DataFrame:
    csv_path = base_dir / "data" / "indicator_catalog.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path, dtype="string").fillna("")
    frame = build_indicator_directory(base_dir=base_dir, config_path=config_path)
    return frame.fillna("")


def render_indicator_directory_markdown(frame: pd.DataFrame) -> str:
    lines = [
        "# Indicator Directory",
        "",
        "This file is generated from project metadata and local data artifacts.",
        "",
        "| Category | Name | Chinese Name | Indicator ID | English Code | Source | Frequency | File Path | Definition |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in frame.to_dict(orient="records"):
        lines.append(
            "| {category} | {indicator_name} | {chinese_name} | {indicator_id} | {english_code} | {source} | {frequency} | {file_path} | {definition} |".format(
                **{key: _escape_markdown(value) for key, value in row.items()}
            )
        )
    lines.append("")
    return "\n".join(lines)


def _build_fred_rows(
    base_dir: Path,
    indicators: list[IndicatorConfig],
    fred_catalog: pd.DataFrame,
) -> list[dict[str, str]]:
    catalog_by_name = {
        str(row["indicator_name"]): row
        for _, row in fred_catalog.iterrows()
        if str(row.get("indicator_name", ""))
    }
    rows: list[dict[str, str]] = []
    for indicator in indicators:
        catalog_row = catalog_by_name.get(indicator.indicator_name, {})
        rows.append(
            {
                "indicator_id": indicator.resolved_indicator_id,
                "category": indicator.category,
                "indicator_name": indicator.indicator_name,
                "chinese_name": str(catalog_row.get("chinese_name", "")) or indicator.resolved_chinese_name,
                "english_code": indicator.resolved_english_code,
                "source": indicator.source,
                "frequency": str(catalog_row.get("frequency", "")) or indicator.frequency,
                "file_path": str(catalog_row.get("file_path", "")) or str(indicator_path(base_dir, indicator)),
                "definition": _resolve_definition(indicator, catalog_row),
                "status": indicator.status,
                "enabled": str(indicator.enabled),
            }
        )
    return rows


def _build_external_rows(
    base_dir: Path,
    data_dirname: str,
    indicators: tuple[dict[str, str], ...],
    manifest: dict[str, object],
) -> list[dict[str, str]]:
    artifacts = {
        item.get("file_name", ""): item
        for item in manifest.get("artifacts", [])
        if isinstance(item, dict)
    }
    rows: list[dict[str, str]] = []
    for item in indicators:
        artifact = artifacts.get(item["file_name"], {})
        rows.append(
            {
                "indicator_id": item["indicator_id"],
                "category": item["category"],
                "indicator_name": item["indicator_name"],
                "chinese_name": item["chinese_name"],
                "english_code": item["english_code"],
                "source": item["source"],
                "frequency": item["frequency"],
                "file_path": str(base_dir / "data" / data_dirname / item["file_name"]),
                "definition": INDICATOR_DEFINITIONS.get(item["indicator_id"], "") or str(artifact.get("notes", "")),
                "status": "active" if artifact else "missing",
                "enabled": "True",
            }
        )
    return rows


def _resolve_definition(indicator: IndicatorConfig, catalog_row: dict[str, object]) -> str:
    if indicator.description:
        return indicator.description
    key = indicator.resolved_indicator_id
    if key in INDICATOR_DEFINITIONS:
        return INDICATOR_DEFINITIONS[key]
    if indicator.series_id in INDICATOR_DEFINITIONS:
        return INDICATOR_DEFINITIONS[indicator.series_id]
    return str(catalog_row.get("units", "")) or str(catalog_row.get("definition", ""))


def _read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype="string").fillna("")


def _read_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _escape_markdown(value: object) -> str:
    text = str(value or "")
    return text.replace("|", "\\|").replace("\n", " ")
