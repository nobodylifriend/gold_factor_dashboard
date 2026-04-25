from __future__ import annotations

from pathlib import Path
import json
import shutil
import unittest
import uuid

from src.gold_data.access import IndicatorStore
from src.gold_data.catalog import refresh_indicator_directory


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


class IndicatorAccessTests(unittest.TestCase):
    def test_refresh_indicator_directory_writes_csv_and_markdown(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            write_file(
                base / "config" / "indicators.yml",
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
            write_file(
                base / "data" / "fred" / "_catalog.csv",
                "category,indicator_name,source,series_id,frequency,units,enabled,status,file_path\n"
                "名义利率,10年期美债收益率,fred,DGS10,D,Percent,True,active,"
                f"{(base / 'data' / 'fred' / '名义利率' / '10年期美债收益率.csv')}\n"
                "真实利率,10年期TIPS实际收益率,fred,DFII10,D,Percent,True,active,"
                f"{(base / 'data' / 'fred' / '真实利率' / '10年期TIPS实际收益率.csv')}\n",
            )
            write_file(base / "data" / "fred" / "名义利率" / "10年期美债收益率.csv", "date,value\n2024-01-01,4.0\n")
            write_file(base / "data" / "fred" / "真实利率" / "10年期TIPS实际收益率.csv", "date,value\n2024-01-01,2.0\n")
            write_file(
                base / "data" / "xau" / "manifest.json",
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "name": "xau_usd_daily_ohlc",
                                "file_name": "xau_usd_daily_ohlc.csv",
                                "notes": "Daily gold price series.",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
            )
            write_file(
                base / "data" / "xau" / "xau_usd_daily_ohlc.csv",
                "date,open,high,low,close,volume,source\n2024-01-01,2000,2010,1995,2005,0,test\n",
            )

            frame = refresh_indicator_directory(base)

            self.assertTrue((base / "data" / "indicator_catalog.csv").exists())
            self.assertTrue((base / "data" / "indicator_catalog.md").exists())
            self.assertIn("DGS10", frame["indicator_id"].tolist())
            self.assertIn("XAU_USD_DAILY_OHLC", frame["indicator_id"].tolist())

    def test_indicator_store_filters_by_id_name_frequency_and_date_range(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            write_file(
                base / "data" / "indicator_catalog.csv",
                "indicator_id,category,indicator_name,english_code,source,frequency,file_path,definition,status,enabled\n"
                f"DGS10,名义利率,10年期美债收益率,DGS10,fred,d,{(base / 'data' / 'fred' / '名义利率' / '10年期美债收益率.csv')},desc,active,True\n"
                f"XAU_USD_DAILY_OHLC,黄金价格,XAU/USD日线OHLC,XAU_USD_DAILY_OHLC,huggingface+investing,d,{(base / 'data' / 'xau' / 'xau_usd_daily_ohlc.csv')},desc,active,True\n",
            )
            write_file(
                base / "data" / "fred" / "名义利率" / "10年期美债收益率.csv",
                "date,value\n2024-01-01,4.0\n2024-01-02,4.1\n2024-01-03,4.2\n",
            )
            write_file(
                base / "data" / "xau" / "xau_usd_daily_ohlc.csv",
                "date,open,high,low,close,volume,source\n"
                "2024-01-01,2000,2010,1990,2005,0,test\n"
                "2024-01-02,2005,2015,1998,2012,0,test\n",
            )

            store = IndicatorStore(base)

            dgs10 = store.get_one(indicator_id="DGS10", start_date="2024-01-02", end_date="2024-01-03")
            self.assertEqual(dgs10["date"].tolist(), ["2024-01-02", "2024-01-03"])
            self.assertEqual(dgs10["value"].tolist(), [4.1, 4.2])

            xau = store.get_one(name="XAU/USD", frequency="d", start_date="2024-01-02")
            self.assertEqual(xau["date"].tolist(), ["2024-01-02"])
            self.assertEqual(xau["close"].tolist(), [2012])


if __name__ == "__main__":
    unittest.main()
