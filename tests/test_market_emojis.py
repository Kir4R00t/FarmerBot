import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bot.commands import pagination_test
from bot.commands.poe2scout import CurrencyExchange
from bot.util import emoji_loader


class EmojiLoaderTests(unittest.TestCase):
    def test_loads_packaged_mapping_outside_project_directory(self):
        original_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                emojis = emoji_loader.load_item_emojis()
            finally:
                os.chdir(original_directory)
        for name in ("divine", "exalted", "chaos", "green-up", "red-down"):
            self.assertIsInstance(emojis[name], str)
        self.assertEqual(pagination_test.EMOJIS, emojis)

    def test_rejects_invalid_mapping_shapes(self):
        with tempfile.TemporaryDirectory() as directory:
            loader_path = Path(directory) / "emoji_loader.py"
            json_path = loader_path.with_name("item_emojis.json")
            for value in ([], {"exalted": 123}):
                with self.subTest(value=value):
                    json_path.write_text(json.dumps(value))
                    with patch.object(emoji_loader, "__file__", str(loader_path)):
                        with self.assertRaisesRegex(ValueError, "mapping names to strings"):
                            emoji_loader.load_item_emojis()


class MarketEmbedTests(unittest.TestCase):
    def setUp(self):
        # Register no Discord commands and perform no network requests.
        with patch.object(CurrencyExchange, "market_command"):
            self.exchange = CurrencyExchange(None)
        self.multiplier = patch.object(
            self.exchange, "calculate_div_multiplier", return_value=100
        )
        self.multiplier.start()
        self.addCleanup(self.multiplier.stop)
        self.reference = SimpleNamespace(value="exalted")
        self.category = SimpleNamespace(value="currency", name="Currency")

    def item(self, name):
        return {"ApiId": name, "CurrentPrice": 5, "PriceLogs": []}

    def test_empty_and_fully_filtered_results_show_empty_message(self):
        cases = (
            ("currency", []),
            ("currency", [self.item("exalted")]),
            ("currency", [self.item("unknown-item-without-emoji")]),
            ("essences", [self.item("lesser-essence"), self.item("greater-essence")]),
        )
        for category, items in cases:
            with self.subTest(category=category, items=items):
                self.category.value = category
                embed = self.exchange.create_embed(
                    {"Items": items}, self.category, self.reference
                )
                self.assertEqual(embed.description, "No prices available for this category.")

    def test_regular_essences_are_kept(self):
        self.category.value = "essences"
        embed = self.exchange.create_embed({"Items": [self.item("chaos")]}, self.category, self.reference)
        self.assertIn("chaos", embed.description)

    def test_populated_results_keep_prices_and_json_emojis(self):
        embed = self.exchange.create_embed(
            {"Items": [self.item("chaos")]}, self.category, self.reference
        )
        self.assertIn(self.exchange.emojis["chaos"], embed.description)
        self.assertIn(self.exchange.emojis["exalted"], embed.description)
        self.assertIn("chaos", embed.description)
        self.assertIn("5", embed.description)
        self.assertNotIn("No prices available", embed.description)


if __name__ == "__main__":
    unittest.main()
