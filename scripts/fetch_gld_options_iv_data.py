from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
import sys

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gold_data.catalog import refresh_indicator_directory

OUTPUT_DIR = ROOT / "data" / "xau"
NASDAQ_OPTION_CHAIN_URL = "https://api.nasdaq.com/api/quote/GLD/option-chain"
HTTP_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
}


@dataclass(frozen=True)
class SourceSummary:
    name: str
    file_name: str
    start_date: str
    end_date: str
    rows: int
    notes: str = ""


def normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def black_scholes_price(
    option_type: str,
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
) -> float:
    if time_to_expiry <= 0 or volatility <= 0:
        intrinsic = max(spot - strike, 0.0) if option_type == "C" else max(strike - spot, 0.0)
        return intrinsic
    sqrt_t = math.sqrt(time_to_expiry)
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility * volatility) * time_to_expiry) / (
        volatility * sqrt_t
    )
    d2 = d1 - volatility * sqrt_t
    discounted_strike = strike * math.exp(-risk_free_rate * time_to_expiry)
    if option_type == "C":
        return spot * normal_cdf(d1) - discounted_strike * normal_cdf(d2)
    return discounted_strike * normal_cdf(-d2) - spot * normal_cdf(-d1)


def black_scholes_delta(
    option_type: str,
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
) -> float:
    if time_to_expiry <= 0 or volatility <= 0:
        if option_type == "C":
            return 1.0 if spot > strike else 0.0
        return -1.0 if spot < strike else 0.0
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility * volatility) * time_to_expiry) / (
        volatility * math.sqrt(time_to_expiry)
    )
    return normal_cdf(d1) if option_type == "C" else normal_cdf(d1) - 1.0


def implied_volatility(
    option_type: str,
    option_price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
) -> float | None:
    if spot <= 0 or strike <= 0 or option_price <= 0 or time_to_expiry <= 0:
        return None

    intrinsic = max(spot - strike, 0.0) if option_type == "C" else max(strike - spot, 0.0)
    if option_price < intrinsic:
        return None

    low = 0.0001
    high = 5.0
    for _ in range(100):
        mid = (low + high) / 2.0
        price = black_scholes_price(option_type, spot, strike, time_to_expiry, risk_free_rate, mid)
        if abs(price - option_price) < 0.0001:
            return mid
        if price > option_price:
            high = mid
        else:
            low = mid
    return (low + high) / 2.0


def parse_number(value: object) -> float | None:
    text = str(value).replace(",", "").replace("$", "").strip()
    if not text or text == "--" or text.lower() == "none":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_last_trade(text: str) -> tuple[float, pd.Timestamp]:
    price_match = re.search(r"\$([0-9.,]+)", text)
    date_match = re.search(r"AS OF ([A-Z]{3} \d{1,2}, \d{4})", text.upper())
    if not price_match or not date_match:
        raise RuntimeError(f"Could not parse Nasdaq lastTrade field: {text}")
    price = float(price_match.group(1).replace(",", ""))
    as_of_date = pd.to_datetime(date_match.group(1), format="%b %d, %Y")
    return price, as_of_date


def fetch_nasdaq_option_chain(as_of_date: pd.Timestamp, horizon_days: int) -> tuple[float, pd.Timestamp, pd.DataFrame]:
    params = {
        "assetclass": "etf",
        "limit": "10000",
        "fromdate": as_of_date.strftime("%Y-%m-%d"),
        "todate": (as_of_date + pd.Timedelta(days=horizon_days)).strftime("%Y-%m-%d"),
    }
    response = requests.get(NASDAQ_OPTION_CHAIN_URL, params=params, headers=HTTP_HEADERS, timeout=60)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") or {}
    spot, quote_date = parse_last_trade(str(data.get("lastTrade", "")))
    rows = data.get("table", {}).get("rows") or []

    records: list[dict[str, object]] = []
    current_expiry: pd.Timestamp | None = None
    for row in rows:
        if row.get("expirygroup"):
            current_expiry = pd.to_datetime(row["expirygroup"])
            continue
        if current_expiry is None:
            continue
        strike = parse_number(row.get("strike"))
        if strike is None:
            continue
        for option_type, prefix in (("C", "c"), ("P", "p")):
            bid = parse_number(row.get(f"{prefix}_Bid"))
            ask = parse_number(row.get(f"{prefix}_Ask"))
            last = parse_number(row.get(f"{prefix}_Last"))
            if bid is not None and ask is not None and ask > 0:
                price = (bid + ask) / 2.0
                price_source = "mid"
            elif last is not None and last > 0:
                price = last
                price_source = "last"
            else:
                continue
            records.append(
                {
                    "date": quote_date,
                    "expiration_date": current_expiry,
                    "option_type": option_type,
                    "strike": strike,
                    "price": price,
                    "bid": bid,
                    "ask": ask,
                    "last": last,
                    "volume": parse_number(row.get(f"{prefix}_Volume")),
                    "open_interest": parse_number(row.get(f"{prefix}_Openinterest")),
                    "price_source": price_source,
                    "underlying_price": spot,
                }
            )
    if not records:
        raise RuntimeError("Nasdaq returned no usable GLD option rows")
    return spot, quote_date, pd.DataFrame(records)


