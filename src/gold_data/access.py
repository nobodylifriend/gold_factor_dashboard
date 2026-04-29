from __future__ import annotations

from pathlib import Path

import pandas as pd

from .catalog import load_indicator_directory


class IndicatorStore:
    def __init__(self, base_dir: Path, config_path: Path | None = None) -> None:
        self.base_dir = base_dir
        self.config_path = config_path
        self.catalog = load_indicator_directory(base_dir=base_dir, config_path=config_path)

    def reload(self) -> None:
        self.catalog = load_indicator_directory(base_dir=self.base_dir, config_path=self.config_path)

    def list_indicators(
        self,
        indicator_id: str | None = None,
        category: str | None = None,
        name: str | None = None,
        frequency: str | None = None,
    ) -> pd.DataFrame:
        frame = self.catalog.copy()
        if indicator_id:
            frame = frame.loc[frame["indicator_id"].str.casefold() == indicator_id.casefold()]
        if category:
            frame = frame.loc[frame["category"] == category]
        if name:
            needle = name.casefold()
            frame = frame.loc[
                frame["indicator_name"].str.casefold().str.contains(needle)
                | frame.get("chinese_name", pd.Series("", index=frame.index, dtype="string")).str.casefold().str.contains(needle)
                | frame["english_code"].str.casefold().str.contains(needle)
            ]
        if frequency:
            frame = frame.loc[frame["frequency"].str.casefold() == frequency.casefold()]
        return frame.reset_index(drop=True)

    def get_data(
        self,
        indicator_id: str | None = None,
        category: str | None = None,
        name: str | None = None,
        frequency: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_metadata: bool = True,
    ) -> dict[str, pd.DataFrame]:
        matches = self.list_indicators(
            indicator_id=indicator_id,
            category=category,
            name=name,
            frequency=frequency,
        )
        result: dict[str, pd.DataFrame] = {}
        for row in matches.to_dict(orient="records"):
            path = Path(str(row["file_path"]))
            if not path.exists():
                continue
            frame = pd.read_csv(path)
            if "date" in frame.columns:
                frame["date"] = frame["date"].astype("string")
                if start_date:
                    frame = frame.loc[frame["date"] >= start_date]
                if end_date:
                    frame = frame.loc[frame["date"] <= end_date]
            frame = frame.reset_index(drop=True)
            if include_metadata:
                for column in ["indicator_id", "category", "indicator_name", "frequency", "source"]:
                    frame[column] = row[column]
            result[str(row["indicator_id"])] = frame
        return result

    def get_one(
        self,
        indicator_id: str | None = None,
        category: str | None = None,
        name: str | None = None,
        frequency: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_metadata: bool = True,
    ) -> pd.DataFrame:
        result = self.get_data(
            indicator_id=indicator_id,
            category=category,
            name=name,
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
            include_metadata=include_metadata,
        )
        if len(result) != 1:
            raise ValueError(f"Expected exactly one indicator, found {len(result)}")
        return next(iter(result.values()))
