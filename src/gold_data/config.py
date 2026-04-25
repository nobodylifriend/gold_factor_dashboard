from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re

import yaml

INVALID_PATH_CHARS = re.compile(r'[\\/:*?"<>|]+')


@dataclass(frozen=True)
class IndicatorConfig:
    category: str
    indicator_name: str
    source: str
    series_type: str
    frequency: str
    start_date: str
    enabled: bool
    status: str
    update_window_days: int
    series_id: str = ""
    formula: str = ""
    dependencies: tuple[str, ...] = ()

    @property
    def category_dirname(self) -> str:
        return sanitize_component(self.category.replace("/", "_"))

    @property
    def file_stem(self) -> str:
        return sanitize_component(self.indicator_name)


def sanitize_component(value: str) -> str:
    sanitized = INVALID_PATH_CHARS.sub("_", value).strip()
    sanitized = re.sub(r"\s+", " ", sanitized)
    sanitized = re.sub(r"\s*_\s*", "_", sanitized)
    sanitized = re.sub(r"_+", "_", sanitized)
    return sanitized.rstrip(".")


def load_indicators(path: Path) -> list[IndicatorConfig]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_items = payload.get("indicators", [])
    indicators = [IndicatorConfig(**item) for item in raw_items]
    validate_indicators(indicators)
    return indicators


def validate_indicators(indicators: list[IndicatorConfig]) -> None:
    output_paths: dict[tuple[str, str], IndicatorConfig] = {}
    names: dict[str, IndicatorConfig] = {}

    for indicator in indicators:
        key = (indicator.category_dirname, indicator.file_stem)
        if key in output_paths:
            other = output_paths[key]
            raise ValueError(
                f"Duplicate output path for '{indicator.indicator_name}' and '{other.indicator_name}'"
            )
        output_paths[key] = indicator

        if indicator.indicator_name in names:
            raise ValueError(f"Duplicate indicator_name: {indicator.indicator_name}")
        names[indicator.indicator_name] = indicator

        if indicator.series_type == "direct" and not indicator.series_id:
            raise ValueError(f"Direct indicator missing series_id: {indicator.indicator_name}")

        if indicator.series_type == "derived":
            if not indicator.dependencies:
                raise ValueError(f"Derived indicator missing dependencies: {indicator.indicator_name}")
            if not indicator.formula:
                raise ValueError(f"Derived indicator missing formula: {indicator.indicator_name}")

    for indicator in indicators:
        if indicator.series_type != "derived":
            continue
        for dependency in indicator.dependencies:
            if dependency not in names:
                raise ValueError(
                    f"Derived indicator '{indicator.indicator_name}' references unknown dependency '{dependency}'"
                )


def indicator_path(base_dir: Path, indicator: IndicatorConfig) -> Path:
    return base_dir / "data" / "fred" / indicator.category_dirname / f"{indicator.file_stem}.csv"


def build_catalog_rows(
    indicators: list[IndicatorConfig],
    base_dir: Path,
    series_meta: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for indicator in indicators:
        meta = series_meta.get(indicator.series_id, {})
        rows.append(
            {
                "category": indicator.category,
                "indicator_name": indicator.indicator_name,
                "source": indicator.source,
                "series_id": indicator.series_id,
                "frequency": meta.get("frequency_short") or indicator.frequency,
                "units": meta.get("units_short") or meta.get("units") or "",
                "enabled": indicator.enabled,
                "status": indicator.status,
                "file_path": str(indicator_path(base_dir, indicator)),
            }
        )
    return rows
