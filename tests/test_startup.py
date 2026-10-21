import os
import runpy
import unittest
from unittest.mock import Mock, patch

from bot import main


class StartupTests(unittest.TestCase):
    def test_initialisation_registers_modules_and_run_passes_token(self):
        # Fake values only; never load the project's .env or log into Discord.
        with patch.object(main, "load_dotenv"), patch.dict(os.environ, {"DC": "fake-token"}, clear=True), patch.object(main.commands, "Bot") as factory, \
             patch.object(main.poe2scout, "CurrencyExchange") as market, patch.object(main.catAPI, "CatApi") as cats, \
             patch.object(main.on_message_actions, "OnMessageActions") as messages, patch.object(main.on_ready, "OnReady") as ready, \
             patch.object(main.pagination, "Pagination") as pagination:
            app = main.BotApp()
            for constructor in (market, cats, messages, ready, pagination):
                constructor.assert_called_once_with(factory.return_value)
            self.assertEqual(factory.call_args.kwargs["command_prefix"], "!")
            app.run()
            factory.return_value.run.assert_called_once_with("fake-token")

    def test_module_entrypoint_constructs_and_runs_bot_offline(self):
        with patch("dotenv.load_dotenv"), patch.dict(os.environ, {"DC": "fake-token"}, clear=True), \
             patch("discord.ext.commands.Bot") as factory, \
             patch("bot.commands.poe2scout.CurrencyExchange"), patch("bot.commands.catAPI.CatApi"), \
             patch("bot.events.on_message_actions.OnMessageActions"), patch("bot.events.on_ready.OnReady"), \
             patch("bot.commands.pagination.Pagination"):
            # run_path avoids importing a second cached module under the same name.
            runpy.run_path(main.__file__, run_name="__main__")
            factory.return_value.run.assert_called_once_with("fake-token")
