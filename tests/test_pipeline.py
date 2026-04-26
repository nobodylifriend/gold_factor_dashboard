from __future__ import annotations

from datetime import date
from pathlib import Path
import unittest
import shutil
import uuid

import pandas as pd

from src.gold_data.config import load_indicators
from src.gold_data.pipeline import DataPipeline, build_local_pipeline, load_api_key


class FakeFredClient:
    def __init__(self, observations=None, metadata=None, failures=None):
        self.observations = observations or {}
        self.metadata = metadata or {}
        self.failures = failures or set()

    def fetch_observations(self, series_id: str, observation_start: str, observation_end: str | None = None):
        if series_id in self.failures:
            raise RuntimeError(f"boom-{series_id}")
        rows = self.observations.get(series_id, [])
        filtered = [row for row in rows if row["date"] >= observation_start]
        frame = pd.DataFrame(filtered, columns=["date", "value"])
        return frame

    def fetch_series_metadata(self, series_id: str):
        return self.metadata.get(series_id, {"frequency_short": "", "units_short": ""})


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class WorkspaceTempDir:
    def __enter__(self) -> str:
        root = Path(__file__).resolve().parents[1] / ".tmp_tests"
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / str(uuid.uuid4())
        self.path.mkdir(parents=True, exist_ok=True)
        return str(self.path)

    def __exit__(self, exc_type, exc, tb) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class PipelineTests(unittest.TestCase):
    def test_indicator_validation_rejects_duplicate_output_path(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            config = base / "config" / "indicators.yml"
            write_file(
                config,
                """
indicators:
  - category: 通胀 / 通胀预期
    indicator_name: CPI
    source: fred
    series_id: CPIAUCSL
    series_type: direct
    frequency: m
    start_date: "2020-01-01"
    enabled: true
    status: active
    update_window_days: 540
  - category: 通胀 _ 通胀预期
    indicator_name: CPI
    source: fred
    series_id: CPIX
    series_type: direct
    frequency: m
    start_date: "2020-01-01"
    enabled: true
    status: active
    update_window_days: 540
""".strip(),
            )
            with self.assertRaises(ValueError):
                load_indicators(config)

    def test_init_writes_catalog_and_series_csvs(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            write_file(base / ".env", "FRED_API_KEY=test-key\n")
            config_path = base / "config" / "indicators.yml"
            write_file(
                config_path,
                """
indicators:
  - category: 通胀 / 通胀预期
    indicator_name: 10年期美债收益率
    source: fred
    series_id: DGS10
    series_type: direct
    frequency: d
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 30
  - category: 真实利率
    indicator_name: 10年期TIPS实际收益率
    source: fred
    series_id: DFII10
    series_type: direct
    frequency: d
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 30
  - category: 通胀 / 通胀预期
    indicator_name: 10年期通胀预期_名义减实际
    source: fred
    series_type: derived
    frequency: d
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 30
    formula: DGS10 - DFII10
    dependencies:
      - 10年期美债收益率
      - 10年期TIPS实际收益率
""".strip(),
            )
            client = FakeFredClient(
                observations={
                    "DGS10": [
                        {"date": "2024-01-01", "value": 4.0},
                        {"date": "2024-01-02", "value": 4.1},
                    ],
                    "DFII10": [
                        {"date": "2024-01-01", "value": 1.8},
                        {"date": "2024-01-02", "value": 1.9},
                    ],
                },
                metadata={
                    "DGS10": {"frequency_short": "D", "units_short": "Percent"},
                    "DFII10": {"frequency_short": "D", "units_short": "Percent"},
                },
            )
            pipeline = DataPipeline(
                base_dir=base,
                config_path=config_path,
                env_path=base / ".env",
                client=client,
                today=date(2024, 1, 2),
            )
            result = pipeline.run("init")
            self.assertTrue(result.success)

            direct_path = base / "data" / "fred" / "通胀_通胀预期" / "10年期美债收益率.csv"
            derived_path = base / "data" / "fred" / "通胀_通胀预期" / "10年期通胀预期_名义减实际.csv"
            catalog_path = base / "data" / "fred" / "_catalog.csv"

            self.assertTrue(direct_path.exists())
            self.assertTrue(derived_path.exists())
            self.assertTrue(catalog_path.exists())

            derived = pd.read_csv(derived_path)
            self.assertEqual(list(derived.columns), ["date", "value"])
            self.assertEqual(derived["value"].round(2).tolist(), [2.2, 2.2])

    def test_update_is_idempotent_and_backfills_window(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            write_file(base / ".env", "FRED_API_KEY=test-key\n")
            config_path = base / "config" / "indicators.yml"
            write_file(
                config_path,
                """
indicators:
  - category: 名义利率
    indicator_name: 10年期美债收益率
    source: fred
    series_id: DGS10
    series_type: direct
    frequency: d
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 30
""".strip(),
            )
            output_path = base / "data" / "fred" / "名义利率" / "10年期美债收益率.csv"
            write_file(output_path, "date,value\n2024-01-01,4.0\n2024-01-02,4.1\n")
            client = FakeFredClient(
                observations={
                    "DGS10": [
                        {"date": "2024-01-01", "value": 4.0},
                        {"date": "2024-01-02", "value": 4.1},
                        {"date": "2024-01-03", "value": 4.2},
                        {"date": "2024-01-03", "value": 4.2},
                    ],
                }
            )
            pipeline = DataPipeline(
                base_dir=base,
                config_path=config_path,
                env_path=base / ".env",
                client=client,
                today=date(2024, 1, 3),
            )

            first = pipeline.run("update")
            second = pipeline.run("update")
            self.assertTrue(first.success)
            self.assertTrue(second.success)

            frame = pd.read_csv(output_path)
            self.assertEqual(frame["date"].tolist(), ["2024-01-01", "2024-01-02", "2024-01-03"])
            self.assertEqual(frame["value"].tolist(), [4.0, 4.1, 4.2])

    def test_pct_change_derived_indicators_are_computed_for_monthly_and_quarterly_series(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            write_file(base / ".env", "FRED_API_KEY=test-key\n")
            config_path = base / "config" / "indicators.yml"
            write_file(
                config_path,
                """
indicators:
  - category: 通胀 / 通胀预期
    indicator_name: CPI
    source: fred
    series_id: CPIAUCSL
    series_type: direct
    frequency: m
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 540
  - category: 通胀 / 通胀预期
    indicator_name: CPI_同比
    indicator_id: CPIAUCSL_YOY
    english_code: CPIAUCSL_YOY
    source: fred
    series_type: derived
    derivation_method: pct_change
    frequency: m
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 540
    dependencies:
      - CPI
    transform_params:
      periods: 12
      annualize: false
  - category: 通胀 / 通胀预期
    indicator_name: CPI_环比
    indicator_id: CPIAUCSL_MOM
    english_code: CPIAUCSL_MOM
    source: fred
    series_type: derived
    derivation_method: pct_change
    frequency: m
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 540
    dependencies:
      - CPI
    transform_params:
      periods: 1
      annualize: false
  - category: 通胀 / 通胀预期
    indicator_name: CPI_环比年化
    indicator_id: CPIAUCSL_MOM_ANNUALIZED
    english_code: CPIAUCSL_MOM_ANNUALIZED
    source: fred
    series_type: derived
    derivation_method: pct_change
    frequency: m
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 540
    dependencies:
      - CPI
    transform_params:
      periods: 1
      annualize: true
  - category: 通胀 / 通胀预期
    indicator_name: GDP平减指数
    source: fred
    series_id: GDPDEF
    series_type: direct
    frequency: q
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 720
  - category: 通胀 / 通胀预期
    indicator_name: GDP平减指数_环比年化
    indicator_id: GDPDEF_QOQ_ANNUALIZED
    english_code: GDPDEF_QOQ_ANNUALIZED
    source: fred
    series_type: derived
    derivation_method: pct_change
    frequency: q
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 720
    dependencies:
      - GDP平减指数
    transform_params:
      periods: 1
      annualize: true
""".strip(),
            )
            client = FakeFredClient(
                observations={
                    "CPIAUCSL": [
                        {"date": "2024-01-01", "value": 100.0},
                        {"date": "2024-02-01", "value": 101.0},
                        {"date": "2024-03-01", "value": 102.0},
                        {"date": "2024-04-01", "value": 103.0},
                        {"date": "2024-05-01", "value": 104.0},
                        {"date": "2024-06-01", "value": 105.0},
                        {"date": "2024-07-01", "value": 106.0},
                        {"date": "2024-08-01", "value": 107.0},
                        {"date": "2024-09-01", "value": 108.0},
                        {"date": "2024-10-01", "value": 109.0},
                        {"date": "2024-11-01", "value": 110.0},
                        {"date": "2024-12-01", "value": 111.0},
                        {"date": "2025-01-01", "value": 112.0},
                    ],
                    "GDPDEF": [
                        {"date": "2024-01-01", "value": 100.0},
                        {"date": "2024-04-01", "value": 101.0},
                    ],
                }
            )
            pipeline = DataPipeline(
                base_dir=base,
                config_path=config_path,
                env_path=base / ".env",
                client=client,
                today=date(2025, 1, 1),
            )

            result = pipeline.run("init")
            self.assertTrue(result.success)

            cpi_yoy = pd.read_csv(base / "data" / "fred" / "通胀_通胀预期" / "CPI_同比.csv")
            cpi_mom = pd.read_csv(base / "data" / "fred" / "通胀_通胀预期" / "CPI_环比.csv")
            cpi_mom_annualized = pd.read_csv(base / "data" / "fred" / "通胀_通胀预期" / "CPI_环比年化.csv")
            gdp_qoq_annualized = pd.read_csv(base / "data" / "fred" / "通胀_通胀预期" / "GDP平减指数_环比年化.csv")

            self.assertAlmostEqual(cpi_yoy["value"].iloc[0], 12.0, places=6)
            self.assertAlmostEqual(cpi_mom["value"].iloc[0], 1.0, places=6)
            self.assertAlmostEqual(
                cpi_mom_annualized["value"].iloc[-1],
                ((112.0 / 111.0) ** 12 - 1.0) * 100.0,
                places=6,
            )
            self.assertAlmostEqual(
                gdp_qoq_annualized["value"].iloc[0],
                ((101.0 / 100.0) ** 4 - 1.0) * 100.0,
                places=6,
            )

    def test_derive_command_rebuilds_derived_from_existing_local_data(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            config_path = base / "config" / "indicators.yml"
            write_file(
                config_path,
                """
indicators:
  - category: 通胀 / 通胀预期
    indicator_name: CPI
    source: fred
    series_id: CPIAUCSL
    series_type: direct
    frequency: m
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 540
  - category: 通胀 / 通胀预期
    indicator_name: CPI_环比
    indicator_id: CPIAUCSL_MOM
    english_code: CPIAUCSL_MOM
    source: fred
    series_type: derived
    derivation_method: pct_change
    frequency: m
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 540
    dependencies:
      - CPI
    transform_params:
      periods: 1
      annualize: false
""".strip(),
            )
            write_file(
                base / "data" / "fred" / "通胀_通胀预期" / "CPI.csv",
                "date,value\n2024-01-01,100\n2024-02-01,102\n",
            )

            pipeline = build_local_pipeline(base_dir=base, config_path=config_path)
            result = pipeline.run("derive")
            self.assertTrue(result.success)

            derived = pd.read_csv(base / "data" / "fred" / "通胀_通胀预期" / "CPI_环比.csv")
            self.assertEqual(derived["date"].tolist(), ["2024-02-01"])
            self.assertAlmostEqual(derived["value"].iloc[0], 2.0, places=6)

    def test_missing_env_key_raises(self) -> None:
        with WorkspaceTempDir() as tmp:
            env_path = Path(tmp) / ".env"
            write_file(env_path, "OTHER_KEY=value\n")
            with self.assertRaisesRegex(RuntimeError, "FRED_API_KEY"):
                load_api_key(env_path)

    def test_series_failure_is_reported_but_other_series_continue(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            write_file(base / ".env", "FRED_API_KEY=test-key\n")
            config_path = base / "config" / "indicators.yml"
            write_file(
                config_path,
                """
indicators:
  - category: 名义利率
    indicator_name: 联邦基金利率
    source: fred
    series_id: FEDFUNDS
    series_type: direct
    frequency: m
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 540
  - category: 名义利率
    indicator_name: 10年期美债收益率
    source: fred
    series_id: DGS10
    series_type: direct
    frequency: d
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 30
""".strip(),
            )
            client = FakeFredClient(
                observations={
                    "FEDFUNDS": [{"date": "2024-01-01", "value": 5.0}],
                },
                failures={"DGS10"},
            )
            pipeline = DataPipeline(
                base_dir=base,
                config_path=config_path,
                env_path=base / ".env",
                client=client,
                today=date(2024, 1, 2),
            )

            result = pipeline.run("init")
            self.assertFalse(result.success)
            self.assertEqual(len(result.errors), 1)
            self.assertTrue((base / "data" / "fred" / "名义利率" / "联邦基金利率.csv").exists())


if __name__ == "__main__":
    unittest.main()
