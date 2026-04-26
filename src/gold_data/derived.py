from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from .config import IndicatorConfig, indicator_path
from .storage import normalize_series_frame, read_series_csv

ANNUALIZATION_FACTORS = {
    "d": 252,
    "w": 52,
    "m": 12,
    "q": 4,
}


class DerivedTransform(ABC):
    @abstractmethod
    def build(self, indicator: IndicatorConfig, dependencies: dict[str, pd.DataFrame]) -> pd.DataFrame:
        raise NotImplementedError


class ExpressionTransform(DerivedTransform):
    def build(self, indicator: IndicatorConfig, dependencies: dict[str, pd.DataFrame]) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for dependency in indicator.dependencies:
            dependency_indicator = dependencies[dependency]
            column_name = str(dependency_indicator.attrs.get("column_name") or dependency)
            frames.append(dependency_indicator.rename(columns={"value": column_name}))

        merged = frames[0]
        for frame in frames[1:]:
            merged = merged.merge(frame, on="date", how="inner")

        merged = merged.sort_values("date").reset_index(drop=True)
        merged["value"] = merged.eval(indicator.formula)
        return normalize_series_frame(merged[["date", "value"]])


class PercentChangeTransform(DerivedTransform):
    def build(self, indicator: IndicatorConfig, dependencies: dict[str, pd.DataFrame]) -> pd.DataFrame:
        dependency_name = indicator.dependencies[0]
        frame = dependencies[dependency_name].copy()
        periods = int(indicator.transform_params["periods"])
        annualize = bool(indicator.transform_params.get("annualize", False))
        frequency = str(
            indicator.transform_params.get("base_frequency") or frame.attrs.get("frequency") or indicator.frequency
        ).casefold()

        frame = frame.sort_values("date").reset_index(drop=True)
        ratio = frame["value"] / frame["value"].shift(periods)
        if annualize:
            factor = indicator.transform_params.get("annualization_factor") or ANNUALIZATION_FACTORS.get(frequency)
            if factor is None:
                raise ValueError(f"Unsupported frequency for annualization: {frequency}")
            values = (ratio.pow(factor / periods) - 1.0) * 100.0
        else:
            values = (ratio - 1.0) * 100.0
        output = pd.DataFrame({"date": frame["date"], "value": values})
        return normalize_series_frame(output)


class DerivedSeriesBuilder:
    def __init__(self) -> None:
        self.transforms: dict[str, DerivedTransform] = {
            "expression": ExpressionTransform(),
            "pct_change": PercentChangeTransform(),
        }

    def load_dependency_frames(
        self,
        base_dir: Path,
        indicator: IndicatorConfig,
        indicators_by_name: dict[str, IndicatorConfig],
    ) -> dict[str, pd.DataFrame]:
        frames: dict[str, pd.DataFrame] = {}
        for dependency_name in indicator.dependencies:
            dependency = indicators_by_name[dependency_name]
            dep_path = indicator_path(base_dir, dependency)
            dep_frame = read_series_csv(dep_path)
            if dep_frame.empty:
                raise RuntimeError(f"Dependency has no data: {dependency_name}")
            column_name = dependency.series_id or dependency.indicator_name
            dep_frame.attrs["column_name"] = column_name
            dep_frame.attrs["frequency"] = dependency.frequency
            frames[dependency_name] = dep_frame
        return frames

    def build(
        self,
        indicator: IndicatorConfig,
        dependencies: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        method = indicator.derivation_method or "expression"
        transform = self.transforms.get(method)
        if transform is None:
            raise ValueError(f"Unsupported derivation_method: {method}")

        return transform.build(indicator, dependencies)
