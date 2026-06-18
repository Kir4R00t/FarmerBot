from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import Connection, connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from bot.data.records import DataQualityIssueRecord, PriceLogRecord, PriceSnapshotRecord


class MarketRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def start_run(self, run_id: UUID, pipeline_name: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO farmerbot.etl_run (run_id, pipeline_name, status)
                VALUES (%s, %s, 'running')
                """,
                (run_id, pipeline_name),
            )

    def finish_run(
        self,
        run_id: UUID,
        status: str,
        records_loaded: int,
        records_failed: int,
        error_message: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE farmerbot.etl_run
                SET finished_at = now(),
                    status = %s,
                    records_loaded = %s,
                    records_failed = %s,
                    error_message = %s
                WHERE run_id = %s
                """,
                (status, records_loaded, records_failed, error_message, run_id),
            )

    def insert_raw_response(
        self,
        run_id: UUID,
        source_endpoint: str,
        payload: Any,
        league_name: str | None = None,
        category_name: str | None = None,
        reference_currency: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO farmerbot.raw_poe2scout_response (
                    run_id,
                    source_endpoint,
                    league_name,
                    category_name,
                    reference_currency,
                    payload
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    source_endpoint,
                    league_name,
                    category_name,
                    reference_currency,
                    Jsonb(payload),
                ),
            )

    def upsert_league(
        self,
        league_name: str,
        divine_price: Decimal | None = None,
        chaos_divine_price: Decimal | None = None,
    ) -> int:
        with self._connect() as conn:
            return self._upsert_league(
                conn,
                league_name,
                divine_price,
                chaos_divine_price,
            )

    def insert_price_snapshots(
        self,
        run_id: UUID,
        records: list[PriceSnapshotRecord],
    ) -> int:
        if not records:
            return 0

        with self._connect() as conn:
            with conn.transaction():
                for record in records:
                    league_id = self._upsert_league(conn, record.league_name)
                    category_id = self._upsert_category(conn, record.category_name)
                    item_id = self._upsert_item(
                        conn,
                        record.item_api_id,
                        record.item_display_name,
                    )
                    conn.execute(
                        """
                        INSERT INTO farmerbot.fact_price_snapshot (
                            run_id,
                            item_id,
                            league_id,
                            category_id,
                            reference_currency,
                            current_price,
                            snapshot_at,
                            price_logs,
                            raw_item
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (
                            item_id,
                            league_id,
                            category_id,
                            reference_currency,
                            snapshot_at
                        )
                        DO UPDATE SET
                            current_price = EXCLUDED.current_price,
                            price_logs = EXCLUDED.price_logs,
                            raw_item = EXCLUDED.raw_item
                        """,
                        (
                            run_id,
                            item_id,
                            league_id,
                            category_id,
                            record.reference_currency,
                            record.current_price,
                            record.snapshot_at,
                            Jsonb(record.price_logs),
                            Jsonb(record.raw_item),
                        ),
                    )
        return len(records)

    def insert_price_logs(
        self,
        run_id: UUID,
        records: list[PriceLogRecord],
    ) -> int:
        if not records:
            return 0

        with self._connect() as conn:
            with conn.transaction():
                for record in records:
                    league_id = self._upsert_league(conn, record.league_name)
                    category_id = self._upsert_category(conn, record.category_name)
                    item_id = self._upsert_item(
                        conn,
                        record.item_api_id,
                        record.item_display_name,
                    )
                    conn.execute(
                        """
                        INSERT INTO farmerbot.fact_price_log (
                            run_id,
                            item_id,
                            league_id,
                            category_id,
                            reference_currency,
                            source_time,
                            price,
                            quantity,
                            frequency_hours,
                            raw_log
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (
                            item_id,
                            league_id,
                            category_id,
                            reference_currency,
                            source_time,
                            frequency_hours
                        )
                        DO UPDATE SET
                            run_id = EXCLUDED.run_id,
                            price = EXCLUDED.price,
                            quantity = EXCLUDED.quantity,
                            raw_log = EXCLUDED.raw_log,
                            loaded_at = now()
                        """,
                        (
                            run_id,
                            item_id,
                            league_id,
                            category_id,
                            record.reference_currency,
                            record.source_time,
                            record.price,
                            record.quantity,
                            record.frequency_hours,
                            Jsonb(record.raw_log),
                        ),
                    )
        return len(records)

    def insert_data_quality_issues(
        self,
        run_id: UUID,
        issues: list[DataQualityIssueRecord],
    ) -> int:
        if not issues:
            return 0

        with self._connect() as conn:
            with conn.transaction():
                for issue in issues:
                    conn.execute(
                        """
                        INSERT INTO farmerbot.data_quality_issue (
                            run_id,
                            source_name,
                            severity,
                            issue_type,
                            message,
                            payload
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            run_id,
                            issue.source_name,
                            issue.severity,
                            issue.issue_type,
                            issue.message,
                            Jsonb(issue.payload),
                        ),
                    )
        return len(issues)

    def get_recent_runs(self, limit: int = 5) -> list[dict[str, Any]]:
        with self._connect() as conn:
            result = conn.execute(
                """
                SELECT
                    run_id,
                    pipeline_name,
                    started_at,
                    finished_at,
                    status,
                    records_loaded,
                    records_failed,
                    error_message
                FROM farmerbot.etl_run
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(result.fetchall())

    def get_top_movers(
        self,
        league_name: str,
        category_name: str,
        reference_currency: str,
        hours: int = 24,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            result = conn.execute(
                """
                WITH filtered AS (
                    SELECT
                        i.api_id,
                        i.display_name,
                        f.price,
                        f.source_time,
                        FIRST_VALUE(f.price) OVER item_window AS first_price,
                        FIRST_VALUE(f.price) OVER item_window_desc AS last_price,
                        MIN(f.source_time) OVER item_partition AS first_seen,
                        MAX(f.source_time) OVER item_partition AS last_seen
                    FROM farmerbot.fact_price_log f
                    JOIN farmerbot.dim_item i ON i.item_id = f.item_id
                    JOIN farmerbot.dim_league l ON l.league_id = f.league_id
                    JOIN farmerbot.dim_category c ON c.category_id = f.category_id
                    WHERE l.league_name = %s
                        AND c.category_name = %s
                        AND f.reference_currency = %s
                        AND f.source_time >= now() - (%s::text || ' hours')::interval
                    WINDOW
                        item_partition AS (PARTITION BY i.item_id),
                        item_window AS (
                            PARTITION BY i.item_id
                            ORDER BY f.source_time ASC
                            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                        ),
                        item_window_desc AS (
                            PARTITION BY i.item_id
                            ORDER BY f.source_time DESC
                            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                        )
                ),
                movers AS (
                    SELECT DISTINCT
                        api_id,
                        display_name,
                        first_price,
                        last_price,
                        first_seen,
                        last_seen,
                        CASE
                            WHEN first_price = 0 THEN NULL
                            ELSE ROUND(
                                ((last_price - first_price) / first_price) * 100,
                                2
                            )
                        END AS change_pct
                    FROM filtered
                    WHERE first_seen <> last_seen
                )
                SELECT *
                FROM movers
                ORDER BY ABS(change_pct) DESC NULLS LAST
                LIMIT %s
                """,
                (league_name, category_name, reference_currency, hours, limit),
            )
            return list(result.fetchall())

    def get_price_history(
        self,
        league_name: str,
        item_api_id: str,
        category_name: str,
        reference_currency: str,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            result = conn.execute(
                """
                SELECT
                    f.source_time,
                    f.price,
                    f.quantity,
                    f.loaded_at
                FROM farmerbot.fact_price_log f
                JOIN farmerbot.dim_item i ON i.item_id = f.item_id
                JOIN farmerbot.dim_league l ON l.league_id = f.league_id
                JOIN farmerbot.dim_category c ON c.category_id = f.category_id
                WHERE l.league_name = %s
                    AND i.api_id = %s
                    AND c.category_name = %s
                    AND f.reference_currency = %s
                    AND f.source_time >= now() - (%s::text || ' days')::interval
                ORDER BY f.source_time
                """,
                (league_name, item_api_id, category_name, reference_currency, days),
            )
            return list(result.fetchall())

    def _connect(self) -> Connection:
        return connect(self.database_url, row_factory=dict_row)

    def _upsert_league(
        self,
        conn: Connection,
        league_name: str,
        divine_price: Decimal | None = None,
        chaos_divine_price: Decimal | None = None,
    ) -> int:
        result = conn.execute(
            """
            INSERT INTO farmerbot.dim_league (
                league_name,
                divine_price,
                chaos_divine_price
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (league_name)
            DO UPDATE SET
                divine_price = COALESCE(EXCLUDED.divine_price, dim_league.divine_price),
                chaos_divine_price = COALESCE(
                    EXCLUDED.chaos_divine_price,
                    dim_league.chaos_divine_price
                ),
                updated_at = now()
            RETURNING league_id
            """,
            (league_name, divine_price, chaos_divine_price),
        )
        return int(result.fetchone()["league_id"])

    def _upsert_category(self, conn: Connection, category_name: str) -> int:
        result = conn.execute(
            """
            INSERT INTO farmerbot.dim_category (category_name)
            VALUES (%s)
            ON CONFLICT (category_name)
            DO UPDATE SET
                category_name = EXCLUDED.category_name,
                updated_at = now()
            RETURNING category_id
            """,
            (category_name,),
        )
        return int(result.fetchone()["category_id"])

    def _upsert_item(
        self,
        conn: Connection,
        api_id: str,
        display_name: str,
    ) -> int:
        result = conn.execute(
            """
            INSERT INTO farmerbot.dim_item (api_id, display_name)
            VALUES (%s, %s)
            ON CONFLICT (api_id)
            DO UPDATE SET
                display_name = EXCLUDED.display_name,
                updated_at = now()
            RETURNING item_id
            """,
            (api_id, display_name),
        )
        return int(result.fetchone()["item_id"])
