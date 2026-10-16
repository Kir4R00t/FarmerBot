from datetime import timedelta
import math
import unittest

from bot.commands import pagination_test as market
from bot.services.market_movers import rank_market_movers
from tests.support import NOW, interaction, record, snapshot


def observations(current, previous):
    return (snapshot(*current), snapshot(*previous, captured_at=NOW - timedelta(hours=1)))


class MarketMoverRankingTests(unittest.TestCase):
    def rank(self, current, previous, **kwargs):
        return rank_market_movers(observations(current, previous), "exalted", **kwargs)

    def test_gainers_and_losers_sort_by_signed_change(self):
        current = [record(api_id="up", name="Up", current_price=20, current_quantity=123),
                   record(api_id="down", name="Down", current_price=5, current_quantity=7),
                   record(api_id="flat", current_price=10), record(api_id="zero", current_price=0)]
        previous = [r | {"current_price": 10} for r in current]
        gainers = self.rank(current, previous)
        self.assertEqual([m.record["api_id"] for m in gainers], ["up"])
        self.assertEqual((gainers[0].current_price, gainers[0].previous_price, gainers[0].change_percent, gainers[0].quantity), (20, 10, 100, 123))
        losers = self.rank(current, previous, direction="losers")
        self.assertEqual([m.change_percent for m in losers], [-100, -50])
        self.assertEqual([m.record["api_id"] for m in losers], ["zero", "down"])

    def test_tied_changes_use_names_then_identifiers(self):
        rows = [record(name="Z", api_id="z", current_price=20), record(name="A", api_id="b", current_price=20),
                record(name="A", api_id="a", current_price=20)]
        ranked = self.rank(rows, [r | {"current_price": 10} for r in rows])
        self.assertEqual([m.record["api_id"] for m in ranked], ["a", "b", "z"])

    def test_filters_missing_invalid_and_nonpositive_history(self):
        old = record(current_price=10)
        for current, previous in ((record(current_price=None), old), (record(current_price="bad"), old),
                                  (record(current_price=-1), old), (record(current_price=True), old),
                                  (record(current_price=float("inf")), old),
                                  (record(current_price=20), record(current_price=0)),
                                  (record(current_price=20), record(current_price=-1)),
                                  (record(current_price=20), record(current_price=None)),
                                  (record(current_price=1e308), record(current_price=1e-308))):
            with self.subTest(current=current, previous=previous):
                self.assertEqual(self.rank([current], [previous]), ())
        self.assertEqual(self.rank([record(current_price=20)], []), ())
        self.assertEqual(self.rank([record(current_price=10.00001)], [old]), ())
        self.assertEqual(self.rank([record(current_price=9.99999)], [old], direction="losers"), ())

    def test_identity_never_matches_other_leagues_realms_categories_or_references(self):
        current = record(current_price=20, realm="poe2", league="Test")
        previous = current | {"current_price": 10}
        for field, value in (("realm", "other"), ("league", "other"), ("category", "other"),
                             ("reference_currency", "divine"), ("api_id", "different"), ("item_kind", "unique")):
            with self.subTest(field=field):
                self.assertEqual(self.rank([current], [previous | {field: value}]), ())
        self.assertEqual(self.rank([record(api_id="exalted", current_price=2)], [record(api_id="exalted", current_price=1)]), ())
        self.assertEqual(self.rank([record(api_id="", name="", current_price=20)], [record(current_price=10)]), ())

    def test_duplicate_identities_are_excluded_in_either_snapshot(self):
        new, old = record(current_price=20), record(current_price=10)
        self.assertEqual(self.rank([new, new], [old]), ())
        self.assertEqual(self.rank([new], [old, old]), ())

    def test_unique_name_fallback_and_numeric_strings(self):
        current = record(item_kind="unique", api_id="123", name="Sword", current_price="20")
        previous = current | {"api_id": "", "name": "sword", "current_price": "10"}
        self.assertEqual(self.rank([current], [previous]), ())
        self.assertEqual(self.rank([current], [previous], item_kind="unique")[0].change_percent, 100)
        current = record(api_id="", name="Sword", current_price=20)
        self.assertEqual(self.rank([current], [current | {"current_price": 10}])[0].change_percent, 100)

    def test_quantity_is_reported_without_volume_inference_or_minimum(self):
        for value, expected in ((0, 0), (1, 1), (1234, 1234), (10**18 + 1, 10**18 + 1), ("123", 123), (None, None),
                                (True, None), (-1, None), (1.5, None), (float("nan"), None), ({}, None)):
            with self.subTest(value=value):
                mover = self.rank([record(current_price=20, current_quantity=value)], [record(current_price=10)])[0]
                self.assertEqual(mover.quantity, expected)

    def test_snapshots_must_have_an_older_comparison(self):
        self.assertEqual(rank_market_movers([], "exalted"), ())
        self.assertEqual(rank_market_movers([snapshot(record())], "exalted"), ())
        self.assertEqual(rank_market_movers([snapshot(record()), snapshot(record())], "exalted"), ())
        reversed_snapshots = list(reversed(observations([record()], [record()])))
        self.assertEqual(rank_market_movers(reversed_snapshots, "exalted"), ())
        with self.assertRaises(ValueError):
            rank_market_movers([], "exalted", direction="sideways")
        with self.assertRaises(ValueError):
            rank_market_movers([], "exalted", item_kind="other")


