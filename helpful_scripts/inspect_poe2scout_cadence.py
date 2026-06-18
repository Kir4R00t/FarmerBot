from __future__ import annotations

import argparse
from datetime import datetime
from typing import Any
from urllib.parse import quote

import requests


DATETIME_KEYS = (
    "Date",
    "date",
    "Timestamp",
    "timestamp",
    "CreatedAt",
    "createdAt",
    "created_at",
    "Time",
    "time",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect poe2scout PriceLogs cadence for a category."
    )
    parser.add_argument("category", nargs="?", default="currency")
    parser.add_argument("reference_currency", nargs="?", default="exalted")
    parser.add_argument("--league", default="Runes of Aldur")
    parser.add_argument("--data-points", type=int, default=7)
    parser.add_argument("--frequency-hours", type=int, default=1)
    args = parser.parse_args()

    url = (
        "https://poe2scout.com/api/poe2/"
        f"Leagues/{quote(args.league, safe='')}/Currencies/ByCategory"
    )
    response = requests.get(
        url,
        params={
            "Category": args.category,
            "ReferenceCurrency": args.reference_currency,
            "DataPoints": args.data_points,
            "FrequencyHours": args.frequency_hours,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()

    items = payload.get("Items", [])
    print(f"category={args.category}")
    print(f"reference_currency={args.reference_currency}")
    print(f"data_points={args.data_points}")
    print(f"frequency_hours={args.frequency_hours}")
    print(f"items={len(items)}")

    for item in items[:10]:
        api_id = item.get("ApiId", "<missing-api-id>")
        price_logs = item.get("PriceLogs") or []
        print()
        print(f"item={api_id}")
        print(f"current_price={item.get('CurrentPrice')}")
        print(f"price_logs_count={len(price_logs)}")

        if not price_logs:
            continue

        print(f"price_log_keys={list(price_logs[0].keys())}")
        for log in price_logs[:5]:
            print(log)

        parsed_dates = [
            parsed
            for log in price_logs
            for parsed in [_parse_first_datetime(log)]
            if parsed is not None
        ]
        if len(parsed_dates) >= 2:
            sorted_dates = sorted(parsed_dates, reverse=True)
            deltas = [
                sorted_dates[index] - sorted_dates[index + 1]
                for index in range(len(sorted_dates) - 1)
            ]
            print("detected_time_deltas=")
            for delta in deltas[:5]:
                print(f"  {delta}")
        else:
            print("No datetime-like PriceLogs field detected.")

    return 0


def _parse_first_datetime(log: dict[str, Any]) -> datetime | None:
    for key in DATETIME_KEYS:
        value = log.get(key)
        if not value:
            continue
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp)

    if not isinstance(value, str):
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
