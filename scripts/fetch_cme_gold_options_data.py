from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gold_data.catalog import refresh_indicator_directory

DEFAULT_INPUT_DIR = ROOT / "data" / "vendor" / "cme" / "gold_options"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "xau"
DEFAULT_LOOKBACK_DAYS = 365
DEFAULT_CONTRACT_MULTIPLIER = 100.0


@dataclass(frozen=True)
class SourceSummary:
    name: str
    file_name: str
    start_date: str
    end_date: str
    rows: int
    notes: str = ""


COLUMN_ALIASES = {
    "date": {
        "date",
        "trade_date",
        "trade date",
        "business date",
        "settle date",
        "settlement date",
        "clearing date",
    },
    "product_code": {"product", "product code", "product_code", "symbol", "commodity", "contract code"},
    "contract_month": {"contract month", "contract_month", "month", "futures contract", "contract"},
    "expiration_date": {"expiration", "expiration date", "expiration_date", "expiry", "expiry date"},
    "option_type": {"option type", "option_type", "put/call", "call/put", "cp", "right", "type"},
    "strike": {"strike", "strike price", "strike_price", "exercise price", "exercise_price"},
    "premium": {"premium", "option price", "option_price", "settle", "settlement", "settle price", "last"},
    "volume": {"volume", "total volume", "total_volume", "vol"},
    "open_interest": {"open interest", "open_interest", "open int", "open_int", "oi"},
    "implied_volatility": {
        "implied volatility",
        "implied_volatility",
        "iv",
        "settle volatility",
        "settlement volatility",
    },
    "delta": {"delta", "option delta"},
    "underlying_price": {
        "underlying price",
        "underlying_price",
        "underlying settle",
        "underlying_settle",
        "future price",
        "futures price",
        "futures settle",
        "fut settle",
    },
    "neutral_value": {"neutral value", "neutral_value", "fair value", "fair_value"},
    "contract_multiplier": {"contract multiplier", "contract_multiplier", "multiplier"},
}


def canonicalize_column_name(column: object) -> str:
    return str(column).strip().lower().replace("\n", " ").replace("\r", " ")


def rename_columns(frame: pd.DataFrame) -> pd.DataFrame:
    by_alias: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            by_alias[alias] = canonical

    rename_map = {
        column: by_alias[canonicalize_column_name(column)]
        for column in frame.columns
        if canonicalize_column_name(column) in by_alias
    }
    return frame.rename(columns=rename_map)


def read_source_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        frame = pd.read_excel(path)
    else:
        frame = pd.read_csv(path)
    frame = rename_columns(frame)
    frame["source_file"] = path.name
    return frame


def optional_series(frame: pd.DataFrame, column: str, default: object = pd.NA) -> pd.Series:
    if column in frame.columns:
        return frame[column]
    return pd.Series([default] * len(frame), index=frame.index)