class MarketMoverEmbedTests(unittest.TestCase):
    def data(self, count=16):
        current = [record(api_id=f"item-{i}", name="Item " + str(i), current_price=20 + i, current_quantity=1234567) for i in range(count)]
        return observations(current, [r | {"current_price": 10} for r in current])

    def test_table_has_signed_percent_price_quantity_and_consistent_columns(self):
        embed, page, pages = market.create_movers_embed(self.data(), "exalted", "gainers", "currency", 0)
        self.assertEqual((page, pages), (0, 2))
        lines = embed.description.splitlines()
        self.assertEqual(len(lines), 16)  # Header plus fifteen items.
        cells = [line.split("`")[1] for line in lines]
        self.assertEqual(len({len(cell) for cell in cells}), 1)
        for name in ("Item", "Price", "Change", "Qty"):
            self.assertIn(name, cells[0])
        self.assertIn("+250.00%", cells[1])
        self.assertIn("1,234,567", cells[1])
        self.assertIn("35", cells[1])
        self.assertIn(market.EMOJIS["green-up"], lines[1])
        self.assertIn("not available", next(f.value for f in embed.fields if f.name == "Qty"))
        self.assertIn("Collection interval: 1h", next(f.value for f in embed.fields if f.name == "Comparison"))
        last, page, pages = market.create_movers_embed(self.data(), "exalted", "gainers", "currency", 999)
        self.assertEqual((page, pages), (1, 2))
        self.assertEqual(len(last.description.splitlines()), 2)
        self.assertEqual(len(last.description.splitlines()[1].split("`")[1]), len(cells[1]))
        self.assertIn("Items 16–16 of 16", last.footer.text)

    def test_losers_and_missing_quantity(self):
        data = observations([record(current_price=5)], [record(current_price=10)])
        embed, _, _ = market.create_movers_embed(data, "exalted", "losers", "currency", -1)
        self.assertIn("-50.00%", embed.description)
        self.assertIn(market.EMOJIS["red-down"], embed.description)
        self.assertIn("—", embed.description)

    def test_prices_and_changes_use_fixed_reference_without_divine_conversion(self):
        data = observations([record(current_price=200), record(api_id="divine", current_price=100)],
                            [record(current_price=100), record(api_id="divine", current_price=50)])
        embed, _, _ = market.create_movers_embed(data, "exalted", "gainers", "currency", 0)
        self.assertIn("200", embed.description)
        self.assertIn("+100.00%", embed.description)
        self.assertIn("Exalted", embed.fields[0].value)

    def test_empty_and_insufficient_history_messages(self):
        for data, expected in (([snapshot(record())], "second, older snapshot"),
                               ([snapshot(record()), snapshot(record())], "second, older snapshot"),
                               (observations([record()], [record()]), "No gainers")):
            with self.subTest(data=data):
                embed, page, pages = market.create_movers_embed(data, "exalted", "gainers", "currency", 0)
                self.assertIn(expected, embed.description)
                self.assertEqual((page, pages), (0, 1))
                self.assertIn("Items 0–0 of 0", embed.footer.text)

    def test_long_names_extreme_numbers_and_backticks_fit_discord_limits(self):
        new = [record(api_id=f"item-{i}", name="`" + "X" * 200 + "\n", current_price=1e100, current_quantity=10**10) for i in range(15)]
        old = [r | {"current_price": 1} for r in new]
        embed, _, _ = market.create_movers_embed(observations(new, old), "exalted", "gainers", "currency", 0)
        self.assertIn("…", embed.description)
        self.assertIn("+1e+102%", embed.description)
        self.assertIn("1e+10", embed.description)
        self.assertLessEqual(len(embed.description), 4096)
        self.assertLessEqual(len(embed), 6000)
        self.assertEqual(len(embed.description.splitlines()), 16)
        self.assertTrue(all(line.count("`") == 2 for line in embed.description.splitlines()))


class MarketMoverViewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        current = [record(api_id=f"item-{i}", current_price=20 + i, category=f"cat-{i}") for i in range(17)]
        current += [record(api_id="annul", reference_currency="chaos", current_price=5), record(item_kind="unique", current_price=20)]
        previous = [r | {"current_price": 10} for r in current]
        self.data = observations(current, previous)
        self.views = []
        self.addCleanup(self.cleanup_views)

    def cleanup_views(self):
        for view in self.views:
            view.stop()

    def keep(self, view):
        self.views.append(view)
        return view

    def button(self, view, setting, value):
        return next(c for c in view.children if isinstance(c, market.MoversButton) and c.setting == setting and c.value == value)

    async def click(self, button):
        inter = interaction()
        await button.callback(inter)
        view = self.keep(inter.response.edit_message.call_args.kwargs["view"])
        self.assertLessEqual(len(view.children), 25)
        for row in range(5):
            self.assertLessEqual(sum(c.row == row for c in view.children), 5)
        return view

    async def test_menu_opens_both_rankings_and_disables_when_no_history(self):
        for direction in ("gainers", "losers"):
            menu = self.keep(market.CategoryMenuView(42, self.data, "exalted", category_page=1))
            button = next(c for c in menu.children if isinstance(c, market.OpenMoversButton) and c.direction == direction)
            self.assertFalse(button.disabled)
            view = await self.click(button)
            self.assertEqual(view.direction, direction)
            self.assertEqual(view.category_page, 1)
            self.assertTrue(menu.is_finished())
        one = self.keep(market.CategoryMenuView(42, self.data[:1], "exalted"))
        self.assertTrue(all(c.disabled for c in one.children if isinstance(c, market.OpenMoversButton)))

    async def test_page_direction_kind_reference_and_back_navigation(self):
        view = self.keep(market.MarketMoversView(42, self.data, "exalted", category_page=1))
        self.assertTrue(self.button(view, "item_page", -1).disabled)
        self.assertTrue(self.button(view, "direction", "gainers").disabled)
        last = await self.click(self.button(view, "item_page", 1))
        self.assertEqual(last.item_page, 1)
        self.assertTrue(self.button(last, "item_page", 2).disabled)
        first = await self.click(self.button(last, "item_page", 0))
        self.assertEqual(first.item_page, 0)
        losers = await self.click(self.button(last, "direction", "losers"))
        self.assertEqual((losers.direction, losers.item_page), ("losers", 0))
        uniques = await self.click(self.button(view, "item_kind", "unique"))
        self.assertEqual(uniques.item_kind, "unique")
        currency = await self.click(self.button(uniques, "item_kind", "currency"))
        self.assertEqual(currency.item_kind, "currency")
        chaos = await self.click(self.button(view, "reference_currency", "chaos"))
        self.assertEqual(chaos.reference_currency, "chaos")
        self.assertIn("-50.00%", (await self.click(self.button(chaos, "direction", "losers"))).create_embed().description)
        self.assertTrue(self.button(chaos, "reference_currency", "divine").disabled)
        back = await self.click(self.button(chaos, "back", ""))
        self.assertIsInstance(back, market.CategoryMenuView)
        self.assertEqual((back.category_page, back.reference_currency), (1, "chaos"))
        other = interaction(43)
        self.assertFalse(await view.interaction_check(other))
        other.response.send_message.assert_awaited_once()

    async def test_single_snapshot_view_and_detached_buttons(self):
        view = self.keep(market.MarketMoversView(42, self.data[:1], "exalted"))
        self.assertIn("second, older snapshot", view.create_embed().description)
        inter = interaction()
        await market.OpenMoversButton("gainers", disabled=False).callback(inter)
        await market.MoversButton("Back", "back", "", row=0).callback(inter)
        inter.response.edit_message.assert_not_awaited()
