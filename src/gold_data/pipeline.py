from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
import logging

import pandas as pd

from .catalog import refresh_indicator_directory
from .config import IndicatorConfig, build_catalog_rows, indicator_path, load_indicators
from .derived import DerivedSeriesBuilder
from .fred import FredClient
from .storage import merge_series_frames, read_series_csv, write_catalog_csv, write_series_csv

LOGGER = logging.getLogger(__name__)


@dataclass
class RunResult:
    errors: list[str]

    @property
    def success(self) -> bool:
        return not self.errors


class DataPipeline:
    def __init__(
        self,
        base_dir: Path,
        config_path: Path,
        env_path: Path,
        client: FredClient | None,
        today: date | None = None,
    ) -> None:
        self.base_dir = base_dir
        self.config_path = config_path
        self.env_path = env_path
        self.client = client
        self.today = today or date.today()
        self.indicators = load_indicators(config_path)
        self.indicators_by_name = {item.indicator_name: item for item in self.indicators}
        self.series_meta: dict[str, dict[str, Any]] = {}
        self.derived_builder = DerivedSeriesBuilder()

    def run(self, command: str) -> RunResult:
        errors: list[str] = []
        enabled = [item for item in self.indicators if item.enabled]
        direct = [item for item in enabled if item.series_type == "direct"] if command != "derive" else []
        derived = [item for item in enabled if item.series_type == "derived"]

        for indicator in direct:
            try:
                self._process_direct(indicator, command)
            except Exception as exc:  # pragma: no cover - exercised via tests
                message = f"{indicator.indicator_name}: {exc}"
                LOGGER.exception("Failed to process indicator %s", indicator.indicator_name)
                errors.append(message)

        for indicator in derived:
            try:
                self._process_derived(indicator)
            except Exception as exc:
                message = f"{indicator.indicator_name}: {exc}"
                LOGGER.exception("Failed to build derived indicator %s", indicator.indicator_name)
                errors.append(message)

        catalog_rows = build_catalog_rows(self.indicators, self.base_dir, self.series_meta)
        write_catalog_csv(self.base_dir / "data" / "fred" / "_catalog.csv", catalog_rows)
        refresh_indicator_directory(self.base_dir, self.config_path)
        return RunResult(errors=errors)

    def _process_direct(self, indicator: IndicatorConfig, command: str) -> None:
        if self.client is None:
            raise RuntimeError("FRED client is not configured for direct series processing")
        path = indicator_path(self.base_dir, indicator)
        existing = read_series_csv(path)
        start_date = indicator.start_date if command == "init" else self._resolve_update_start(indicator, existing)
        metadata = self.client.fetch_series_metadata(indicator.series_id)
        self.series_meta[indicator.series_id] = metadata
        incoming = self.client.fetch_observations(
            indicator.series_id,
            observation_start=start_date,
            observation_end=self.today.isoformat(),
        )
        merged = incoming if command == "init" else merge_series_frames(existing, incoming)
        write_series_csv(path, merged)
        LOGGER.info("Wrote %s rows to %s", len(merged), path)

    def _process_derived(self, indicator: IndicatorConfig) -> None:
        dependencies = self.derived_builder.load_dependency_frames(
            base_dir=self.base_dir,
            indicator=indicator,
            indicators_by_name=self.indicators_by_name,
        )
        output = self.derived_builder.build(indicator=indicator, dependencies=dependencies)
        write_series_csv(indicator_path(self.base_dir, indicator), output)

    def _resolve_update_start(self, indicator: IndicatorConfig, existing: pd.DataFrame) -> str:
        if existing.empty:
            return indicator.start_date

        last_date = datetime.strptime(str(existing["date"].iloc[-1]), "%Y-%m-%d").date()
        candidate = last_date - timedelta(days=indicator.update_window_days)
        floor = datetime.strptime(indicator.start_date, "%Y-%m-%d").date()
        return max(candidate, floor).isoformat()


def load_api_key(env_path: Path) -> str:
    if not env_path.exists():
        raise RuntimeError(f"Missing env file: {env_path}")

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == "FRED_API_KEY":
            result = value.strip()
            if result:
                return result
            break

    raise RuntimeError("FRED_API_KEY is missing from .env")


def build_pipeline(
    base_dir: Path,
    config_path: Path | None = None,
    env_path: Path | None = None,
    today: date | None = None,
) -> DataPipeline:
    env_file = env_path or (base_dir / ".env")
    api_key = load_api_key(env_file)
    return DataPipeline(
        base_dir=base_dir,
        config_path=config_path or (base_dir / "config" / "indicators.yml"),
        env_path=env_file,
        client=FredClient(api_key=api_key),
        today=today,
    )


def build_local_pipeline(
    base_dir: Path,
    config_path: Path | None = None,
    env_path: Path | None = None,
    today: date | None = None,
) -> DataPipeline:
    return DataPipeline(
        base_dir=base_dir,
        config_path=config_path or (base_dir / "config" / "indicators.yml"),
        env_path=env_path or (base_dir / ".env"),
        client=None,
        today=today,
    )