def add_iv_and_delta(frame: pd.DataFrame, risk_free_rate: float) -> pd.DataFrame:
    enriched = frame.copy()
    enriched["dte"] = (pd.to_datetime(enriched["expiration_date"]) - pd.to_datetime(enriched["date"])).dt.days
    enriched = enriched.loc[enriched["dte"] > 0].reset_index(drop=True)
    enriched["time_to_expiry"] = enriched["dte"] / 365.0
    iv_values = []
    delta_values = []
    for row in enriched.to_dict(orient="records"):
        iv = implied_volatility(
            str(row["option_type"]),
            float(row["price"]),
            float(row["underlying_price"]),
            float(row["strike"]),
            float(row["time_to_expiry"]),
            risk_free_rate,
        )
        iv_values.append(iv)
        if iv is None:
            delta_values.append(None)
        else:
            delta_values.append(
                black_scholes_delta(
                    str(row["option_type"]),
                    float(row["underlying_price"]),
                    float(row["strike"]),
                    float(row["time_to_expiry"]),
                    risk_free_rate,
                    iv,
                )
            )
    enriched["implied_volatility"] = iv_values
    enriched["delta"] = delta_values
    return enriched.dropna(subset=["implied_volatility", "delta"]).reset_index(drop=True)


def select_target_expiry(frame: pd.DataFrame, target_days: int, min_days: int) -> pd.DataFrame:
    candidates = frame.loc[frame["dte"] >= min_days].copy()
    if candidates.empty:
        candidates = frame.copy()
    expiry_dte = candidates.groupby("expiration_date", as_index=False)["dte"].first()
    expiry_dte["distance"] = (expiry_dte["dte"] - target_days).abs()
    target_expiry = expiry_dte.sort_values(["distance", "dte"]).iloc[0]["expiration_date"]
    return candidates.loc[candidates["expiration_date"] == target_expiry].reset_index(drop=True)


