from typing import Any
from urllib.parse import quote

import requests


class Poe2ScoutClient:
    base_url = "https://poe2scout.com/api/poe2"

    def __init__(self, timeout_seconds: float = 15.0):
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def fetch_leagues(self) -> list[dict[str, Any]]:
        data = self._get("Leagues")
        if not isinstance(data, list):
            raise ValueError("Expected poe2scout leagues response to be a list")
        return data

    def fetch_currency_category(
        self,
        league_name: str,
        category_name: str,
        reference_currency: str,
        data_points: int = 7,
        frequency_hours: int = 1,
    ) -> dict[str, Any]:
        encoded_league = quote(league_name, safe="")
        return self._get(
            f"Leagues/{encoded_league}/Currencies/ByCategory",
            params={
                "Category": category_name,
                "ReferenceCurrency": reference_currency,
                "DataPoints": str(data_points),
                "FrequencyHours": str(frequency_hours),
            },
        )

    def _get(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path}"
        response = self.session.get(url, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json()
