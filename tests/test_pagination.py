from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import Mock, patch

import discord

from bot.commands import pagination as market
from bot.services.r2_snapshot_reader import SnapshotConfigurationError, SnapshotStorageError
from tests.support import NOW, bot, interaction, record, snapshot, run_in_test_thread


class MarketDataTests(unittest.TestCase):
    def test_price_change_handles_direction_zero_and_invalid_values(self):
        for current, previous, expected in ((15, 10, 50), (5, 10, -50), (10, 10, 0), (0, 10, -100),
                                            ("12", "10", 20), (1, 0, None), (1, -1, None),
                                            (True, 1, None), (None, 1, None), ("bad", 1, None),
                                            (float("inf"), 1, None), (1, float("nan"), None), ({}, 1, None)):
            with self.subTest(current=current, previous=previous):
                self.assertEqual(market.calculate_price_change(current, previous), expected)

    def test_discovery_deduplicates_labels_and_orders_currency_first(self):
        groups = market.discover_category_groups([
            record(category="uncutgems"), record(category="uncutgems"),
            record(category="uncutgems", item_kind="unique"), record(category=""),
            record(category="soul_cores"), record(category="", item_kind="")])
        self.assertEqual([(g.item_kind, g.label) for g in groups], [
            ("currency", "Soul Cores"), ("currency", "Uncut Gems (Currency)"),
            ("unique", "Uncut Gems (Unique)")])
        self.assertEqual(market.available_reference_currencies([record(), {}, record(reference_currency=" chaos ")]), {"exalted", "chaos"})

    def test_price_formatting_preserves_readable_magnitudes(self):
        for value, expected in ((1e9, "1e+09"), (1234.5, "1,234.5"), (12, "12"),
                                (0.01234, "0.0123"), (0.000123, "0.000123"), (0, "0"), (-5, "-5")):
            with self.subTest(value=value):
                self.assertEqual(market._format_price(value), expected)

    def test_timestamp_and_age_summaries(self):
        self.assertIsNone(market._parse_optional_timestamp("bad"))
        self.assertIsNone(market._parse_optional_timestamp(None))
        self.assertEqual(market._parse_optional_timestamp("2026-10-16T12:00:00"), NOW)
        self.assertEqual(market._parse_optional_timestamp("2026-10-16T14:00:00+02:00"), NOW)
        for seconds, expected in ((-1, "<1m"), (60, "1m"), (3600, "1h"), (3660, "1h 1m"),
                                  (86400, "1d"), (90000, "1d 1h")):
            self.assertEqual(market._format_duration(seconds), expected)
        records = [record(), record(price_observed_at="2026-10-16T10:00:00Z")]
        summary = market._staleness_summary(records, NOW, now=NOW.replace(tzinfo=None))
        self.assertIn("1h to 2h old", summary)
        self.assertIn("1h old", market._staleness_summary([record()], NOW, now=NOW))
        self.assertEqual(market._observed_at_summary([]), "Not recorded")
        self.assertEqual(market._staleness_summary([], NOW), "Not recorded in this snapshot")
        self.assertIn(" – ", market._observed_at_summary(records))

    def test_filters_invalid_prices_reference_items_and_other_categories(self):
        group = market.CategoryGroup("currency", "currency", "Currency")
        records = [record(name="B", current_price=2), record(name="A", current_price=2),
                   record(name="High", current_price=20), record(api_id="exalted"),
                   record(current_price="bad"), record(category="other"),
                   record(item_kind="unique"), record(reference_currency="chaos")]
        filtered = market._records_for_category(snapshot(*records), group, "exalted")
        self.assertEqual([r["name"] for r in filtered], ["High", "A", "B"])

    def test_emoji_and_currency_fallbacks(self):
        self.assertEqual(market._item_emoji(record(api_id="unknown", name="Chaos")), market.EMOJIS["chaos"])
        self.assertEqual(market._item_emoji(record(api_id="unknown", name="Unknown")), "📦")
        self.assertEqual(market._currency_marker("unknown"), "Unknown")
        self.assertEqual(market._humanise_identifier(""), "Unknown")

    def test_unique_and_non_exchange_rows_have_no_item_emoji_or_placeholder(self):
        for kind, category, api_id, name in (
            ('unique', 'jewel', 'against-the-darkness', 'Against the Darkness'),
            ('unique', 'accessory', 'headhunter', 'Headhunter'),
            ('currency', 'waystones', 'waystone-1', 'Waystone'),
            ('currency', 'currency', 'sep', 'Currency'),
        ):
            with self.subTest(category=category):
                item = record(item_kind=kind, category=category, api_id=api_id, name=name)
                self.assertEqual(market._item_emoji(item), '')
                embed, _, _ = market.create_category_embed(
                    [snapshot(item)], market.CategoryGroup(kind, category, category.title()), 'exalted', 0,
                )
                self.assertTrue(embed.description.startswith('`' + name))
                self.assertNotIn('📦', embed.description)

    def test_category_embeds_compare_in_the_displayed_currency(self):
        group = market.CategoryGroup("unique", "weapons", "Weapons")
        current = snapshot(record(api_id="divine", current_price=100),
                           record(item_kind="unique", category="weapons", name="*Sword*", current_price=200))
        previous = snapshot(record(api_id="divine", current_price=50),
                            record(item_kind="unique", category="weapons", name="*Sword*", current_price=100))
        embed, page, count = market.create_category_embed([current, previous], group, "exalted", 100)
        self.assertEqual((page, count), (0, 1))
        self.assertIn("*Sword*  2`", embed.description)
        self.assertIn("`0.00%`", embed.description)  # 2 divines in both snapshots.
        self.assertIn("`*Sword*", embed.description)
        self.assertIn("Compared with", [f.name for f in embed.fields])
        no_rate, _, _ = market.create_category_embed([current, snapshot()], group, "exalted", 0)
        self.assertIn("— `---`", no_rate.description)

    def test_category_embeds_show_increase_decrease_and_missing_history(self):
        group = market.CategoryGroup("currency", "currency", "Currency")
        for old, new, expected in ((10, 15, "+50.00%"), (10, 5, "-50.00%"), (10, 10, "0.00%")):
            with self.subTest(old=old, new=new):
                embed, _, _ = market.create_category_embed([snapshot(record(current_price=new)), snapshot(record(current_price=old))], group, "exalted", 0)
                self.assertIn(expected, embed.description)
        embed, _, _ = market.create_category_embed([snapshot(record())], group, "exalted", 0)
        self.assertIn("— `---`", embed.description)
        empty, page, pages = market.create_category_embed([snapshot()], group, "divine", -1)
        self.assertIn("No priced items", empty.description)
        self.assertEqual((page, pages), (0, 1))
        self.assertIn("Items 0–0 of 0", empty.footer.text)

    def test_category_pagination_clamps_and_shows_last_page(self):
        records = [record(name=f"Item {i}", api_id=f"item-{i}", current_price=i + 1) for i in range(16)]
        embed, page, pages = market.create_category_embed([snapshot(*records)], market.CategoryGroup("currency", "currency", "Currency"), "exalted", 99)
        self.assertEqual((page, pages), (1, 2))
        self.assertIn("Items 16–16 of 16", embed.footer.text)
        self.assertIn("Item 0", embed.description)
        self.assertNotIn("Item 15", embed.description)

    def test_table_aligns_names_and_prices_with_emojis_outside_code(self):
        group = market.CategoryGroup("currency", "currency", "Currency")
        data = snapshot(
            record(name="Chaos Orb", current_price=39.84),
            record(api_id="annul", name="Orb of Annulment", current_price=5),
        )
        embed, _, _ = market.create_category_embed([data], group, "exalted", 0)
        lines = embed.description.splitlines()
        self.assertEqual(lines[0].split("`")[1], "Chaos Orb         39.84")
        self.assertEqual(lines[1].split("`")[1], "Orb of Annulment      5")
        # A single monospace span contains both columns; custom emojis render
        # outside it, as they do in the original command.
        self.assertTrue(lines[0].startswith(market.EMOJIS["chaos"] + " `"))
        self.assertIn("` " + market.EMOJIS["exalted"], lines[0])
        self.assertNotIn("**", embed.description)
        self.assertIn("Currency Pricing", embed.title)

    def test_table_columns_stay_the_same_width_across_pages(self):
        group = market.CategoryGroup("currency", "currency", "Currency")
        data = snapshot(
            record(name="The longest name is on the last page", current_price=0.5),
            *(record(name=f"Item {i}", api_id=f"item-{i}", current_price=100 + i) for i in range(15)),
        )
        first, _, _ = market.create_category_embed([data], group, "exalted", 0)
        last, _, _ = market.create_category_embed([data], group, "exalted", 1)
        cells = [line.split("`")[1] for line in (first.description + "\n" + last.description).splitlines()]
        self.assertEqual(len({len(cell) for cell in cells}), 1)
        self.assertIn("The longest name is on the last page", cells[-1])

    def test_missing_core_icons_reserve_an_emoji_before_the_table(self):
        group = market.CategoryGroup('currency', 'ultimatum', 'Soul Cores')
        data = snapshot(
            record(category='ultimatum', api_id='unknown-soul-core', name='Unknown Soul Core'),
            record(category='ultimatum', api_id='uromotis-soul-core-of-attenuation', name="Uromoti's Soul Core of Attenuation"),
        )
        embed, _, _ = market.create_category_embed([data], group, 'exalted', 0)
        lines = embed.description.splitlines()
        self.assertTrue(lines[0].startswith('📦 `'))
        self.assertTrue(lines[1].startswith(market.EMOJIS['uromotis-soul-core-of-attenuation'] + ' `'))
        self.assertEqual(len(lines[0].split('`')[1]), len(lines[1].split('`')[1]))

    def test_table_names_cannot_break_rows_or_inline_code(self):
        group = market.CategoryGroup("unique", "weapons", "Weapons")
        data = snapshot(
            record(item_kind="unique", category="weapons", name="  Sword`\nwith\ttabs  "),
            record(item_kind="unique", category="weapons", name="X" * 200),
            record(item_kind="unique", category="weapons", name="", api_id="test-sword"),
            record(item_kind="unique", category="weapons", name="", api_id=""),
        )
        embed, _, _ = market.create_category_embed([data], group, "exalted", 0)
        self.assertEqual(len(embed.description.splitlines()), 4)
        self.assertIn("Sword' with tabs", embed.description)
        self.assertIn("X" * 39 + "…", embed.description)
        self.assertNotIn("X" * 40, embed.description)
        self.assertIn("test sword", embed.description)
        self.assertIn("Unknown", embed.description)
        for line in embed.description.splitlines():
            self.assertEqual(line.count("`"), 4)
        self.assertLessEqual(len(embed.description), 4096)

    def test_full_page_of_long_names_fits_embed_description(self):
        group = market.CategoryGroup("unique", "weapons", "Weapons")
        data = snapshot(*(record(item_kind="unique", category="weapons", name="X" * 200,
                                 current_price=1e9, api_id=f"item-{i}") for i in range(15)))
        embed, _, _ = market.create_category_embed([data], group, "exalted", 0)
        self.assertEqual(len(embed.description.splitlines()), 15)
        self.assertLessEqual(len(embed.description), 4096)

    def test_invalid_divine_rates_do_not_convert_prices(self):
        data = snapshot(record(api_id="divine", current_price=0), record(api_id="divine", current_price="bad"))
        self.assertIsNone(market._divine_multiplier(data, "exalted"))

    def test_menu_embeds_with_and_without_history(self):
        for snapshots, expected in (([snapshot(record())], "second snapshot"),
                                    ([snapshot(record()), snapshot(record())], "previous snapshot")):
            embed = market.create_menu_embed(snapshots, [], "exalted", 0)
            self.assertEqual(embed.title, "PoE2 Market Categories")
            self.assertIn(expected, embed.fields[1].value)
            self.assertIn("Category page 1/1", embed.footer.text)


class MarketViewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.data = [snapshot(*(record(category=f"category-{i}") for i in range(21)))]
        self.addAsyncCleanup(self.stop_views)
        self.views = []

    async def stop_views(self):
        for view in self.views:
            view.stop()

    def keep(self, view):
        self.views.append(view)
        return view

    async def test_only_owner_can_use_browser(self):
        view = self.keep(market.OwnedView(42))
        self.assertTrue(await view.interaction_check(interaction(42)))
        other = interaction(43)
        self.assertFalse(await view.interaction_check(other))
        other.response.send_message.assert_awaited_once()
        self.assertTrue(other.response.send_message.call_args.kwargs["ephemeral"])

    async def test_category_navigation_reference_change_and_selection(self):
        menu = self.keep(market.CategoryMenuView(42, self.data, "exalted"))
        self.assertLessEqual(len(menu.children), 25)
        self.assertEqual(sum(isinstance(c, market.CategoryButton) for c in menu.children), market.CATEGORY_PAGE_SIZE)
        previous = next(c for c in menu.children if isinstance(c, market.CategoryPageButton) and c.direction == -1)
        self.assertTrue(previous.disabled)
        references = {c.reference_currency: c for c in menu.children if isinstance(c, market.ReferenceCurrencyButton)}
        self.assertTrue(references["exalted"].disabled)
        self.assertTrue(references["chaos"].disabled)
        inter = interaction()
        await menu.children[-1].callback(inter)
        next_menu = self.keep(inter.response.edit_message.call_args.kwargs["view"])
        self.assertEqual(next_menu.category_page, 1)
        self.assertTrue(menu.is_finished())
        previous = next(c for c in next_menu.children if isinstance(c, market.CategoryPageButton) and c.direction == -1)
        await previous.callback(inter)
        self.assertEqual(self.keep(inter.response.edit_message.call_args.kwargs["view"]).category_page, 0)
        await next_menu.change_reference(inter, "chaos")
        changed = self.keep(inter.response.edit_message.call_args.kwargs["view"])
        self.assertEqual(changed.reference_currency, "chaos")
        await next_menu.children[0].callback(inter)
        items = self.keep(inter.response.edit_message.call_args.kwargs["view"])
        self.assertIsInstance(items, market.MarketPageView)
        self.assertEqual(items.category_page, 1)
        await items.children[0].callback(inter)
        returned = self.keep(inter.response.edit_message.call_args.kwargs["view"])
        self.assertEqual(returned.category_page, 1)

    async def test_detached_buttons_do_not_edit_messages(self):
        group = market.CategoryGroup("currency", "currency", "Currency")
        buttons = [market.CategoryButton(group, row=0, index=0),
                   market.CategoryPageButton(1, disabled=False),
                   market.ReferenceCurrencyButton("chaos", selected=False, available=True),
                   market.BackToCategoriesButton(), market.ItemPageButton(1, disabled=False)]
        inter = interaction()
        for button in buttons:
            await button.callback(inter)
        inter.response.edit_message.assert_not_awaited()

    async def test_reference_button_and_item_buttons_dispatch(self):
        data = [snapshot(*(record(api_id=f"item-{i}") for i in range(16)), record(reference_currency="chaos"))]
        menu = self.keep(market.CategoryMenuView(42, data, "exalted"))
        inter = interaction()
        chaos = next(c for c in menu.children if isinstance(c, market.ReferenceCurrencyButton) and c.reference_currency == "chaos")
        self.assertFalse(chaos.disabled)
        await chaos.callback(inter)
        self.assertEqual(self.keep(inter.response.edit_message.call_args.kwargs["view"]).reference_currency, "chaos")
        items = self.keep(market.MarketPageView(42, data, menu.groups[0], "exalted", category_page=0))
        self.assertTrue(items.children[1].disabled)
        await items.children[3].callback(inter)
        last = self.keep(inter.response.edit_message.call_args.kwargs["view"])
        self.assertEqual(last.item_page, 1)
        self.assertTrue(last.children[3].disabled)
        await last.children[1].callback(inter)
        first = self.keep(inter.response.edit_message.call_args.kwargs["view"])
        self.assertEqual(first.item_page, 0)


class MarketCommandTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        offload = patch.object(market.asyncio, "to_thread", side_effect=run_in_test_thread)
        self.offload = offload.start()
        self.addCleanup(offload.stop)
        self.client = bot()
        self.addAsyncCleanup(self.client.close)
        self.reader = Mock()
        self.command = market.Pagination(self.client, self.reader)
        self.callback = self.client.tree.get_command("market-menu").callback

    async def test_success_loads_two_snapshots_and_sends_menu(self):
        self.reader.load_latest_snapshots.return_value = (snapshot(record()),)
        inter = interaction()
        await self.callback(inter)
        inter.response.defer.assert_awaited_once_with(thinking=True)
        self.reader.load_latest_snapshots.assert_called_once_with(2)
        view = inter.followup.send.call_args.kwargs["view"]
        self.addCleanup(view.stop)
        self.assertEqual(view.owner_id, 42)
        self.assertEqual(view.reference_currency, "exalted")
        self.assertEqual(inter.followup.send.call_args.kwargs["embed"].title, "PoE2 Market Categories")

    async def test_missing_configuration_and_storage_failure(self):
        for error, message in ((SnapshotConfigurationError("missing config"), "not ready"),
                               (SnapshotStorageError("offline"), "could not load")):
            with self.subTest(error=error), self.assertLogs(market.logger, level="ERROR"):
                self.reader.load_latest_snapshots.side_effect = error
                inter = interaction()
                await self.callback(inter)
                self.assertIn(message, inter.followup.send.call_args.args[0])
                self.assertTrue(inter.followup.send.call_args.kwargs["ephemeral"])

    async def test_lazy_reader_initialisation_and_reference_fallback(self):
        self.command.snapshot_reader = None
        self.reader.load_latest_snapshots.return_value = (snapshot(record(reference_currency="chaos")),)
        with patch.object(market.R2SnapshotReader, "from_env", return_value=self.reader) as factory:
            inter = interaction()
            await self.callback(inter)
            factory.assert_called_once_with(cache_ttl_seconds=60)
        view = inter.followup.send.call_args.kwargs["view"]
        self.addCleanup(view.stop)
        self.assertEqual(view.reference_currency, "chaos")

    async def test_empty_categories_and_unsupported_reference(self):
        for records, expected in (([{}], "no item categories"), ([record(reference_currency="unknown")], "no reference currencies")):
            with self.subTest(records=records):
                self.reader.load_latest_snapshots.return_value = (snapshot(*records),)
                inter = interaction()
                await self.callback(inter)
                self.assertIn(expected, inter.followup.send.call_args.args[0])
                self.assertTrue(inter.followup.send.call_args.kwargs["ephemeral"])
