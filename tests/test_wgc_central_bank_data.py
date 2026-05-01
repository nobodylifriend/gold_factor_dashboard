from __future__ import annotations

import unittest

from scripts.fetch_xau_data import (
    build_country_metric_series,
    derive_wgc_cbd_change,
    flatten_wgc_cbd_linechart,
    flatten_wgc_cbd_snapshot,
)


class WGCCentralBankDataTests(unittest.TestCase):
    def test_flattens_snapshot_table(self) -> None:
        chart_data = {
            "options": {"maxDateAvailable": "2025-12-31"},
            "countries": {
                "CHN": {
                    "countryNameDefault": "China",
                    "countryWGC": "China, P.R.: Mainland",
                    "regionGroup": "East Asia",
                    "economicGroup": "Upper middle income",
                }
            },
            "table": {
                "2025-12-31": {
                    "headers": [[
                        {"val": "Country", "filterId": "countryNameDefault"},
                        {"val": "Region", "filterId": "regionGroup"},
                        {"val": "Economic grouping", "filterId": "economicGroup"},
                        {"val": "FX Reserves", "filterId": "fx_reserves"},
                        {"val": "Total Reserves", "filterId": "total_reserves"},
                        {"val": "Gold Reserves", "filterId": "gold_reserves"},
                        {"val": "Gold Reserves (Tonnes)", "filterId": "gold_reserves_tns"},
                        {"val": "Gold Holdings %", "filterId": "holdings_pct"},
                    ]],
                    "rows": [[
                        {"val": "China", "rowId": "CHN"},
                        {"val": "East Asia", "rowId": "CHN"},
                        {"val": "Upper middle income", "rowId": "CHN"},
                        {"val": "3424872", "rowId": "CHN"},
                        {"val": "3748744.37", "rowId": "CHN"},
                        {"val": "323872.37", "rowId": "CHN"},
                        {"val": "2306.3", "rowId": "CHN"},
                        {"val": "8.64", "rowId": "CHN"},
                    ]],
                }
            },
        }

        frame = flatten_wgc_cbd_snapshot(chart_data, "test:wgc:snapshot")

        self.assertEqual(frame.loc[0, "iso3"], "CHN")
        self.assertEqual(frame.loc[0, "country"], "China")
        self.assertAlmostEqual(frame.loc[0, "gold_reserves_tonnes"], 2306.3)
        self.assertAlmostEqual(frame.loc[0, "gold_holdings_pct"], 8.64)

    def test_flattens_quarterly_series_and_derives_changes(self) -> None:
        chart_data = {
            "countries": {
                "CHN": {
                    "countryNameDefault": "China",
                    "countryWGC": "China, P.R.: Mainland",
                    "regionGroup": "East Asia",
                    "economicGroup": "Upper middle income",
                }
            },
            "linechart": {
                "QTD_FULL": {
                    "gold_reserves_tns": {
                        "data": [
                            {
                                "name": "CHN",
                                "data": [
                                    [1703980800000, 2235.39],
                                    [1711843200000, 2262.45],
                                    [1719705600000, 2264.32],
                                ],
                            }
                        ]
                    },
                    "holdings_pct": {
                        "data": [
                            {
                                "name": "CHN",
                                "data": [
                                    [1703980800000, 4.33],
                                    [1711843200000, 4.87],
                                    [1719705600000, 4.91],
                                ],
                            }
                        ]
                    },
                }
            },
        }

        quarterly = flatten_wgc_cbd_linechart(chart_data, "QTD_FULL", "test:wgc:quarterly")
        changes = derive_wgc_cbd_change(quarterly, "test:wgc:change")
        holdings = build_country_metric_series(
            quarterly,
            "gold_holdings_pct",
            "test:wgc:quarterly",
            extra_columns=("region_group", "economic_group"),
        )

        self.assertEqual(quarterly["date"].tolist(), ["2023-12-31", "2024-03-31", "2024-06-30"])
        self.assertAlmostEqual(changes["value"].iloc[0], 27.06, places=2)
        self.assertEqual(changes["direction"].tolist(), ["purchase", "purchase"])
        self.assertAlmostEqual(holdings["value"].iloc[-1], 4.91)


if __name__ == "__main__":
    unittest.main()
