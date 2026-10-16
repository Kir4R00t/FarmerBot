"""Rank comparable market observations without depending on Discord."""

from dataclasses import dataclass
import math
from typing import Any, Literal, Mapping, Sequence

from bot.services.r2_snapshot_reader import ExchangeSnapshot


Direction = Literal["gainers", "losers"]
ItemKind = Literal["currency", "unique"]


@dataclass(frozen=True, slots=True)
class MarketMover:
    record: Mapping[str, Any]
    current_price: float
    previous_price: float
    change_percent: float
    quantity: int | None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _identity(record: Mapping[str, Any]) -> tuple[str, ...] | None:
    def text(key: str) -> str:
        return str(record.get(key) or "").strip()

    # Match unique names across older snapshots which lacked stable unique IDs,
    # consistent with the existing market browser's historical comparisons.
    identifier = (
        text("name").casefold() if text("item_kind") == "unique"
        else text("api_id") or text("name").casefold()
    )
    if not identifier:
        return None
    return (text("realm"), text("league"), text("item_kind"),
            text("category"), identifier, text("reference_currency"))


def _quantity(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value if value >= 0 else None
    number = _number(value)
    if number is None or number < 0 or not number.is_integer():
        return None
    return int(number)


def rank_market_movers(
    snapshots: Sequence[ExchangeSnapshot],
    reference_currency: str,
    *,
    direction: Direction = "gainers",
    item_kind: ItemKind = "currency",
) -> tuple[MarketMover, ...]:
    """Rank changes in a fixed reference; do not infer traded volume.

    Snapshot order is newest first. Ambiguous duplicate identities are excluded
    rather than arbitrarily selecting a price. Missing/new items, non-finite or
    negative prices, and zero/nonpositive historical denominators are excluded.
    """
    if direction not in ("gainers", "losers") or item_kind not in ("currency", "unique"):
        raise ValueError("Unsupported market mover direction or item kind")
    if len(snapshots) < 2:
        return ()
    latest, previous = snapshots[:2]
    if latest.captured_at <= previous.captured_at:
        return ()

    def index(snapshot: ExchangeSnapshot) -> dict[tuple[str, ...], Mapping[str, Any]]:
        records = {}
        duplicates = set()
        for record in snapshot.records:
            if (str(record.get("item_kind") or "").strip() != item_kind
                    or str(record.get("reference_currency") or "").strip() != reference_currency):
                continue
            if item_kind == "currency" and record.get("api_id") == reference_currency:
                continue
            key = _identity(record)
            if key is None:
                continue
            if key in records:
                duplicates.add(key)
            records[key] = record
        return {key: record for key, record in records.items() if key not in duplicates}

    old_records = index(previous)
    movers = []
    for key, record in index(latest).items():
        old = old_records.get(key)
        if old is None:
            continue
        current_price = _number(record.get("current_price"))
        previous_price = _number(old.get("current_price"))
        if (current_price is None or current_price < 0
                or previous_price is None or previous_price <= 0):
            continue
        change = ((current_price - previous_price) / previous_price) * 100
        if not math.isfinite(change):
            continue
        rounded = round(change, 2)
        if (direction == "gainers" and rounded <= 0) or (direction == "losers" and rounded >= 0):
            continue
        movers.append(MarketMover(record, current_price, previous_price, change,
                                  _quantity(record.get("current_quantity"))))
    movers.sort(key=lambda mover: (
        -mover.change_percent if direction == "gainers" else mover.change_percent,
        str(mover.record.get("name") or "").casefold(),
        str(mover.record.get("api_id") or ""),
    ))
    return tuple(movers)
