from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import math
import re
from typing import Any, Iterable, Sequence

import discord
from discord.ext import commands

from bot.services.r2_snapshot_reader import (
    ExchangeSnapshot,
    R2SnapshotReader,
    SnapshotConfigurationError,
    SnapshotReaderError,
)
from bot.util import item_emojis


logger = logging.getLogger(__name__)

CATEGORY_PAGE_SIZE = 20
ITEM_PAGE_SIZE = 15
REFERENCE_CURRENCIES = ("exalted", "chaos", "divine")
EMOJIS: dict[str, str] = getattr(item_emojis, "list", {})

CATEGORY_LABELS = {
    "lineagesupportgems": "Lineage Supports",
    "uncutgems": "Uncut Gems",
    "ultimatum": "Soul Cores",
    "vaultkeys": "Reliquary Keys",
}


@dataclass(frozen=True, slots=True)
class CategoryGroup:
    item_kind: str
    category: str
    label: str


def _text(value: Any) -> str:
    return str(value or "").strip()


def _humanise_identifier(value: str) -> str:
    if value in CATEGORY_LABELS:
        return CATEGORY_LABELS[value]
    words = re.sub(r"[-_]+", " ", value).strip()
    return words.title() if words else "Unknown"


def discover_category_groups(
    records: Iterable[dict[str, Any]],
) -> tuple[CategoryGroup, ...]:
    """Discover category buttons from the newest snapshot itself."""

    identities = {
        (_text(record.get("item_kind")), _text(record.get("category")))
        for record in records
        if _text(record.get("item_kind")) and _text(record.get("category"))
    }
    category_occurrences: dict[str, int] = {}
    for _, category in identities:
        category_occurrences[category] = category_occurrences.get(category, 0) + 1

    groups = []
    for item_kind, category in identities:
        label = _humanise_identifier(category)
        if category_occurrences[category] > 1:
            label = f"{label} ({_humanise_identifier(item_kind)})"
        groups.append(
            CategoryGroup(
                item_kind=item_kind,
                category=category,
                label=label,
            )
        )

    return tuple(
        sorted(
            groups,
            key=lambda group: (
                0 if group.item_kind == "currency" else 1,
                group.label.casefold(),
            ),
        )
    )


def available_reference_currencies(
    records: Iterable[dict[str, Any]],
) -> frozenset[str]:
    return frozenset(
        reference
        for record in records
        if (reference := _text(record.get("reference_currency")))
    )


def _record_identity(record: dict[str, Any]) -> tuple[str, str, str, str]:
    item_kind = _text(record.get("item_kind"))
    category = _text(record.get("category"))
    reference = _text(record.get("reference_currency"))

    # Unique IDs were absent in older snapshots. Their display names remain a
    # stable bridge across the schema change, while currency ApiIds are stable.
    if item_kind == "unique":
        identifier = _text(record.get("name")).casefold()
    else:
        identifier = (
            _text(record.get("api_id"))
            or _text(record.get("name")).casefold()
        )
    return item_kind, category, identifier, reference


def _index_records(
    records: Iterable[dict[str, Any]],
) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    return {_record_identity(record): record for record in records}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def calculate_price_change(
    current_price: Any,
    previous_price: Any,
) -> float | None:
    """Return conventional percentage change, or None when incomparable."""

    current = _number(current_price)
    previous = _number(previous_price)
    if current is None or previous is None or previous <= 0:
        return None
    return ((current - previous) / previous) * 100


def _records_for_category(
    snapshot: ExchangeSnapshot,
    group: CategoryGroup,
    reference_currency: str,
) -> list[dict[str, Any]]:
    records = [
        record
        for record in snapshot.records
        if _text(record.get("item_kind")) == group.item_kind
        and _text(record.get("category")) == group.category
        and _text(record.get("reference_currency")) == reference_currency
        and _number(record.get("current_price")) is not None
        and not (
            group.item_kind == "currency"
            and _text(record.get("api_id")) == reference_currency
        )
    ]
    records.sort(
        key=lambda record: (
            -(_number(record.get("current_price")) or 0),
            _text(record.get("name")).casefold(),
        )
    )
    return records


def _format_price(value: float) -> str:
    absolute = abs(value)
    if absolute >= 1_000_000_000:
        return f"{value:.3g}"
    if absolute >= 1_000:
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    if absolute >= 1:
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if absolute >= 0.01:
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _item_emoji(record: dict[str, Any]) -> str:
    candidates = (
        _text(record.get("api_id")),
        _slug(_text(record.get("name"))),
    )
    return next((EMOJIS[key] for key in candidates if key in EMOJIS), "•")


