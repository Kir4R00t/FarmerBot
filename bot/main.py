from dotenv import load_dotenv # type: ignore
from discord.ext import commands # type: ignore
from discord import app_commands # type: ignore
import requests # type: ignore
import discord # type: ignore
import os

from commands import poe2scout

# Loading intents & bot token
load_dotenv('.env')
BOT_TOKEN = os.getenv('DC')
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    global guild
    for guild in bot.guilds:
        if guild.name == guild:
            break

    # Bot connection info
    print(
        f'{bot.user} is connected to the following guild:\n'
        f'{guild.name}(id: {guild.id})'
    )

    # Commands sync
    try:
        print("Synced commands: \n")
        synced = await bot.tree.sync()
        for x in synced:
            print(f'{x}\n')
        if synced is None:
            print(f'{x} is not synced\n')

    except Exception as error:
        print(error)

@bot.event
async def on_message(message):
    msg_content = message.content.lower()
    msg_mention = message.author.mention

    # Ignore all bot messages
    if message.author.bot:
        return

    # Ping --> simple check if bot is alive
    if message.author.id == 419571860041105410: # only reply to msgs from me
        if msg_content == 'ping':
            await message.channel.send('pong')

    # Pricecheck channel message check
    if message.channel.id == 1336034291427053578:
        trade_site_url = 'www.pathofexile.com/trade2/'
        if message.attachments and trade_site_url not in msg_content:
            embed=discord.Embed (
                title="Your message was deleted!", 
                description=f'{msg_mention} Please provide a valid trade link + screenshot of your item to get a price check.', 
                color=0xff0000
                )
            embed.set_footer(text="See pinned message.")
            
            await message.channel.send(embed=embed)
            await message.delete()

def init():
    try:
        poe2scout.CurrencyExchange(bot)
    except Exception as e:
        print(f'Error initializing modules: {e}')

def main():
    init()
    bot.run(BOT_TOKEN)

if __name__ == '__main__':
    main()
