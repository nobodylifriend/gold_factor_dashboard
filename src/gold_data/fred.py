from __future__ import annotations

from datetime import date
from typing import Any
import time

import pandas as pd
import requests


class FredClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.stlouisfed.org/fred",
        timeout_seconds: int = 30,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.session = requests.Session()

    def fetch_observations(
        self,
        series_id: str,
        observation_start: str,
        observation_end: str | None = None,
    ) -> pd.DataFrame:
        payload = self._request(
            "series/observations",
            {
                "series_id": series_id,
                "observation_start": observation_start,
                "observation_end": observation_end or date.today().isoformat(),
                "sort_order": "asc",
            },
        )
        rows = []
        for item in payload.get("observations", []):
            value = item.get("value")
            if value in (None, "", "."):
                continue
            rows.append({"date": item["date"], "value": float(value)})
        return pd.DataFrame(rows, columns=["date", "value"])

    def fetch_series_metadata(self, series_id: str) -> dict[str, Any]:
        payload = self._request("series", {"series_id": series_id})
        series = payload.get("seriess", [])
        return series[0] if series else {}

    def _request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        final_params = {"api_key": self.api_key, "file_type": "json", **params}
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, params=final_params, timeout=self.timeout_seconds)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(self.backoff_seconds * attempt)

        raise RuntimeError(f"FRED request failed for {endpoint} with params {params}") from last_error
