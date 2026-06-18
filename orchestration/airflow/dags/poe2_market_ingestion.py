from __future__ import annotations
from datetime import datetime
from airflow.decorators import dag, task


@dag(
    dag_id="poe2_market_ingestion",
    description="Ingest poe2scout market data into FarmerBot PostgreSQL warehouse.",
    schedule="0 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["farmerbot", "market-data", "etl"],
)
def poe2_market_ingestion():
    @task.bash
    def run_market_pipeline() -> str:
        return "python -m bot.data.pipeline"

    run_market_pipeline()


poe2_market_ingestion()
