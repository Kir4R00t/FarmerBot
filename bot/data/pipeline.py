from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import argparse
import logging
from typing import Any
from uuid import UUID, uuid4

from bot.data.poe2scout_client import Poe2ScoutClient
from bot.data.repository import MarketRepository
from bot.data.settings import DataSettings, load_settings
from bot.data.transform import build_price_snapshot_records


logger = logging.getLogger(__name__)
PIPELINE_NAME = "poe2_market_ingestion"


@dataclass(frozen=True)
class IngestionSummary:
    run_id: UUID
    status: str
    categories: tuple[str, ...]
    reference_currencies: tuple[str, ...]
    records_loaded: int
    records_failed: int


def run_market_ingestion(
    settings: DataSettings | None = None,
    categories: tuple[str, ...] | None = None,
    reference_currencies: tuple[str, ...] | None = None,
) -> IngestionSummary:
    settings = settings or load_settings()
    selected_categories = categories or settings.market_categories
    selected_references = reference_currencies or settings.reference_currencies

    client = Poe2ScoutClient(timeout_seconds=settings.request_timeout_seconds)
    repository = MarketRepository(settings.database_url)
    run_id = uuid4()
    records_loaded = 0
    records_failed = 0

    repository.start_run(run_id, PIPELINE_NAME)

    try:
        leagues_payload = client.fetch_leagues()
        repository.insert_raw_response(
            run_id=run_id,
            source_endpoint="/Leagues",
            payload=leagues_payload,
        )
        league_metadata = _find_league(leagues_payload, settings.league_name)
        repository.upsert_league(
            settings.league_name,
            divine_price=_decimal_or_none(league_metadata.get("DivinePrice")),
            chaos_divine_price=_decimal_or_none(
                league_metadata.get("ChaosDivinePrice")
            ),
        )

        for selected_reference in selected_references:
            for category_name in selected_categories:
                snapshot_at = datetime.now(UTC)
                payload = client.fetch_currency_category(
                    league_name=settings.league_name,
                    category_name=category_name,
                    reference_currency=selected_reference,
                    data_points=settings.price_log_data_points,
                    frequency_hours=settings.price_log_frequency_hours,
                )
                repository.insert_raw_response(
                    run_id=run_id,
                    source_endpoint="/Leagues/{league}/Currencies/ByCategory",
                    league_name=settings.league_name,
                    category_name=category_name,
                    reference_currency=selected_reference,
                    payload=payload,
                )

                transform_result = build_price_snapshot_records(
                    payload=payload,
                    league_name=settings.league_name,
                    category_name=category_name,
                    reference_currency=selected_reference,
                    snapshot_at=snapshot_at,
                    frequency_hours=settings.price_log_frequency_hours,
                )
                snapshot_count = repository.insert_price_snapshots(
                    run_id,
                    transform_result.records,
                )
                price_log_count = repository.insert_price_logs(
                    run_id,
                    transform_result.price_logs,
                )
                records_loaded += snapshot_count + price_log_count
                records_failed += repository.insert_data_quality_issues(
                    run_id,
                    transform_result.issues,
                )
                logger.info(
                    "Loaded %s snapshots, %s price logs and %s data quality issues "
                    "for category=%s reference_currency=%s",
                    snapshot_count,
                    price_log_count,
                    len(transform_result.issues),
                    category_name,
                    selected_reference,
                )

        repository.finish_run(
            run_id,
            status="success",
            records_loaded=records_loaded,
            records_failed=records_failed,
        )
        return IngestionSummary(
            run_id=run_id,
            status="success",
            categories=selected_categories,
            reference_currencies=selected_references,
            records_loaded=records_loaded,
            records_failed=records_failed,
        )
    except Exception as exc:
        repository.finish_run(
            run_id,
            status="failed",
            records_loaded=records_loaded,
            records_failed=records_failed,
            error_message=str(exc),
        )
        raise


def _find_league(
    leagues_payload: list[dict[str, Any]],
    league_name: str,
) -> dict[str, Any]:
    for league in leagues_payload:
        if league.get("Value") == league_name or league.get("Name") == league_name:
            return league
    raise ValueError(f"League not found in poe2scout response: {league_name}")


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Run FarmerBot market ETL pipeline.")
    parser.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Market category to ingest. Can be passed multiple times.",
    )
    parser.add_argument(
        "--reference-currency",
        action="append",
        dest="reference_currencies",
        help=(
            "Reference currency used by poe2scout, for example exalted or chaos. "
            "Can be passed multiple times."
        ),
    )
    args = parser.parse_args()

    summary = run_market_ingestion(
        categories=tuple(args.categories) if args.categories else None,
        reference_currencies=(
            tuple(args.reference_currencies) if args.reference_currencies else None
        ),
    )
    logger.info(
        "Finished %s with run_id=%s, records_loaded=%s, records_failed=%s",
        summary.status,
        summary.run_id,
        summary.records_loaded,
        summary.records_failed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
