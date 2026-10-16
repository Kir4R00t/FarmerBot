import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import requests

from bot.commands import catAPI, poe2scout
from bot.events import on_message_actions, on_ready
from tests.support import bot, interaction, run_in_test_thread


class LegacyMarketTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        offload = patch.object(poe2scout.asyncio, "to_thread", side_effect=run_in_test_thread)
        self.offload = offload.start()
        self.addCleanup(offload.stop)
        self.client = bot()
        self.addAsyncCleanup(self.client.close)
        self.market = poe2scout.CurrencyExchange(self.client)
        self.category = SimpleNamespace(value="currency", name="Currency")
        self.reference = SimpleNamespace(value="exalted")
        self.callback = self.client.tree.get_command("poe2scout").callback

    def test_price_change_indicators(self):
        for new, old, emoji, text in ((20, 10, "green-up", "100.0%"),
                                       (10, 20, "red-down", "50.0%"), (10, 10, None, "0%")):
            with self.subTest(new=new, old=old):
                result = self.market.calculate_price_change(new, old)
                self.assertIn(text, result)
                self.assertIn(self.market.emojis[emoji] if emoji else ":zero:", result)

    def test_zero_and_invalid_price_history(self):
        self.assertIn("100.0%", self.market.calculate_price_change(0, 10))
        for new, old in ((10, 0), (-1, 10), (10, -1), (None, 10), ("bad", 10), (float("nan"), 10), (10, float("inf"))):
            with self.subTest(new=new, old=old):
                self.assertEqual(self.market.calculate_price_change(new, old), "---")

    def test_multiplier_chooses_league_and_reference(self):
        data = [{"Value": "other"}, {"Value": "Runes of Aldur", "DivinePrice": 100, "ChaosDivinePrice": 10}]
        with patch.object(poe2scout.requests, "get", return_value=Mock(status_code=200, json=Mock(return_value=data))):
            self.assertEqual(self.market.calculate_div_multiplier(self.reference), 100)
            self.assertEqual(self.market.calculate_div_multiplier(SimpleNamespace(value="chaos")), 10)
            with self.assertRaisesRegex(Exception, "No div price"):
                self.market.calculate_div_multiplier(SimpleNamespace(value="unsupported"))
        for status, records in ((503, []), (200, []), (200, [{"Value": "Runes of Aldur", "DivinePrice": 0, "ChaosDivinePrice": 10}])):
            with self.subTest(status=status), patch.object(poe2scout.requests, "get", return_value=Mock(status_code=status, json=Mock(return_value=records))):
                self.assertIsNone(self.market.calculate_div_multiplier(self.reference))

    def test_embed_price_direction_conversion_and_missing_history(self):
        for new, old, expected in ((10, 20, "red-down"), (20, 10, "green-up"), (10, 10, None)):
            data = {"Items": [{"ApiId": "chaos", "CurrentPrice": 200, "PriceLogs": [{"Price": new}, {"Price": old}]}]}
            with self.subTest(new=new, old=old), patch.object(self.market, "calculate_div_multiplier", return_value=100):
                embed = self.market.create_embed(data, self.category, self.reference)
                self.assertIn(self.market.emojis["divine"], embed.description)
                self.assertIn("2.0", embed.description)
                self.assertIn(self.market.emojis[expected] if expected else "0%", embed.description)

    async def test_command_success_and_upstream_http_failure(self):
        for status in (200, 503):
            with self.subTest(status=status), patch.object(poe2scout.requests, "get", return_value=Mock(status_code=status, json=Mock(return_value={"Items": []}))), patch.object(self.market, "calculate_div_multiplier", return_value=100):
                inter = interaction()
                await self.callback(inter, self.category, self.reference)
                inter.response.defer.assert_awaited_once()
                self.offload.assert_awaited()
                inter.followup.send.assert_awaited_once()
                if status == 200:
                    self.assertIn("No prices available", inter.followup.send.call_args.kwargs["embed"].description)
                else:
                    self.assertIn("API is down", inter.followup.send.call_args.args[0])

    async def test_invalid_arguments_use_followup_after_defer(self):
        inter = interaction()
        await self.callback(inter, SimpleNamespace(value=None), self.reference)
        inter.followup.send.assert_awaited_once_with("Unknown category or reference currency.", ephemeral=True)
        inter.response.send_message.assert_not_awaited()

    async def test_network_failure_and_missing_multiplier_return_error(self):
        for failure in ("network", "multiplier"):
            with self.subTest(failure=failure):
                inter = interaction()
                response = Mock(status_code=200, json=Mock(return_value={"Items": [{"ApiId": "chaos", "CurrentPrice": 5, "PriceLogs": []}]}))
                with patch.object(poe2scout.requests, "get", side_effect=requests.RequestException("offline") if failure == "network" else None, return_value=response), patch.object(self.market, "calculate_div_multiplier", return_value=None):
                    await self.callback(inter, self.category, self.reference)
                self.assertTrue(inter.followup.send.call_args.kwargs["ephemeral"])
                self.assertIn("API", inter.followup.send.call_args.args[0])


class CatCommandTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        offload = patch.object(catAPI.asyncio, "to_thread", side_effect=run_in_test_thread)
        self.offload = offload.start()
        self.addCleanup(offload.stop)
        self.client = bot()
        self.addAsyncCleanup(self.client.close)
        catAPI.CatApi(self.client)
        self.callback = self.client.tree.get_command("gibcat").callback
        self.dotenv = patch.object(catAPI, "load_dotenv")
        self.dotenv.start()
        self.addCleanup(self.dotenv.stop)
        self.env = patch.dict(os.environ, {"CAT_API": "fake-test-key"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    async def test_success_empty_and_http_error(self):
        for status, data, expected in ((200, [{"url": "https://example.invalid/cat.jpg"}], "https://example.invalid/cat.jpg"),
                                       (200, [], "No data from API"), (503, [], "API ERROR: 503")):
            with self.subTest(status=status, data=data), patch.object(catAPI.requests, "get", return_value=Mock(status_code=status, json=Mock(return_value=data))):
                inter = interaction()
                await self.callback(inter)
                self.assertEqual(inter.response.send_message.call_args.args[0], expected)

    async def test_network_failure_returns_error(self):
        with patch.object(catAPI.requests, "get", side_effect=requests.RequestException("offline")):
            inter = interaction()
            await self.callback(inter)
        self.assertTrue(inter.response.send_message.call_args.kwargs["ephemeral"])
        self.assertIn("API", inter.response.send_message.call_args.args[0])


class MessageEventTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = bot()
        self.addAsyncCleanup(self.client.close)
        with patch.object(on_message_actions, "load_dotenv"), patch.dict(os.environ, {"DEV_ID": "42"}, clear=True):
            on_message_actions.OnMessageActions(self.client)

    def message(self, *, channel=1, content="hello", attachments=None, author=7, is_bot=False):
        return SimpleNamespace(content=content, attachments=attachments or [],
                               author=SimpleNamespace(id=author, mention=f"<@{author}>", bot=is_bot),
                               channel=SimpleNamespace(id=channel, send=AsyncMock()), delete=AsyncMock())

    async def test_developer_non_ping_message_is_ignored(self):
        msg = self.message(author=42)
        await self.client.on_message(msg)
        msg.channel.send.assert_not_awaited()

    async def test_bot_messages_are_ignored_and_only_developer_can_ping(self):
        for author, is_bot, responds in ((42, True, False), (7, False, False), (42, False, True)):
            msg = self.message(author=author, is_bot=is_bot, content="PING")
            await self.client.on_message(msg)
            if responds:
                msg.channel.send.assert_awaited_once_with("pong")
            else:
                msg.channel.send.assert_not_awaited()
            msg.delete.assert_not_awaited()

    async def test_pricecheck_moderation_for_both_games(self):
        for channel, url in ((1336034291427053578, "www.pathofexile.com/trade2/"),
                             (1382141426103750736, "www.pathofexile.com/trade/")):
            for content, attachments, deleted in (("check this", [object()], True),
                                                  (url.upper() + "search/test", [object()], False),
                                                  ("text only", [], False)):
                with self.subTest(channel=channel, content=content):
                    msg = self.message(channel=channel, content=content, attachments=attachments)
                    await self.client.on_message(msg)
                    if deleted:
                        msg.delete.assert_awaited_once()
                        embed = msg.channel.send.call_args.kwargs["embed"]
                        self.assertIn(msg.author.mention, embed.description)
                        self.assertEqual(embed.title, "Your message was deleted!")
                    else:
                        msg.delete.assert_not_awaited()
                        msg.channel.send.assert_not_awaited()


class ReadyEventTests(unittest.IsolatedAsyncioTestCase):
    async def test_ready_syncs_commands_with_zero_or_multiple_guilds(self):
        for guilds in ([], [SimpleNamespace(name="One", id=1), SimpleNamespace(name="Two", id=2)]):
            with self.subTest(guilds=guilds):
                client = Mock(guilds=guilds, user="Test bot", tree=Mock(sync=AsyncMock(return_value=[SimpleNamespace(name="gibcat", type="chat_input")])) )
                client.event.side_effect = lambda callback: setattr(client, callback.__name__, callback)
                on_ready.OnReady(client)
                with self.assertLogs(on_ready.logger, level="INFO") as logs:
                    await client.on_ready()
                client.tree.sync.assert_awaited_once()
                self.assertIn("gibcat", "\n".join(logs.output))

    async def test_sync_failure_is_logged(self):
        client = Mock(guilds=[], user="Test bot", tree=Mock(sync=AsyncMock(side_effect=RuntimeError("sync failed"))))
        client.event.side_effect = lambda callback: setattr(client, callback.__name__, callback)
        on_ready.OnReady(client)
        with self.assertLogs(on_ready.logger, level="ERROR") as logs:
            await client.on_ready()
        self.assertIn("sync failed", "\n".join(logs.output))
