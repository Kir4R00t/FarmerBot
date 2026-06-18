from decimal import Decimal
import logging

from discord import app_commands
from discord.ext import commands
import discord

from bot.data.repository import MarketRepository
from bot.data.settings import load_settings


logger = logging.getLogger(__name__)

CATEGORY_CHOICES = [
    app_commands.Choice(name="Currency", value="currency"),
    app_commands.Choice(name="Soul Cores", value="ultimatum"),
    app_commands.Choice(name="Essences", value="essences"),
    app_commands.Choice(name="Delirium", value="delirium"),
    app_commands.Choice(name="Breach", value="breach"),
    app_commands.Choice(name="Fragments", value="fragments"),
    app_commands.Choice(name="Uncut Gems", value="uncutgems"),
    app_commands.Choice(name="Runes", value="runes"),
    app_commands.Choice(name="Idols", value="idols"),
    app_commands.Choice(name="Lineage Supports", value="lineagesupportgems"),
    app_commands.Choice(name="Abyss", value="abyss"),
    app_commands.Choice(name="Reliquary keys", value="vaultkeys"),
]

REFERENCE_CHOICES = [
    app_commands.Choice(name="Exalted", value="exalted"),
    app_commands.Choice(name="Chaos", value="chaos"),
]


class MarketAnalytics:
    def __init__(self, client: commands.Bot):
        self.client = client
        self.settings = load_settings()
        self.repository = MarketRepository(self.settings.database_url)
        self.register_commands()

    def register_commands(self):
        @self.client.tree.command(
            name="etlstatus",
            description="Show recent market ETL pipeline runs",
        )
        async def etlstatus(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            try:
                runs = self.repository.get_recent_runs(limit=5)
            except Exception as exc:
                logger.exception("Could not read ETL status")
                await interaction.followup.send(
                    f"Could not read ETL status: {exc}",
                    ephemeral=True,
                )
                return

            if not runs:
                await interaction.followup.send(
                    "No ETL runs found yet. Run `python -m bot.data.pipeline` first.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title="Market ETL status",
                color=discord.Color.blue(),
            )
            for run in runs:
                started_at = run["started_at"].strftime("%Y-%m-%d %H:%M:%S")
                finished_at = (
                    run["finished_at"].strftime("%Y-%m-%d %H:%M:%S")
                    if run["finished_at"]
                    else "running"
                )
                value = (
                    f"status: `{run['status']}`\n"
                    f"started: `{started_at}`\n"
                    f"finished: `{finished_at}`\n"
                    f"loaded: `{run['records_loaded']}` "
                    f"failed: `{run['records_failed']}`"
                )
                embed.add_field(
                    name=str(run["run_id"])[:8],
                    value=value,
                    inline=False,
                )
            await interaction.followup.send(embed=embed, ephemeral=True)

        @self.client.tree.command(
            name="topmovers",
            description="Show items with the biggest price changes from stored snapshots",
        )
        @app_commands.choices(category=CATEGORY_CHOICES, ref_choice=REFERENCE_CHOICES)
        async def topmovers(
            interaction: discord.Interaction,
            category: app_commands.Choice[str],
            ref_choice: app_commands.Choice[str],
            hours: int = 24,
        ):
            await interaction.response.defer()
            safe_hours = max(1, min(hours, 168))
            try:
                rows = self.repository.get_top_movers(
                    league_name=self.settings.league_name,
                    category_name=category.value,
                    reference_currency=ref_choice.value,
                    hours=safe_hours,
                    limit=10,
                )
            except Exception as exc:
                logger.exception("Could not read top movers")
                await interaction.followup.send(
                    f"Could not read top movers: {exc}",
                    ephemeral=True,
                )
                return

            if not rows:
                await interaction.followup.send(
                    "Not enough market history yet. Run the ETL at least twice.",
                    ephemeral=True,
                )
                return

            lines = []
            for row in rows:
                change = _format_change(row["change_pct"])
                lines.append(
                    f"`{row['api_id']}` {_format_price(row['first_price'])}"
                    f" -> {_format_price(row['last_price'])} ({change})"
                )

            embed = discord.Embed(
                title=f"Top movers: {category.name} / {ref_choice.name}",
                description="\n".join(lines),
                color=discord.Color.green(),
            )
            embed.set_footer(text=f"Window: last {safe_hours}h")
            await interaction.followup.send(embed=embed)

        @self.client.tree.command(
            name="pricehistory",
            description="Show poe2scout price log history for an item",
        )
        @app_commands.choices(category=CATEGORY_CHOICES, ref_choice=REFERENCE_CHOICES)
        async def pricehistory(
            interaction: discord.Interaction,
            item_api_id: str,
            category: app_commands.Choice[str],
            ref_choice: app_commands.Choice[str],
            days: int = 7,
        ):
            await interaction.response.defer(ephemeral=True)
            safe_days = max(1, min(days, 30))
            try:
                rows = self.repository.get_price_history(
                    league_name=self.settings.league_name,
                    item_api_id=item_api_id,
                    category_name=category.value,
                    reference_currency=ref_choice.value,
                    days=safe_days,
                )
            except Exception as exc:
                logger.exception("Could not read price history")
                await interaction.followup.send(
                    f"Could not read price history: {exc}",
                    ephemeral=True,
                )
                return

            if not rows:
                await interaction.followup.send(
                    f"No price history found for `{item_api_id}`.",
                    ephemeral=True,
                )
                return

            lines = [
                f"`{row['source_time'].strftime('%m-%d %H:%M')}` "
                f"price `{_format_price(row['price'])}` "
                f"qty `{row['quantity'] if row['quantity'] is not None else 'n/a'}`"
                for row in rows[-15:]
            ]
            embed = discord.Embed(
                title=f"Price history: {item_api_id}",
                description="\n".join(lines),
                color=discord.Color.gold(),
            )
            embed.set_footer(text=f"Showing last {min(len(rows), 15)} buckets")
            await interaction.followup.send(embed=embed, ephemeral=True)


def _format_price(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _format_change(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{value}%"