def _currency_marker(reference_currency: str) -> str:
    return EMOJIS.get(reference_currency, reference_currency.title())


def _divine_multiplier(
    snapshot: ExchangeSnapshot,
    reference_currency: str,
) -> float | None:
    if reference_currency == "divine":
        return None
    for record in snapshot.records:
        if (
            _text(record.get("item_kind")) == "currency"
            and _text(record.get("category")) == "currency"
            and _text(record.get("api_id")) == "divine"
            and _text(record.get("reference_currency")) == reference_currency
        ):
            multiplier = _number(record.get("current_price"))
            if multiplier is not None and multiplier > 0:
                return multiplier
    return None


def _display_price(
    raw_price: float,
    reference_currency: str,
    divine_multiplier: float | None,
) -> tuple[float, str]:
    # Preserve the useful behaviour of the old command: very expensive items
    # are easier to read in divines than as a huge exalted/chaos number.
    if (
        divine_multiplier is not None
        and raw_price > divine_multiplier * 1.3
    ):
        return raw_price / divine_multiplier, "divine"
    return raw_price, reference_currency


def _parse_optional_timestamp(value: Any) -> datetime | None:
    raw = _text(value)
    if not raw:
        return None
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    try:
        result = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _observed_at_summary(records: Iterable[dict[str, Any]]) -> str:
    observed = _observed_timestamps(records)
    if not observed:
        return "Not recorded"
    if len(observed) == 1:
        return _format_timestamp(observed[0])
    return f"{_format_timestamp(observed[0])} – {_format_timestamp(observed[-1])}"


def _observed_timestamps(
    records: Iterable[dict[str, Any]],
) -> tuple[datetime, ...]:
    return tuple(
        sorted(
            {
                timestamp
                for record in records
                if (
                    timestamp := _parse_optional_timestamp(
                        record.get("price_observed_at")
                    )
                )
            }
        )
    )


def _format_duration(total_seconds: float) -> str:
    seconds = max(0, int(total_seconds))
    minutes = seconds // 60
    if minutes < 1:
        return "<1m"

    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d {hours}h" if hours else f"{days}d"
    if hours:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    return f"{minutes}m"


def _age_range(
    reference_time: datetime,
    observed: Sequence[datetime],
) -> str:
    ages = sorted(
        max(0.0, (reference_time - timestamp).total_seconds())
        for timestamp in observed
    )
    youngest = _format_duration(ages[0])
    oldest = _format_duration(ages[-1])
    if youngest == oldest:
        return f"{youngest} old"
    return f"{youngest} to {oldest} old"


def _staleness_summary(
    records: Iterable[dict[str, Any]],
    captured_at: datetime,
    *,
    now: datetime | None = None,
) -> str:
    observed = _observed_timestamps(records)
    if not observed:
        return "Not recorded in this snapshot"

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    else:
        current_time = current_time.astimezone(timezone.utc)

    return (
        f"At collection: {_age_range(captured_at, observed)}\n"
        f"Right now: {_age_range(current_time, observed)}"
    )


def create_menu_embed(
    snapshots: Sequence[ExchangeSnapshot],
    groups: Sequence[CategoryGroup],
    reference_currency: str,
    category_page: int,
) -> discord.Embed:
    latest = snapshots[0]
    total_pages = max(1, math.ceil(len(groups) / CATEGORY_PAGE_SIZE))
    reference_records = [
        record
        for record in latest.records
        if _text(record.get("reference_currency")) == reference_currency
    ]
    embed = discord.Embed(
        title="PoE2 Market Categories",
        description=(
            "Choose an item category below. The currency buttons change the "
            "reference used for every displayed price.\n\n"
            f"**Reference:** {_currency_marker(reference_currency)} "
            f"{reference_currency.title()}\n"
            f"**Categories found:** {len(groups)}\n"
            f"**Snapshot captured:** {_format_timestamp(latest.captured_at)}"
        ),
        color=discord.Color.gold(),
        timestamp=latest.captured_at,
    )
    embed.add_field(
        name="Data staleness",
        value=_staleness_summary(reference_records, latest.captured_at),
        inline=False,
    )
    if len(snapshots) > 1:
        embed.add_field(
            name="Price comparison",
            value=(
                "Against the previous snapshot captured "
                f"{_format_timestamp(snapshots[1].captured_at)}"
            ),
            inline=False,
        )
    else:
        embed.add_field(
            name="Price comparison",
            value="A second snapshot is needed before changes can be shown.",
            inline=False,
        )
    embed.set_footer(
        text=(
            f"Category page {category_page + 1}/{total_pages} • "
            "Market observation time is shown inside each category"
        )
    )
    return embed


