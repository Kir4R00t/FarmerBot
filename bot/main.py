from dotenv import load_dotenv # type: ignore
from discord.ext import commands # type: ignore
import discord # type: ignore
import os

from bot.commands import poe2scout, catAPI
from bot.events import on_message_actions, on_ready

class BotApp():
    def __init__(self):
        # Loading envs
        load_dotenv('.env')
        self.BOT_TOKEN = os.getenv('DC')
        
        # Load intents, create bot instance
        intents = discord.Intents.all()
        self.bot = commands.Bot(command_prefix='!', intents=intents)

        # Initalize bot modules
        poe2scout.CurrencyExchange(self.bot)
        catAPI.CatApi(self.bot)
        on_message_actions.OnMessageActions(self.bot)
        on_ready.OnReady(self.bot)
    
    def run(self):
        self.bot.run(self.BOT_TOKEN)

if __name__ == '__main__':
    app = BotApp()
    app.run()
