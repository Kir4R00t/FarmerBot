from dataclasses import dataclass
import os

from dotenv import load_dotenv


DEFAULT_MARKET_CATEGORIES = (
    "currency",
    "ultimatum",
    "essences",
    "delirium",
    "breach",
    "fragments",
    "uncutgems",
    "runes",
    "idols",
    "lineagesupportgems",
    "abyss",
    "vaultkeys",
)


@dataclass(frozen=True)
class DataSettings:
    database_url: str
    league_name: str
    reference_currencies: tuple[str, ...]
    market_categories: tuple[str, ...]
    price_log_data_points: int
    price_log_frequency_hours: int
    request_timeout_seconds: float


def load_settings(env_file: str | None = ".env") -> DataSettings:
    if env_file:
        load_dotenv(env_file)

    categories = _csv_tuple(
        os.getenv("POE2_MARKET_CATEGORIES", ",".join(DEFAULT_MARKET_CATEGORIES))
    )
    reference_currencies = _csv_tuple(
        os.getenv(
            "POE2_REFERENCE_CURRENCIES",
            os.getenv("POE2_REFERENCE_CURRENCY", "exalted"),
        )
    )

    return DataSettings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql://farmerbot:farmerbot@localhost:5432/farmerbot",
        ),
        league_name=os.getenv("POE2_LEAGUE", "Runes of Aldur"),
        reference_currencies=reference_currencies or ("exalted",),
        market_categories=categories or DEFAULT_MARKET_CATEGORIES,
        price_log_data_points=int(os.getenv("POE2_PRICE_LOG_DATA_POINTS", "7")),
        price_log_frequency_hours=int(os.getenv("POE2_PRICE_LOG_FREQUENCY_HOURS", "1")),
        request_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "15")),
    )


def _csv_tuple(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())