def build_atm_iv(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    spot = float(working["underlying_price"].iloc[0])
    working["moneyness_distance"] = (working["strike"] - spot).abs()
    atm_strike = working.sort_values(["moneyness_distance", "strike"]).iloc[0]["strike"]
    atm_rows = working.loc[working["strike"] == atm_strike]
    call_iv = atm_rows.loc[atm_rows["option_type"] == "C", "implied_volatility"].mean()
    put_iv = atm_rows.loc[atm_rows["option_type"] == "P", "implied_volatility"].mean()
    value = pd.Series([call_iv, put_iv]).dropna().mean()
    return pd.DataFrame(
        [
            {
                "date": pd.to_datetime(working["date"].iloc[0]).strftime("%Y-%m-%d"),
                "value": value,
                "call_atm_iv": call_iv,
                "put_atm_iv": put_iv,
                "expiration_date": pd.to_datetime(working["expiration_date"].iloc[0]).strftime("%Y-%m-%d"),
                "dte": int(working["dte"].iloc[0]),
                "strike": atm_strike,
                "underlying_price": spot,
                "source": "nasdaq_gld_option_chain+black_scholes",
            }
        ]
    )


def build_25d_iv(frame: pd.DataFrame) -> pd.DataFrame:
    calls = frame.loc[frame["option_type"] == "C"].copy()
    puts = frame.loc[frame["option_type"] == "P"].copy()
    if calls.empty or puts.empty:
        return pd.DataFrame()
    call = calls.loc[(calls["delta"] - 0.25).abs().idxmin()]
    put = puts.loc[(puts["delta"] + 0.25).abs().idxmin()]
    call_iv = float(call["implied_volatility"])
    put_iv = float(put["implied_volatility"])
    return pd.DataFrame(
        [
            {
                "date": pd.to_datetime(frame["date"].iloc[0]).strftime("%Y-%m-%d"),
                "value": (call_iv + put_iv) / 2.0,
                "call_25d_iv": call_iv,
                "put_25d_iv": put_iv,
                "iv_skew_25d": call_iv - put_iv,
                "expiration_date": pd.to_datetime(frame["expiration_date"].iloc[0]).strftime("%Y-%m-%d"),
                "dte": int(frame["dte"].iloc[0]),
                "call_strike": float(call["strike"]),
                "put_strike": float(put["strike"]),
                "call_delta": float(call["delta"]),
                "put_delta": float(put["delta"]),
                "underlying_price": float(frame["underlying_price"].iloc[0]),
                "source": "nasdaq_gld_option_chain+black_scholes",
            }
        ]
    )


def append_daily(path: Path, frame: pd.DataFrame) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_csv(path)
        combined = pd.concat([existing, frame], ignore_index=True)
    else:
        combined = frame.copy()
    combined = combined.drop_duplicates(subset=["date"], keep="last")
    combined = combined.sort_values("date").reset_index(drop=True)
    combined.to_csv(path, index=False)
    return combined


def summarize(frame: pd.DataFrame, name: str, file_name: str, notes: str = "") -> SourceSummary:
    return SourceSummary(
        name=name,
        file_name=file_name,
        start_date=str(frame["date"].iloc[0]),
        end_date=str(frame["date"].iloc[-1]),
        rows=len(frame),
        notes=notes,
    )


def upsert_manifest(output_dir: Path, summaries: list[SourceSummary]) -> None:
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"artifacts": []}
    artifacts = {
        item.get("file_name", ""): item
        for item in manifest.get("artifacts", [])
        if isinstance(item, dict)
    }
    for summary in summaries:
        artifacts[summary.file_name] = summary.__dict__
    manifest["generated_at"] = pd.Timestamp.utcnow().isoformat()
    manifest["artifacts"] = list(artifacts.values())
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch GLD option-chain data and derive gold option IV proxies.")
    parser.add_argument("--target-days", type=int, default=30)
    parser.add_argument("--min-days", type=int, default=7)
    parser.add_argument("--horizon-days", type=int, default=90)
    parser.add_argument("--risk-free-rate", type=float, default=0.045)
    parser.add_argument("--as-of-date", type=str, default=pd.Timestamp.utcnow().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    as_of_date = pd.to_datetime(args.as_of_date)
    _, quote_date, raw_chain = fetch_nasdaq_option_chain(as_of_date, args.horizon_days)
    chain = add_iv_and_delta(raw_chain, args.risk_free_rate)
    target_chain = select_target_expiry(chain, args.target_days, args.min_days)

    atm_iv = build_atm_iv(target_chain)
    iv_25d = build_25d_iv(target_chain)
    if atm_iv.empty or iv_25d.empty:
        raise RuntimeError("Could not derive both ATM IV and 25D IV from Nasdaq GLD option chain")

    atm_file = "gld_gold_options_atm_iv.csv"
    iv_25d_file = "gld_gold_options_25d_iv.csv"
    written_atm = append_daily(OUTPUT_DIR / atm_file, atm_iv)
    written_25d = append_daily(OUTPUT_DIR / iv_25d_file, iv_25d)

    summaries = [
        summarize(
            written_atm,
            "GLD_GOLD_OPTIONS_ATM_IV",
            atm_file,
            "Daily GLD option ATM implied volatility proxy derived from Nasdaq option-chain bid/ask prices with Black-Scholes inversion.",
        ),
        summarize(
            written_25d,
            "GLD_GOLD_OPTIONS_25D_IV",
            iv_25d_file,
            "Daily GLD option 25-delta implied volatility proxy derived from Nasdaq option-chain bid/ask prices and Black-Scholes deltas.",
        ),
    ]
    upsert_manifest(OUTPUT_DIR, summaries)
    refresh_indicator_directory(ROOT)

    print(f"Quote date: {quote_date.date()}")
    print(f"Wrote {OUTPUT_DIR / atm_file}")
    print(f"Wrote {OUTPUT_DIR / iv_25d_file}")
    print(f"Wrote {OUTPUT_DIR / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
