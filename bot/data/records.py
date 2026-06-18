from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class PriceSnapshotRecord:
    league_name: str
    category_name: str
    reference_currency: str
    item_api_id: str
    item_display_name: str
    current_price: Decimal
    snapshot_at: datetime
    price_logs: list[dict[str, Any]]
    raw_item: dict[str, Any]


@dataclass(frozen=True)
class PriceLogRecord:
    league_name: str
    category_name: str
    reference_currency: str
    item_api_id: str
    item_display_name: str
    source_time: datetime
    price: Decimal
    quantity: int | None
    frequency_hours: int
    raw_log: dict[str, Any]


@dataclass(frozen=True)
class DataQualityIssueRecord:
    source_name: str
    severity: str
    issue_type: str
    message: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class TransformResult:
    records: list[PriceSnapshotRecord]
    price_logs: list[PriceLogRecord]
    issues: list[DataQualityIssueRecord]