def create_category_embed(
    snapshots: Sequence[ExchangeSnapshot],
    group: CategoryGroup,
    reference_currency: str,
    item_page: int,
) -> tuple[discord.Embed, int, int]:
    latest = snapshots[0]
    current_records = _records_for_category(
        latest,
        group,
        reference_currency,
    )
    total_pages = max(1, math.ceil(len(current_records) / ITEM_PAGE_SIZE))
    item_page = min(max(item_page, 0), total_pages - 1)
    start = item_page * ITEM_PAGE_SIZE
    visible_records = current_records[start : start + ITEM_PAGE_SIZE]

    previous_index = (
        _index_records(snapshots[1].records) if len(snapshots) > 1 else {}
    )
    multiplier = _divine_multiplier(latest, reference_currency)
    previous_multiplier = (
        _divine_multiplier(snapshots[1], reference_currency)
        if len(snapshots) > 1
        else None
    )
    lines: list[str] = []

    for record in visible_records:
        raw_price = _number(record.get("current_price"))
        if raw_price is None:
            continue
        display_price, display_currency = _display_price(
            raw_price,
            reference_currency,
            multiplier,
        )
        previous = previous_index.get(_record_identity(record))
        previous_raw_price = (
            _number(previous.get("current_price")) if previous else None
        )

        # The percentage must describe the same unit that is visible. If the
        # current value is displayed in divines, convert the previous value to
        # divines using the previous snapshot's exchange rate before comparing.
        if display_currency == "divine" and reference_currency != "divine":
            comparison_previous = (
                previous_raw_price / previous_multiplier
                if previous_raw_price is not None
                and previous_multiplier is not None
                and previous_multiplier > 0
                else None
            )
            comparison_current = display_price
        else:
            comparison_previous = previous_raw_price
            comparison_current = raw_price
        change = calculate_price_change(
            comparison_current,
            comparison_previous,
        )

        if change is None:
            change_display = "`change —`"
        elif change > 0.005:
            change_display = (
                f"{EMOJIS.get('green-up', '▲')} `+{change:.2f}%`"
            )
        elif change < -0.005:
            change_display = (
                f"{EMOJIS.get('red-down', '▼')} `{change:.2f}%`"
            )
        else:
            change_display = "`0.00%`"

        item_name = _text(record.get("name")) or _text(record.get("api_id"))
        item_name = discord.utils.escape_markdown(item_name[:100] or "Unknown")
        lines.append(
            f"{_item_emoji(record)} **{item_name}** — "
            f"`{_format_price(display_price)}` "
            f"{_currency_marker(display_currency)} · {change_display}"
        )

    if not lines:
        lines.append("No priced items were found for this category and reference.")

    embed = discord.Embed(
        title=f"{group.label} Prices",
        description="\n".join(lines),
        color=discord.Color.gold(),
        timestamp=latest.captured_at,
    )
    embed.add_field(
        name="Reference",
        value=f"{_currency_marker(reference_currency)} {reference_currency.title()}",
        inline=True,
    )
    embed.add_field(
        name="Market observed",
        value=_observed_at_summary(current_records),
        inline=True,
    )
    embed.add_field(
        name="Data staleness",
        value=_staleness_summary(current_records, latest.captured_at),
        inline=False,
    )
    if len(snapshots) > 1:
        previous_records = _records_for_category(
            snapshots[1],
            group,
            reference_currency,
        )
        embed.add_field(
            name="Compared with",
            value=(
                f"Previous snapshot ({_observed_at_summary(previous_records)})"
            ),
            inline=False,
        )
    else:
        embed.add_field(
            name="Compared with",
            value="Unavailable until a second snapshot is stored",
            inline=False,
        )

    first_item = start + 1 if current_records else 0
    last_item = min(start + ITEM_PAGE_SIZE, len(current_records))
    embed.set_footer(
        text=(
            f"Items {first_item}–{last_item} of {len(current_records)} • "
            f"Page {item_page + 1}/{total_pages} • Data from poe2scout.com"
        )
    )
    return embed, item_page, total_pages


class OwnedView(discord.ui.View):
    def __init__(self, owner_id: int, *, timeout: float = 300) -> None:
        super().__init__(timeout=timeout)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Run `/market-menu` yourself to open your own market browser.",
            ephemeral=True,
        )
        return False


class CategoryButton(discord.ui.Button):
    def __init__(
        self,
        group: CategoryGroup,
        *,
        row: int,
        index: int,
    ) -> None:
        super().__init__(
            label=group.label[:80],
            style=discord.ButtonStyle.secondary,
            row=row,
            custom_id=f"market:category:{index}",
        )
        self.group = group

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, CategoryMenuView):
            await view.show_category(interaction, self.group)


