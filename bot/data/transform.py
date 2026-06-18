from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from bot.data.records import (
    DataQualityIssueRecord,
    PriceLogRecord,
    PriceSnapshotRecord,
    TransformResult,
)


def build_price_snapshot_records(
        payload: dict[str, Any],
        league_name: str,
        category_name: str,
        reference_currency: str,
        snapshot_at: datetime,
        frequency_hours: int = 1,
    ) -> TransformResult:

    records: list[PriceSnapshotRecord] = []
    price_log_records: list[PriceLogRecord] = []
    issues: list[DataQualityIssueRecord] = []

    items = payload.get("Items")
    if not isinstance(items, list):
        issues.append(
            _issue(
                "error",
                "missing_items",
                "poe2scout payload does not contain an Items list",
                payload,
            )
        )
        return TransformResult(records=records, price_logs=price_log_records, issues=issues)

    
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            issues.append(
                _issue(
                    "warning",
                    "invalid_item",
                    f"Item at index {index} is not an object",
                    {"index": index, "item": item},
                )
            )
            continue

        api_id = item.get("ApiId")
        if not isinstance(api_id, str) or not api_id:
            issues.append(
                _issue(
                    "warning",
                    "missing_api_id",
                    f"Item at index {index} has no ApiId",
                    item,
                )
            )
            continue

        try:
            current_price = Decimal(str(item.get("CurrentPrice")))
        except (InvalidOperation, TypeError):
            issues.append(
                _issue(
                    "warning",
                    "invalid_price",
                    f"{api_id} has invalid CurrentPrice",
                    item,
                )
            )
            continue

        if current_price < 0:
            issues.append(
                _issue(
                    "warning",
                    "negative_price",
                    f"{api_id} has negative CurrentPrice",
                    item,
                )
            )
            continue

        price_logs = item.get("PriceLogs")
        if not isinstance(price_logs, list):
            price_logs = []

        records.append(
            PriceSnapshotRecord(
                league_name=league_name,
                category_name=category_name,
                reference_currency=reference_currency,
                item_api_id=api_id,
                item_display_name=api_id.replace("-", " "),
                current_price=current_price,
                snapshot_at=snapshot_at,
                price_logs=price_logs,
                raw_item=item,
            )
        )

        for log_index, price_log in enumerate(price_logs):
            if not isinstance(price_log, dict):
                issues.append(
                    _issue(
                        "warning",
                        "invalid_price_log",
                        f"{api_id} PriceLogs entry at index {log_index} is not an object",
                        {"item": item, "price_log": price_log},
                    )
                )
                continue

            try:
                log_price = Decimal(str(price_log.get("Price")))
            except (InvalidOperation, TypeError):
                issues.append(
                    _issue(
                        "warning",
                        "invalid_price_log_price",
                        f"{api_id} PriceLogs entry has invalid Price",
                        price_log,
                    )
                )
                continue

            source_time = _parse_source_time(price_log.get("Time"))
            if source_time is None:
                issues.append(
                    _issue(
                        "warning",
                        "invalid_price_log_time",
                        f"{api_id} PriceLogs entry has invalid Time",
                        price_log,
                    )
                )
                continue

            quantity = price_log.get("Quantity")
            if not isinstance(quantity, int):
                quantity = None

            price_log_records.append(
                PriceLogRecord(
                    league_name=league_name,
                    category_name=category_name,
                    reference_currency=reference_currency,
                    item_api_id=api_id,
                    item_display_name=api_id.replace("-", " "),
                    source_time=source_time,
                    price=log_price,
                    quantity=quantity,
                    frequency_hours=frequency_hours,
                    raw_log=price_log,
                )
            )

    return TransformResult(
        records=records,
        price_logs=price_log_records,
        issues=issues,
    )


def _parse_source_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    
    
    return parsed


def _issue(
    severity: str,
    issue_type: str,
    message: str,
    payload: dict[str, Any],
    ) -> DataQualityIssueRecord:
    
    return DataQualityIssueRecord(
        source_name="poe2scout",
        severity=severity,
        issue_type=issue_type,
        message=message,
        payload=payload,
    )
