from discord.ext import commands # type: ignore
from discord import app_commands # type: ignore
import requests # type: ignore
import discord # type: ignore

from util import item_emojis

class CurrencyExchange():
    def __init__(self, client: commands.Bot):
        self.client = client
        self.market_command()

    def market_command(self):
        @self.client.tree.command(name="poe2scout", description="Check the current market prices for specified item category and with specified currency reference")
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