class CategoryPageButton(discord.ui.Button):
    def __init__(self, direction: int, *, disabled: bool) -> None:
        super().__init__(
            label="◀" if direction < 0 else "▶",
            style=discord.ButtonStyle.secondary,
            row=4,
            disabled=disabled,
            custom_id=f"market:categories:{'previous' if direction < 0 else 'next'}",
        )
        self.direction = direction

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, CategoryMenuView):
            await view.change_category_page(interaction, self.direction)


class ReferenceCurrencyButton(discord.ui.Button):
    def __init__(
        self,
        reference_currency: str,
        *,
        selected: bool,
        available: bool,
    ) -> None:
        super().__init__(
            label=reference_currency.title(),
            style=(
                discord.ButtonStyle.primary
                if selected
                else discord.ButtonStyle.secondary
            ),
            row=4,
            disabled=selected or not available,
            custom_id=f"market:reference:{reference_currency}",
        )
        self.reference_currency = reference_currency

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, CategoryMenuView):
            await view.change_reference(interaction, self.reference_currency)


class CategoryMenuView(OwnedView):
    def __init__(
        self,
        owner_id: int,
        snapshots: Sequence[ExchangeSnapshot],
        reference_currency: str,
        *,
        category_page: int = 0,
    ) -> None:
        super().__init__(owner_id)
        self.snapshots = tuple(snapshots)
        self.reference_currency = reference_currency
        self.groups = discover_category_groups(self.snapshots[0].records)
        self.available_references = available_reference_currencies(
            self.snapshots[0].records
        )
        self.total_pages = max(
            1,
            math.ceil(len(self.groups) / CATEGORY_PAGE_SIZE),
        )
        self.category_page = min(max(category_page, 0), self.total_pages - 1)

        start = self.category_page * CATEGORY_PAGE_SIZE
        for local_index, group in enumerate(
            self.groups[start : start + CATEGORY_PAGE_SIZE]
        ):
            self.add_item(
                CategoryButton(
                    group,
                    row=local_index // 5,
                    index=start + local_index,
                )
            )

        self.add_item(
            CategoryPageButton(-1, disabled=self.category_page == 0)
        )
        for reference in REFERENCE_CURRENCIES:
            self.add_item(
                ReferenceCurrencyButton(
                    reference,
                    selected=reference == self.reference_currency,
                    available=reference in self.available_references,
                )
            )
        self.add_item(
            CategoryPageButton(
                1,
                disabled=self.category_page >= self.total_pages - 1,
            )
        )

    def create_embed(self) -> discord.Embed:
        return create_menu_embed(
            self.snapshots,
            self.groups,
            self.reference_currency,
            self.category_page,
        )

    async def change_category_page(
        self,
        interaction: discord.Interaction,
        direction: int,
    ) -> None:
        view = CategoryMenuView(
            self.owner_id,
            self.snapshots,
            self.reference_currency,
            category_page=self.category_page + direction,
        )
        self.stop()
        await interaction.response.edit_message(embed=view.create_embed(), view=view)

    async def change_reference(
        self,
        interaction: discord.Interaction,
        reference_currency: str,
    ) -> None:
        view = CategoryMenuView(
            self.owner_id,
            self.snapshots,
            reference_currency,
            category_page=self.category_page,
        )
        self.stop()
        await interaction.response.edit_message(embed=view.create_embed(), view=view)

    async def show_category(
        self,
        interaction: discord.Interaction,
        group: CategoryGroup,
    ) -> None:
        view = MarketPageView(
            self.owner_id,
            self.snapshots,
            group,
            self.reference_currency,
            category_page=self.category_page,
        )
        self.stop()
        await interaction.response.edit_message(embed=view.create_embed(), view=view)


class BackToCategoriesButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            label="Categories",
            style=discord.ButtonStyle.secondary,
            row=0,
            custom_id="market:items:back",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, MarketPageView):
            await view.back_to_categories(interaction)


class ItemPageButton(discord.ui.Button):
    def __init__(self, direction: int, *, disabled: bool) -> None:
        super().__init__(
            label="◀" if direction < 0 else "▶",
            style=discord.ButtonStyle.secondary,
            row=0,
            disabled=disabled,
            custom_id=f"market:items:{'previous' if direction < 0 else 'next'}",
        )
        self.direction = direction

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, MarketPageView):
            await view.change_item_page(interaction, self.direction)


