from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
import requests
import logging
import discord
import os

from bot import item_emojis

# Loading intents & bot token
load_dotenv('.env')
BOT_TOKEN = os.getenv('DC')
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Logger stuff
logger = logging.getLogger("bot")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()


@bot.event
async def on_ready():
    global guild
    for guild in bot.guilds:
        if guild.name == guild:
            break

    # Bot connection info
    logger.info(
        f'{bot.user} is connected to the following guild:\n'
        f'{guild.name}(id: {guild.id})'
    )

    # Commands sync
    try:
        logger.info("Synced commands: \n")
        synced = await bot.tree.sync()
        for x in synced:
            logger.info(f'{x}\n')
        if synced is None:
            logger.info(f'{x} is not synced\n')

    except Exception as error:
        logger.info(error)

@bot.event
async def on_message(message):
    if message.content.lower() == 'ping':
        await message.channel.send('pong')

# CATSSS
@bot.tree.command(name="gibcat", description="Get a random image of a cat :3")
async def gibcat(interaction: discord.Interaction):
    load_dotenv('.env')
    api_key = os.getenv('CAT_API')
    url = f"https://api.thecatapi.com/v1/images/search?&api_key={api_key}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        cat_photo_url = (data[0]['url'])
        if data:
            await interaction.response.send_message(cat_photo_url, ephemeral=False)
        else:
            await interaction.response.send_message("No data from API", ephemeral=False)
    else:
        await interaction.response.send_message(f"API ERROR: {response.status_code}", ephemeral=False)

# Currency market check
@bot.tree.command(name="poe2scout", description="Check the current market prices for specified item category and with specified currency reference")
@app_commands.describe(
    category="Select the category of currency",
    ref_choice="Select currency reference"
)
@app_commands.choices(
    category = [
        app_commands.Choice(name="Currency", value="currency"),
        app_commands.Choice(name="Soul Cores", value="ultimatum"),
        app_commands.Choice(name="Essences", value="essences")
    ],
    ref_choice = [
        app_commands.Choice(name="Exalted", value="exalted"),
        app_commands.Choice(name="Chaos", value="chaos")
    ]
)
async def poe2scout(interaction: discord.Interaction, category: app_commands.Choice[str], ref_choice: app_commands.Choice[str]):
    # Defer to make sure that bot has enough time to parse data
    await interaction.response.defer()
    
    # Load emojis
    emojis = item_emojis.list

    # Get desired category and reference currency
    if category.value and ref_choice:
        url = f'https://poe2scout.com/api/items/currency/{category.value}?referenceCurrency={ref_choice.value}&page=1&perPage=25&league=Rise%20Of%20The%20Abyssal'
        logger.info(f'Successfully made a query with: {url}')
    else:
        logger.info(f'Shit just hit the fan with {url}')
        await interaction.response.send_message("Unknown category or reference currency.", ephemeral=True)
        return
        
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
  
        embed = discord.Embed(
            title=f"{emojis['divine']} Currency prices {emojis['divine']}",
            description="Current rates for basic currency. NOTE: data is collected from poe2scout and they collect data every 3hrs",
            color=discord.Color.gold()
        )

        # Parse item data & match with emoji
        for line in data['items']:
            item_name = line['apiId']
            
            # Exclude all lesser and greater essences since their price is alwyas very small/irrelevant
            if category.value == 'essences':
                if 'lesser' in item_name or 'greater' in item_name:
                    continue

            item_emoji = emojis[item_name]
            price = line['currentPrice']
            
            embed.add_field(
                name=f"{item_emoji} {item_name}",
                value=f"price = {round(price, 3)} {emojis[ref_choice.value]} ",
                inline=True
            )

        await interaction.followup.send(embed=embed)

    else:
        await interaction.followup.send('poe2scout API is down', ephemeral=True)
        logger.warning("Did not get a response ... poe2scout API may be down")

def main():
    bot.run(BOT_TOKEN)

if __name__ == '__main__':
    main()
