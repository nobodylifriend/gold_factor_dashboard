from __future__ import annotations

from pathlib import Path

import pandas as pd


CSV_COLUMNS = ["date", "value"]


def read_series_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=CSV_COLUMNS)
    frame = pd.read_csv(path, dtype={"date": "string", "value": "float64"})
    if frame.empty:
        return pd.DataFrame(columns=CSV_COLUMNS)
    return normalize_series_frame(frame)


def write_series_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_series_frame(frame)
    normalized.to_csv(path, index=False)


def write_catalog_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(path, index=False)


def normalize_series_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=CSV_COLUMNS)

    normalized = frame.copy()
    normalized = normalized.dropna(subset=["date", "value"])
    normalized["date"] = normalized["date"].astype("string")
    normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce")
    normalized = normalized.dropna(subset=["value"])
    normalized = normalized.drop_duplicates(subset=["date"], keep="last")
    normalized = normalized.sort_values("date").reset_index(drop=True)
    return normalized[CSV_COLUMNS]


def merge_series_frames(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat([existing, incoming], ignore_index=True)
    return normalize_series_frame(combined)
