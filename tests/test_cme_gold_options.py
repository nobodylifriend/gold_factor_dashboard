from __future__ import annotations

from pathlib import Path
import shutil
import unittest
import uuid

from scripts.fetch_cme_gold_options_data import build_outputs, load_option_chain


class WorkspaceTempDir:
    def __enter__(self) -> Path:
        root = Path(__file__).resolve().parents[1] / ".tmp_tests"
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / str(uuid.uuid4())
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path

    def __exit__(self, exc_type, exc, tb) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class CMEGoldOptionsTests(unittest.TestCase):
    def test_loads_official_export_aliases_and_derives_metrics(self) -> None:
        with WorkspaceTempDir() as input_dir:
            (input_dir / "gold_options.csv").write_text(
                "\n".join(
                    [
                        "Trade Date,Product Code,Option Type,Strike Price,Settle,Volume,Open Interest,Implied Volatility,Delta,Underlying Settle",
                        "2026-04-27,OG,C,3000,80,100,10,0.18,0.25,3050",
                        "2026-04-27,OG,P,3000,75,80,5,0.19,-0.25,3050",
                        "2026-04-27,OG,C,3100,35,20,1,0.17,0.18,3050",
                        "2026-04-27,OG,P,3100,120,40,20,0.22,-0.35,3050",
                        "2026-04-28,OG,C,3000,90,110,12,0.20,0.28,3060",
                        "2026-04-28,OG,P,3000,70,70,5,0.18,-0.22,3060",
                        "2026-04-28,OG,C,3100,40,30,1,0.19,0.20,3060",
                        "2026-04-28,OG,P,3100,115,50,18,0.21,-0.30,3060",
                    ]
                ),
                encoding="utf-8",
            )

            chain = load_option_chain(input_dir)
            outputs = build_outputs(chain)

            max_pain = outputs["cme_gold_options_max_pain_strike.csv"][0]
            self.assertEqual(max_pain["value"].tolist(), [3100.0, 3100.0])

            strike_change = outputs["cme_gold_options_strike_oi_change_recent.csv"][0]
            call_3000_second_day = strike_change.loc[
                (strike_change["date"] == "2026-04-28") & (strike_change["strike"] == 3000),
                "call_open_interest_change",
            ].iloc[0]
            self.assertEqual(call_3000_second_day, 2.0)

            put_call_ratio = outputs["cme_gold_options_put_call_oi_ratio.csv"][0]
            self.assertAlmostEqual(put_call_ratio["value"].iloc[-1], 23 / 13)

            iv_25d = outputs["cme_gold_options_25d_iv.csv"][0]
            self.assertAlmostEqual(iv_25d["value"].iloc[0], 0.185)


if __name__ == "__main__":
    unittest.main()
