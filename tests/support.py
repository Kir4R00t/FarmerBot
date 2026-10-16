"""Small fixtures shared by tests; no real service credentials or connections."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
from discord.ext import commands

from bot.services.r2_snapshot_reader import ExchangeSnapshot


NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)


def record(**overrides):
    values = dict(item_kind="currency", category="currency", api_id="chaos",
                  name="Chaos Orb", reference_currency="exalted", current_price=10,
                  price_observed_at="2026-10-16T11:00:00Z")
    values.update(overrides)
    return values


def snapshot(*records, captured_at=NOW, snapshot_id="snapshot-1"):
    return ExchangeSnapshot("test/exchange-snapshot.json", snapshot_id, captured_at, tuple(records))


def interaction(owner_id=42):
    return SimpleNamespace(
        user=SimpleNamespace(id=owner_id),
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock(), edit_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )


def bot():
    return commands.Bot(command_prefix="!", intents=discord.Intents.none())


async def run_in_test_thread(function, /, *args, **kwargs):
    """Execute the mocked blocking dependency inline in command unit tests."""
    return function(*args, **kwargs)
