from __future__ import annotations

import unittest

import pandas as pd

from scripts.fetch_gld_options_iv_data import (
    add_iv_and_delta,
    black_scholes_price,
    build_25d_iv,
    build_atm_iv,
    select_target_expiry,
)


class GLDOptionsIVTests(unittest.TestCase):
    def test_derives_atm_and_25d_iv_from_option_prices(self) -> None:
        spot = 100.0
        trade_date = pd.Timestamp("2026-04-29")
        expiry = pd.Timestamp("2026-05-29")
        risk_free_rate = 0.04
        time_to_expiry = 30 / 365
        rows = []
        for option_type in ["C", "P"]:
            for strike in [85.0, 90.0, 95.0, 100.0, 105.0, 110.0, 115.0]:
                price = black_scholes_price(option_type, spot, strike, time_to_expiry, risk_free_rate, 0.20)
                rows.append(
                    {
                        "date": trade_date,
                        "expiration_date": expiry,
                        "option_type": option_type,
                        "strike": strike,
                        "price": price,
                        "bid": price - 0.01,
                        "ask": price + 0.01,
                        "last": price,
                        "volume": 10,
                        "open_interest": 100,
                        "price_source": "mid",
                        "underlying_price": spot,
                    }
                )

        chain = add_iv_and_delta(pd.DataFrame(rows), risk_free_rate)
        target = select_target_expiry(chain, target_days=30, min_days=7)
        atm = build_atm_iv(target)
        iv_25d = build_25d_iv(target)

        self.assertAlmostEqual(atm["value"].iloc[0], 0.20, places=3)
        self.assertAlmostEqual(iv_25d["call_25d_iv"].iloc[0], 0.20, places=3)
        self.assertAlmostEqual(iv_25d["put_25d_iv"].iloc[0], 0.20, places=3)


if __name__ == "__main__":
    unittest.main()