class MarketPageView(OwnedView):
    def __init__(
        self,
        owner_id: int,
        snapshots: Sequence[ExchangeSnapshot],
        group: CategoryGroup,
        reference_currency: str,
        *,
        category_page: int,
        item_page: int = 0,
    ) -> None:
        super().__init__(owner_id)
        self.snapshots = tuple(snapshots)
        self.group = group
        self.reference_currency = reference_currency
        self.category_page = category_page

        record_count = len(
            _records_for_category(
                self.snapshots[0],
                self.group,
                self.reference_currency,
            )
        )
        self.total_pages = max(1, math.ceil(record_count / ITEM_PAGE_SIZE))
        self.item_page = min(max(item_page, 0), self.total_pages - 1)

        self.add_item(BackToCategoriesButton())
        self.add_item(ItemPageButton(-1, disabled=self.item_page == 0))
        self.add_item(
            discord.ui.Button(
                label=f"{self.item_page + 1}/{self.total_pages}",
                style=discord.ButtonStyle.secondary,
                row=0,
                disabled=True,
            )
        )
        self.add_item(
            ItemPageButton(
                1,
                disabled=self.item_page >= self.total_pages - 1,
            )
        )
        self.add_item(
            discord.ui.Button(
                label=reference_currency.title(),
                style=discord.ButtonStyle.primary,
                row=0,
                disabled=True,
            )
        )

    def create_embed(self) -> discord.Embed:
        embed, normalised_page, _ = create_category_embed(
            self.snapshots,
            self.group,
            self.reference_currency,
            self.item_page,
        )
        self.item_page = normalised_page
        return embed

    async def change_item_page(
        self,
        interaction: discord.Interaction,
        direction: int,
    ) -> None:
        view = MarketPageView(
            self.owner_id,
            self.snapshots,
            self.group,
            self.reference_currency,
            category_page=self.category_page,
            item_page=self.item_page + direction,
        )
        self.stop()
        await interaction.response.edit_message(embed=view.create_embed(), view=view)

    async def back_to_categories(
        self,
        interaction: discord.Interaction,
    ) -> None:
        view = CategoryMenuView(
            self.owner_id,
            self.snapshots,
            self.reference_currency,
            category_page=self.category_page,
        )
        self.stop()
        await interaction.response.edit_message(embed=view.create_embed(), view=view)


class PaginationTest:
    def __init__(
        self,
        client: commands.Bot,
        snapshot_reader: R2SnapshotReader | None = None,
    ) -> None:
        self.client = client
        self.snapshot_reader = snapshot_reader
        self.register_command()

    def register_command(self) -> None:
        @self.client.tree.command(
            name="market-menu",
            description="Browse PoE2 market snapshot prices by category",
        )
        async def market_menu(
            interaction: discord.Interaction,
        ) -> None:
            await interaction.response.defer(thinking=True)
            reference_currency = "exalted"

            try:
                if self.snapshot_reader is None:
                    self.snapshot_reader = R2SnapshotReader.from_env(
                        cache_ttl_seconds=60
                    )
                snapshots = await asyncio.to_thread(
                    self.snapshot_reader.load_latest_snapshots,
                    2,
                )
            except SnapshotConfigurationError as exc:
                logger.error("R2 snapshot reader is not configured: %s", exc)
                await interaction.followup.send(
                    f"The R2 snapshot reader is not ready: {exc}",
                    ephemeral=True,
                )
                return
            except SnapshotReaderError:
                logger.exception("Could not load market snapshots from R2")
                await interaction.followup.send(
                    "I could not load a consolidated exchange snapshot from R2. "
                    "Check the bot logs for the storage error.",
                    ephemeral=True,
                )
                return

            groups = discover_category_groups(snapshots[0].records)
            if not groups:
                await interaction.followup.send(
                    "The newest snapshot contains no item categories.",
                    ephemeral=True,
                )
                return

            available_references = available_reference_currencies(
                snapshots[0].records
            )
            if reference_currency not in available_references:
                fallback = next(
                    (
                        reference
                        for reference in REFERENCE_CURRENCIES
                        if reference in available_references
                    ),
                    None,
                )
                if fallback is None:
                    await interaction.followup.send(
                        "The newest snapshot contains no reference currencies.",
                        ephemeral=True,
                    )
                    return
                reference_currency = fallback

            view = CategoryMenuView(
                interaction.user.id,
                snapshots,
                reference_currency,
            )
            await interaction.followup.send(embed=view.create_embed(), view=view)


__all__ = [
    "CategoryGroup",
    "PaginationTest",
    "calculate_price_change",
    "create_category_embed",
    "discover_category_groups",
]
