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
                            },
                            {
                                "name": "GVZ",
                                "file_name": "GVZ.csv",
                                "notes": "Gold volatility index series.",
                            },
                            {
                                "name": "GLOBAL_GOLD_ETF_HOLDINGS_MONTHLY",
                                "file_name": "global_gold_etf_holdings_monthly.csv",
                                "notes": "Monthly global gold ETF holdings.",
                            },
                            {
                                "name": "GLD_TOTAL_HOLDINGS_TONNES",
                                "file_name": "GLD_total_holdings_tonnes.csv",
                                "notes": "Daily GLD holdings in tonnes.",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
            )
            write_file(
                base / "data" / "xau" / "xau_usd_daily_ohlc.csv",
                "date,open,high,low,close,volume,source\n2024-01-01,2000,2010,1995,2005,0,test\n",
            )
            write_file(
                base / "data" / "xau" / "GVZ.csv",
                "date,value,source\n2024-01-01,18.5,test\n",
            )
            write_file(
                base / "data" / "xau" / "global_gold_etf_holdings_monthly.csv",
                "date,value,source\n2024-01-31,2500.0,test\n",
            )
            write_file(
                base / "data" / "xau" / "GLD_total_holdings_tonnes.csv",
                "date,value,source\n2024-01-01,850.0,test\n",
            )

            frame = refresh_indicator_directory(base)

            self.assertTrue((base / "data" / "indicator_catalog.csv").exists())
            self.assertTrue((base / "data" / "indicator_catalog.md").exists())
            self.assertIn("DGS10", frame["indicator_id"].tolist())
            self.assertIn("XAU_USD_DAILY_OHLC", frame["indicator_id"].tolist())
            self.assertIn("GVZ", frame["indicator_id"].tolist())
            self.assertIn("GLOBAL_GOLD_ETF_HOLDINGS_MONTHLY", frame["indicator_id"].tolist())
            self.assertIn("GLD_TOTAL_HOLDINGS_TONNES", frame["indicator_id"].tolist())
            self.assertIn("chinese_name", frame.columns.tolist())
            self.assertEqual(
                frame.loc[frame["indicator_id"] == "GVZ", "category"].iloc[0],
                "黄金价格",
            )
            self.assertEqual(
                frame.loc[frame["indicator_id"] == "GLD_TOTAL_HOLDINGS_TONNES", "category"].iloc[0],
                "黄金价格",
            )

    def test_refresh_indicator_directory_includes_fx_manifest_artifacts(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            write_file(base / "config" / "indicators.yml", "indicators: []\n")
            write_file(
                base / "data" / "fx" / "manifest.json",
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "name": "DXY",
                                "file_name": "DXY.csv",
                                "notes": "ICE U.S. Dollar Index",
                            },
                            {
                                "name": "EURUSD",
                                "file_name": "EURUSD.csv",
                                "notes": "EUR/USD spot",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
            )
            write_file(
                base / "data" / "fx" / "DXY.csv",
                "date,open,high,low,close,volume,source\n2024-01-01,100,101,99,100.5,0,test\n",
            )
            write_file(
                base / "data" / "fx" / "EURUSD.csv",
                "date,open,high,low,close,volume,source\n2024-01-01,1.1,1.2,1.0,1.15,0,test\n",
            )

            frame = refresh_indicator_directory(base)

            self.assertIn("DXY", frame["indicator_id"].tolist())
            self.assertIn("EURUSD", frame["indicator_id"].tolist())
            self.assertEqual(
                frame.loc[frame["indicator_id"] == "DXY", "chinese_name"].iloc[0],
                "美元指数",
            )

    def test_refresh_indicator_directory_includes_stock_volatility_manifest_artifacts(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            write_file(base / "config" / "indicators.yml", "indicators: []\n")
            write_file(
                base / "data" / "stock_volatility" / "manifest.json",
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "name": "VIX",
                                "file_name": "VIX.csv",
                                "notes": "Cboe Volatility Index from Yahoo Finance.",
                            },
                            {
                                "name": "VVIX",
                                "file_name": "VVIX.csv",
                                "notes": "VVIX from Yahoo Finance.",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
            )
            write_file(
                base / "data" / "stock_volatility" / "VIX.csv",
                "date,open,high,low,close,volume,source\n2024-01-01,12,13,11,12.5,0,test\n",
            )
            write_file(
                base / "data" / "stock_volatility" / "VVIX.csv",
                "date,open,high,low,close,volume,source\n2024-01-01,80,82,79,81,0,test\n",
            )

            frame = refresh_indicator_directory(base)

            self.assertIn("VIX", frame["indicator_id"].tolist())
            self.assertIn("VVIX", frame["indicator_id"].tolist())
            self.assertEqual(
                frame.loc[frame["indicator_id"] == "VIX", "category"].iloc[0],
                "股票波动率",
            )

    def test_refresh_indicator_directory_includes_stock_index_manifest_artifacts(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            write_file(base / "config" / "indicators.yml", "indicators: []\n")
            write_file(
                base / "data" / "stock_index" / "manifest.json",
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "name": "SP500",
                                "file_name": "SP500.csv",
                                "notes": "S&P 500 daily close series.",
                            },
                            {
                                "name": "NASDAQ100",
                                "file_name": "NASDAQ100.csv",
                                "notes": "Nasdaq-100 daily close series.",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
            )
            write_file(
                base / "data" / "stock_index" / "SP500.csv",
                "date,value,source\n2024-01-01,4769.83,test\n",
            )
            write_file(
                base / "data" / "stock_index" / "NASDAQ100.csv",
                "date,value,source\n2024-01-01,16824.46,test\n",
            )

            frame = refresh_indicator_directory(base)

            self.assertIn("SP500", frame["indicator_id"].tolist())
            self.assertIn("NASDAQ100", frame["indicator_id"].tolist())
            self.assertEqual(
                frame.loc[frame["indicator_id"] == "SP500", "source"].iloc[0],
                "yahoo",
            )
            self.assertEqual(
                frame.loc[frame["indicator_id"] == "NASDAQ100", "frequency"].iloc[0],
                "d",
            )

    def test_refresh_indicator_directory_includes_us_debt_manifest_artifacts(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            write_file(base / "config" / "indicators.yml", "indicators: []\n")
            write_file(
                base / "data" / "us_debt" / "manifest.json",
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "name": "Federal Debt Intragovernmental Holdings",
                                "file_name": "Federal Debt Intragovernmental Holdings.csv",
                                "notes": "Daily intragovernmental holdings.",
                            },
                            {
                                "name": "Marketable Treasury Securities Outstanding",
                                "file_name": "Marketable Treasury Securities Outstanding.csv",
                                "notes": "Monthly total marketable debt outstanding.",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
            )
            write_file(
                base / "data" / "us_debt" / "Federal Debt Intragovernmental Holdings.csv",
                "date,value,source\n2024-01-01,7000000,test\n",
            )
            write_file(
                base / "data" / "us_debt" / "Marketable Treasury Securities Outstanding.csv",
                "date,value,source\n2024-01-31,27000000,test\n",
            )

            frame = refresh_indicator_directory(base)

            self.assertIn("FEDERAL_DEBT_INTRAGOVERNMENTAL_HOLDINGS", frame["indicator_id"].tolist())
            self.assertIn("MARKETABLE_TREASURY_SECURITIES_OUTSTANDING", frame["indicator_id"].tolist())
            self.assertEqual(
                frame.loc[
                    frame["indicator_id"] == "FEDERAL_DEBT_INTRAGOVERNMENTAL_HOLDINGS",
                    "chinese_name",
                ].iloc[0],
                "政府内部持有债务",
            )

    def test_indicator_store_filters_by_id_name_frequency_and_date_range(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            write_file(
                base / "data" / "indicator_catalog.csv",
                "indicator_id,category,indicator_name,chinese_name,english_code,source,frequency,file_path,definition,status,enabled\n"
                f"DGS10,名义利率,10年期美债收益率,10年期美债收益率,DGS10,fred,d,{(base / 'data' / 'fred' / '名义利率' / '10年期美债收益率.csv')},desc,active,True\n"
                f"XAU_USD_DAILY_OHLC,黄金价格,XAU/USD日线OHLC,XAU/USD日线OHLC,XAU_USD_DAILY_OHLC,huggingface+investing,d,{(base / 'data' / 'xau' / 'xau_usd_daily_ohlc.csv')},desc,active,True\n",
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

    def test_indicator_store_reads_fx_data_by_english_name(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            write_file(
                base / "data" / "indicator_catalog.csv",
                "indicator_id,category,indicator_name,chinese_name,english_code,source,frequency,file_path,definition,status,enabled\n"
                f"DXY,汇率,DXY,美元指数,DXY,yahoo,d,{(base / 'data' / 'fx' / 'DXY.csv')},desc,active,True\n",
            )
            write_file(
                base / "data" / "fx" / "DXY.csv",
                "date,open,high,low,close,volume,source\n"
                "2024-01-01,100,101,99,100.5,0,test\n"
                "2024-01-02,100.5,101.2,100.1,100.8,0,test\n",
            )

            store = IndicatorStore(base)
            dxy = store.get_one(name="DXY", frequency="d", start_date="2024-01-02")
            dxy_cn = store.get_one(name="美元指数", frequency="d", start_date="2024-01-02")

            self.assertEqual(dxy["date"].tolist(), ["2024-01-02"])
            self.assertEqual(dxy["close"].tolist(), [100.8])
            self.assertEqual(dxy_cn["date"].tolist(), ["2024-01-02"])

    def test_refresh_indicator_directory_keeps_dfii_series_in_nominal_rate_category(self) -> None:
        with WorkspaceTempDir() as tmp:
            base = Path(tmp)
            write_file(
                base / "config" / "indicators.yml",
                """
indicators:
  - category: 名义利率
    indicator_name: 5年期TIPS实际收益率
    source: fred
    series_id: DFII5
    series_type: direct
    frequency: d
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 30
  - category: 名义利率
    indicator_name: 10年期TIPS实际收益率
    source: fred
    series_id: DFII10
    series_type: direct
    frequency: d
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 30
  - category: 名义利率
    indicator_name: 30年期TIPS实际收益率
    source: fred
    series_id: DFII30
    series_type: direct
    frequency: d
    start_date: "2024-01-01"
    enabled: true
    status: active
    update_window_days: 30
""".strip(),
            )
            write_file(
                base / "data" / "fred" / "_catalog.csv",
                "category,indicator_name,source,series_id,frequency,units,enabled,status,file_path\n"
                f"名义利率,5年期TIPS实际收益率,fred,DFII5,D,Percent,True,active,{(base / 'data' / 'fred' / '名义利率' / '5年期TIPS实际收益率.csv')}\n"
                f"名义利率,10年期TIPS实际收益率,fred,DFII10,D,Percent,True,active,{(base / 'data' / 'fred' / '名义利率' / '10年期TIPS实际收益率.csv')}\n"
                f"名义利率,30年期TIPS实际收益率,fred,DFII30,D,Percent,True,active,{(base / 'data' / 'fred' / '名义利率' / '30年期TIPS实际收益率.csv')}\n",
            )
            for name in ["5年期TIPS实际收益率", "10年期TIPS实际收益率", "30年期TIPS实际收益率"]:
                write_file(base / "data" / "fred" / "名义利率" / f"{name}.csv", "date,value\n2024-01-01,1.0\n")

            frame = refresh_indicator_directory(base)
            tips_rows = frame[frame["indicator_id"].isin(["DFII5", "DFII10", "DFII30"])].copy()

            self.assertEqual(sorted(tips_rows["category"].tolist()), ["名义利率", "名义利率", "名义利率"])
            self.assertEqual(sorted(tips_rows["english_code"].tolist()), ["DFII10", "DFII30", "DFII5"])


if __name__ == "__main__":
    unittest.main()