def load_option_chain(input_dir: Path) -> pd.DataFrame:
    files = sorted(
        path
        for pattern in ("*.csv", "*.xlsx", "*.xls")
        for path in input_dir.glob(pattern)
        if path.is_file()
    )
    if not files:
        raise FileNotFoundError(
            f"No CME gold option source files found under {input_dir}. "
            "Place official CME/DataMine option-chain exports there first."
        )

    frame = pd.concat([read_source_file(path) for path in files], ignore_index=True)
    required = {"date", "option_type", "strike", "premium"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"CME option source files are missing required columns: {sorted(missing)}")

    if "product_code" in frame.columns:
        product = frame["product_code"].astype(str).str.upper()
        frame = frame.loc[product.str.contains("GC|OG|GOLD", regex=True, na=False)].copy()

    normalized = pd.DataFrame()
    normalized["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    normalized["contract_month"] = optional_series(frame, "contract_month", "").astype(str).str.strip()
    expiration = pd.to_datetime(optional_series(frame, "expiration_date"), errors="coerce")
    normalized["expiration_date"] = expiration.dt.strftime("%Y-%m-%d")
    normalized["option_type"] = frame["option_type"].map(normalize_option_type)
    normalized["strike"] = pd.to_numeric(frame["strike"], errors="coerce")
    normalized["premium"] = pd.to_numeric(frame["premium"], errors="coerce")
    normalized["volume"] = pd.to_numeric(optional_series(frame, "volume", 0), errors="coerce").fillna(0)
    normalized["open_interest"] = pd.to_numeric(optional_series(frame, "open_interest", 0), errors="coerce").fillna(0)
    normalized["implied_volatility"] = pd.to_numeric(optional_series(frame, "implied_volatility"), errors="coerce")
    normalized["delta"] = pd.to_numeric(optional_series(frame, "delta"), errors="coerce")
    normalized["underlying_price"] = pd.to_numeric(optional_series(frame, "underlying_price"), errors="coerce")
    normalized["neutral_value"] = pd.to_numeric(optional_series(frame, "neutral_value"), errors="coerce")
    normalized["contract_multiplier"] = pd.to_numeric(
        optional_series(frame, "contract_multiplier", DEFAULT_CONTRACT_MULTIPLIER),
        errors="coerce",
    ).fillna(DEFAULT_CONTRACT_MULTIPLIER)
    normalized["source"] = "cme_official_export:" + frame["source_file"].astype(str)
    normalized = normalized.dropna(subset=["date", "option_type", "strike", "premium"])
    normalized = normalized.loc[normalized["option_type"].isin(["C", "P"])]
    normalized = normalized.sort_values(["date", "expiration_date", "option_type", "strike"]).reset_index(drop=True)
    return normalized


def normalize_option_type(value: object) -> str:
    text = str(value).strip().upper()
    if text.startswith("C"):
        return "C"
    if text.startswith("P"):
        return "P"
    return text


def filter_recent(frame: pd.DataFrame, lookback_days: int) -> pd.DataFrame:
    if frame.empty:
        return frame
    dates = pd.to_datetime(frame["date"])
    min_date = dates.max() - pd.Timedelta(days=lookback_days)
    return frame.loc[dates >= min_date].reset_index(drop=True)


def build_strike_oi_change(chain: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        chain.groupby(["date", "strike", "option_type"], as_index=False)
        .agg(open_interest=("open_interest", "sum"), volume=("volume", "sum"))
        .pivot(index=["date", "strike"], columns="option_type", values=["open_interest", "volume"])
        .fillna(0)
    )
    grouped.columns = [f"{prefix}_{option.lower()}" for prefix, option in grouped.columns]
    grouped = grouped.reset_index().sort_values(["strike", "date"])
    for column in ["open_interest_c", "open_interest_p", "volume_c", "volume_p"]:
        if column not in grouped.columns:
            grouped[column] = 0
    grouped = grouped.rename(
        columns={
            "open_interest_c": "call_open_interest",
            "open_interest_p": "put_open_interest",
            "volume_c": "call_volume",
            "volume_p": "put_volume",
        }
    )
    grouped["call_open_interest_change"] = grouped.groupby("strike")["call_open_interest"].diff().fillna(0)
    grouped["put_open_interest_change"] = grouped.groupby("strike")["put_open_interest"].diff().fillna(0)
    grouped["source"] = "derived:cme_gold_options_chain_recent"
    return grouped[
        [
            "date",
            "strike",
            "call_open_interest",
            "put_open_interest",
            "call_open_interest_change",
            "put_open_interest_change",
            "call_volume",
            "put_volume",
            "source",
        ]
    ]


def build_max_pain(chain: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for date, group in chain.groupby("date"):
        strikes = sorted(group["strike"].dropna().unique())
        if not strikes:
            continue
        best_strike = None
        best_pain = None
        for candidate in strikes:
            call = group.loc[group["option_type"] == "C"]
            put = group.loc[group["option_type"] == "P"]
            call_pain = ((candidate - call["strike"]).clip(lower=0) * call["open_interest"] * call["contract_multiplier"]).sum()
            put_pain = ((put["strike"] - candidate).clip(lower=0) * put["open_interest"] * put["contract_multiplier"]).sum()
            total_pain = float(call_pain + put_pain)
            if best_pain is None or total_pain < best_pain:
                best_strike = float(candidate)
                best_pain = total_pain
        records.append(
            {
                "date": date,
                "value": best_strike,
                "total_pain_value": best_pain,
                "source": "derived:cme_gold_options_chain_recent",
            }
        )
    return pd.DataFrame(records).sort_values("date").reset_index(drop=True)


def build_put_call_oi_ratio(chain: pd.DataFrame) -> pd.DataFrame:
    daily = (
        chain.groupby(["date", "option_type"], as_index=False)["open_interest"]
        .sum()
        .pivot(index="date", columns="option_type", values="open_interest")
        .fillna(0)
        .reset_index()
    )
    call_open_interest = daily["C"] if "C" in daily.columns else pd.Series([0] * len(daily), index=daily.index)
    put_open_interest = daily["P"] if "P" in daily.columns else pd.Series([0] * len(daily), index=daily.index)
    daily["value"] = put_open_interest / call_open_interest.replace(0, pd.NA)
    daily["put_open_interest"] = put_open_interest
    daily["call_open_interest"] = call_open_interest
    daily["source"] = "derived:cme_gold_options_chain_recent"
    return daily[["date", "value", "put_open_interest", "call_open_interest", "source"]].dropna(subset=["value"])


def build_daily_volume(chain: pd.DataFrame, option_type: str) -> pd.DataFrame:
    daily = (
        chain.loc[chain["option_type"] == option_type]
        .groupby("date", as_index=False)["volume"]
        .sum()
        .rename(columns={"volume": "value"})
    )
    daily["source"] = "derived:cme_gold_options_chain_recent"
    return daily[["date", "value", "source"]]


def build_atm_iv(chain: pd.DataFrame) -> pd.DataFrame:
    required = chain.dropna(subset=["implied_volatility", "underlying_price"]).copy()
    if required.empty:
        return pd.DataFrame(columns=["date", "value", "source"])
    required["moneyness_distance"] = (required["strike"] - required["underlying_price"]).abs()
    selected = required.loc[required.groupby("date")["moneyness_distance"].idxmin()]
    selected = selected.rename(columns={"implied_volatility": "value"})
    selected["source"] = "derived:cme_gold_options_chain_recent"
    return selected[["date", "value", "strike", "underlying_price", "source"]].sort_values("date").reset_index(drop=True)


def build_25d_iv(chain: pd.DataFrame) -> pd.DataFrame:
    required = chain.dropna(subset=["implied_volatility", "delta"]).copy()
    if required.empty:
        return pd.DataFrame(columns=["date", "call_25d_iv", "put_25d_iv", "value", "source"])

    records: list[dict[str, object]] = []
    for date, group in required.groupby("date"):
        calls = group.loc[group["option_type"] == "C"].copy()
        puts = group.loc[group["option_type"] == "P"].copy()
        call_iv = pd.NA
        put_iv = pd.NA
        if not calls.empty:
            call_row = calls.loc[(calls["delta"] - 0.25).abs().idxmin()]
            call_iv = call_row["implied_volatility"]
        if not puts.empty:
            put_row = puts.loc[(puts["delta"] + 0.25).abs().idxmin()]
            put_iv = put_row["implied_volatility"]
        value = pd.NA
        if pd.notna(call_iv) and pd.notna(put_iv):
            value = (float(call_iv) + float(put_iv)) / 2
        records.append(
            {
                "date": date,
                "value": value,
                "call_25d_iv": call_iv,
                "put_25d_iv": put_iv,
                "source": "derived:cme_gold_options_chain_recent",
            }
        )
    return pd.DataFrame(records).dropna(subset=["value"]).sort_values("date").reset_index(drop=True)


def build_neutral_value(chain: pd.DataFrame) -> pd.DataFrame:
    working = chain.copy()
    if working["neutral_value"].notna().any():
        daily = working.groupby("date", as_index=False)["neutral_value"].sum().rename(columns={"neutral_value": "value"})
        source = "cme_official_export:neutral_value"
    else:
        working["value"] = working["premium"] * working["open_interest"] * working["contract_multiplier"]
        daily = working.groupby("date", as_index=False)["value"].sum()
        source = "derived:premium_open_interest_value"
    daily["source"] = source
    return daily[["date", "value", "source"]]


def summarize(frame: pd.DataFrame, name: str, file_name: str, notes: str = "") -> SourceSummary:
    return SourceSummary(
        name=name,
        file_name=file_name,
        start_date=str(frame["date"].iloc[0]),
        end_date=str(frame["date"].iloc[-1]),
        rows=len(frame),
        notes=notes,
    )


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


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


def build_outputs(chain: pd.DataFrame) -> dict[str, tuple[pd.DataFrame, str]]:
    return {
        "cme_gold_options_premium_recent.csv": (
            chain,
            "Recent CME/COMEX gold option-chain premiums, volumes, open interest, IV, delta, and strikes from official local CME exports.",
        ),
        "cme_gold_options_strike_oi_change_recent.csv": (
            build_strike_oi_change(chain),
            "Daily call/put open interest and day-over-day open-interest change by strike, derived from official CME gold option-chain exports.",
        ),
        "cme_gold_options_max_pain_strike.csv": (
            build_max_pain(chain),
            "Daily max pain strike derived from CME gold option open interest by strike.",
        ),
        "cme_gold_options_atm_iv.csv": (
            build_atm_iv(chain),
            "Daily ATM implied volatility selected from the strike closest to the reported underlying price.",
        ),
        "cme_gold_options_25d_iv.csv": (
            build_25d_iv(chain),
            "Daily 25-delta implied volatility, using call delta closest to +0.25 and put delta closest to -0.25.",
        ),
        "cme_gold_options_put_call_oi_ratio.csv": (
            build_put_call_oi_ratio(chain),
            "Daily put/call open-interest ratio for CME/COMEX gold options.",
        ),
        "cme_gold_options_call_volume.csv": (
            build_daily_volume(chain, "C"),
            "Daily call option volume for CME/COMEX gold options.",
        ),
        "cme_gold_options_put_volume.csv": (
            build_daily_volume(chain, "P"),
            "Daily put option volume for CME/COMEX gold options.",
        ),
        "cme_gold_options_neutral_value.csv": (
            build_neutral_value(chain),
            "Daily neutral option value. Uses official neutral_value when present; otherwise derives premium * open_interest * contract_multiplier.",
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import official CME/COMEX gold option exports and derive daily indicators.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    args = parser.parse_args()

    chain = filter_recent(load_option_chain(args.input_dir), args.lookback_days)
    if chain.empty:
        raise RuntimeError("No CME gold option rows remain after filtering.")

    summaries: list[SourceSummary] = []
    for file_name, (frame, notes) in build_outputs(chain).items():
        if frame.empty:
            print(f"Skipped {file_name}: no source columns available")
            continue
        write_csv(args.output_dir / file_name, frame)
        summaries.append(summarize(frame, Path(file_name).stem.upper(), file_name, notes=notes))
        print(f"Wrote {args.output_dir / file_name}")

    upsert_manifest(args.output_dir, summaries)
    refresh_indicator_directory(ROOT)
    print(f"Wrote {args.output_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
