from dotenv import load_dotenv # type: ignore
from discord.ext import commands # type: ignore
from discord import app_commands # type: ignore
import requests # type: ignore
import discord # type: ignore
import os

from bot import item_emojis

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
            # Posting a url is enough since Discord automatically embeds it
            await interaction.response.send_message(cat_photo_url, ephemeral=True)
        
        else:
            await interaction.response.send_message("No data from API", ephemeral=False)
    
    else:
        await interaction.response.send_message(f"API ERROR: {response.status_code}", ephemeral=True)

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
    if category.value is None or ref_choice is None:
        await interaction.response.send_message("Unknown category or reference currency.", ephemeral=True)
        return
    
    url = f'https://poe2scout.com/api/items/currency/{category.value}?referenceCurrency={ref_choice.value}&page=1&perPage=25&league=Rise%20Of%20The%20Abyssal'
    
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
  
        embed = discord.Embed(
            title=f"{emojis['divine']} Currency prices {emojis['divine']}",
            description="Current rates for basic currency. NOTE: data is collected from [poe2scout](https://poe2scout.com/) and they collect data every 3hrs",
            color=discord.Color.gold()
        )

        # Get divine price from leagues api.
        leagues_url = 'https://poe2scout.com/api/leagues'
        league_data_response = requests.get(leagues_url)

        if (league_data_response.status_code != 200):
            await interaction.followup.send('poe2scout API is down', ephemeral=True)
            print("Did not get a response ... poe2scout API may be down")
            return

        league_data_json = league_data_response.json()

        divine_price = 0
        chaos_divine_price = 0
        for league in league_data_json:
            if league['value'] != 'Rise of the Abyssal':
                continue
            divine_price = league['divinePrice']
            chaos_divine_price = league['chaosDivinePrice']

        if divine_price == 0 or chaos_divine_price == 0:
            await interaction.followup.send('poe2scout is not working right now.', ephemeral=True)
            print("Poe2scout returned malformed data")
            return
        
        current_div_multiplier = 0
        if (ref_choice.value == 'exalted'):
            current_div_multiplier = divine_price
        elif (ref_choice.value == 'chaos'):
            current_div_multiplier = chaos_divine_price
        else:
            await interaction.followup.send('Farmerbot had a catastrophic failure.', ephemeral=True)
            raise Exception("No div price for given ref_choice")

        # Parse item data & match with emoji
        for line in data['items']:
            item_name = line['apiId']
            
            # Exclude all lesser and greater essences since their price is alwyas very small/irrelevant
            if category.value == 'essences':
                if 'lesser' in item_name or 'greater' in item_name:
                    continue
            
            # If there are any missing emojis just log them and skip to the next iteration
            if item_name not in emojis:
                print(f'Emote missing for {item_name}')
                continue

            item_emoji = emojis[item_name]
            price = line['currentPrice']

            # If the price is over 1.3 the given multiplier. Price it in div. Else price it to ref_choice
            if price > (current_div_multiplier * 1.3):
                div_price = price / current_div_multiplier
                embed.add_field(
                    name=f"{item_emoji} {item_name}",
                    value=f"price = {round(div_price, 3)} {emojis['divine']} ",
                    inline=True
                )
            else:
                embed.add_field(
                    name=f"{item_emoji} {item_name}",
                    value=f"price = {round(price, 3)} {emojis[ref_choice.value]} ",
                    inline=True
                )

        await interaction.followup.send(embed=embed)

    else:
        await interaction.followup.send('poe2scout API is down', ephemeral=True)
        print("Did not get a response ... poe2scout API may be down")

def main():
    bot.run(BOT_TOKEN)

if __name__ == '__main__':
    main()
