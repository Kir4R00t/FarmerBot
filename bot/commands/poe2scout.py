from discord.ext import commands # type: ignore
from discord import app_commands # type: ignore
import requests # type: ignore
import discord # type: ignore

from bot.util import item_emojis

class CurrencyExchange():
    def __init__(self, client: commands.Bot):
        self.client = client
        self.emojis = item_emojis.list
        self.market_command()

    def calculate_price_change(self, price_new: float, price_old: float) -> str:
        price_change = round((price_old / price_new) * 100, 2)
        
        if price_change > 100.0:
            price_change = f"{round(price_change - 100.00, 2)} %"
            price_change_emoji = self.emojis['red-down']
        elif price_change < 100.0:
            price_change = f"{round(100.00 - price_change, 2)} %" 
            price_change_emoji = self.emojis['green-up']
        elif price_change == 100.0:
            price_change = f"0%"
            price_change_emoji = ':zero:'
        else:
            raise Exception

        return f"{price_change_emoji} {price_change}"

    def calculate_div_multiplier(self, ref_choice: str) -> float:
        # Get divine price from leagues api.
        leagues_url = 'https://poe2scout.com/api/leagues'
        league_data_response = requests.get(leagues_url)

        if (league_data_response.status_code != 200):
            print("Did not get a response ... poe2scout API may be down")
            return

        league_data_json = league_data_response.json()

        divine_price = 0
        chaos_divine_price = 0
        for league in league_data_json:
            if league['value'] != 'Fate of the Vaal':
                continue
            divine_price = league['divinePrice']
            chaos_divine_price = league['chaosDivinePrice']

        if divine_price == 0 or chaos_divine_price == 0:
            print("Poe2scout returned malformed data")
            return
        
        if (ref_choice.value == 'exalted'):
            current_div_multiplier = divine_price
        elif (ref_choice.value == 'chaos'):
            current_div_multiplier = chaos_divine_price
        else:
            raise Exception("No div price for given ref_choice")

        return current_div_multiplier

    def create_embed(self, item_list: dict, category: str, ref_choice: str) -> discord.Embed:
        current_div_multiplier = self.calculate_div_multiplier(ref_choice)
        
        # First pass: collect all items and find max name length
        items_data = []
        max_name_length = 0
        
        for itemdata in item_list['items']:
            # Extract item data, calculate price change
            item_name = itemdata['apiId']
            
            if item_name == ref_choice.value: continue # skip ref currency
            
            price = itemdata['currentPrice']
            
            try:
                # Get price change
                new_price = itemdata['priceLogs'][0]['price']
                old_price = itemdata['priceLogs'][1]['price']
                price_change_value = round((old_price / new_price) * 100, 2)
                
                if price_change_value > 100.0:
                    price_change_text = f"{round(price_change_value - 100.00, 2)}%"
                    price_change_emoji = self.emojis['red-down']
                elif price_change_value < 100.0:
                    price_change_text = f"{round(100.00 - price_change_value, 2)}%"
                    price_change_emoji = self.emojis['green-up']
                else:
                    price_change_text = "0%"
                    price_change_emoji = "="
            except (TypeError, IndexError, KeyError) as e:
                print(f"Exception while calculating the price: {e}")
                price_change_text = "---"
                price_change_emoji = ""
            
            # Exclude all lesser and greater essences since their price is alwyas very small/irrelevant
            if category.value == 'essences':
                if 'lesser' in item_name or 'greater' in item_name:
                    continue
            
            # If there are any missing emojis just log them and skip to the next iteration
            if item_name not in self.emojis:
                print(f'Emote missing for {item_name}')
                continue
            
            # If the price is over 1.3 the given multiplier. Price it in div. Else price it to ref_choice
            if price > (current_div_multiplier * 1.3):
                div_price = price / current_div_multiplier
                price_str = f"{round(div_price, 2)}"
                price_emoji = self.emojis['divine']
            else:
                price_str = f"{round(price, 2)}"
                price_emoji = self.emojis[ref_choice.value]
            
            item_emoji = self.emojis.get(item_name, '')
            name_display = item_name.replace('-', ' ')
            max_name_length = max(max_name_length, len(name_display))
            
            items_data.append({
                'emoji': item_emoji,
                'name': name_display,
                'price': price_str,
                'price_emoji': price_emoji,
                'change_emoji': price_change_emoji,
                'change_text': price_change_text
            })
        
        # Second pass: format with consistent alignment
        max_price_length = max(len(item['price']) for item in items_data)
        
        all_items = []
        for item in items_data:
            name_padded = item['name'].ljust(max_name_length)
            price_padded = item['price'].rjust(max_price_length)
            line = f"{item['emoji']} `{name_padded}  {price_padded}` {item['price_emoji']} {item['change_emoji']} `{item['change_text']}`"
            all_items.append(line)
        
        description_text = "\n".join(all_items)
        
        embed = discord.Embed(
            title=f"{self.emojis['divine']} Currency Prices {self.emojis['divine']}",
            description=description_text,
            color=discord.Color.gold()
        )
        
        total_items = len(all_items)
        shown_items = total_items
        
        mirror_img_url = "https://web.poecdn.com//gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lEdXBsaWNhdGUiLCJzY2FsZSI6MSwicmVhbG0iOiJwb2UyIn1d/26bc31680e/CurrencyDuplicate.png"
        embed.set_footer(
                text =      f"Showing {shown_items} of {total_items} fetched items • Data extracted from poe2scout.com",
                icon_url =  mirror_img_url             
            )
            
        return embed

    def market_command(self):
        @self.client.tree.command(name="poe2scout", description="Check the current market prices for specified item category and with specified currency reference")
        @app_commands.describe(
            category="Select the category of currency",
            ref_choice="Select currency reference"
        )
        @app_commands.choices(
            category = [
                app_commands.Choice(name="Currency",            value="currency"),
                app_commands.Choice(name="Soul Cores",          value="ultimatum"),
                app_commands.Choice(name="Essences",            value="essences"),
                app_commands.Choice(name="Delirium",            value="delirium"),
                app_commands.Choice(name="Breach",              value="breach"),
                app_commands.Choice(name="Fragments",           value="fragments"),
                app_commands.Choice(name="Uncut Gems",          value="uncutgems"),
                app_commands.Choice(name="Runes",               value="runes"),
                app_commands.Choice(name="Idols",               value="idols"),
                app_commands.Choice(name="Lineage Supports",    value="runes"),
                app_commands.Choice(name="Abyss",               value="abyss"),
                app_commands.Choice(name="Reliquary keys",      value="vaultkeys")
            ],
            ref_choice = [
                app_commands.Choice(name="Exalted", value="exalted"),
                app_commands.Choice(name="Chaos", value="chaos")
            ]
        )
        async def poe2scout(interaction: discord.Interaction, category: app_commands.Choice[str], ref_choice: app_commands.Choice[str]):
            # Defer to make sure that bot has enough time to parse data
            await interaction.response.defer()
            
            # Get desired category and reference currency
            if category.value is None or ref_choice is None:
                await interaction.response.send_message("Unknown category or reference currency.", ephemeral=True)
                return
            
            url = f'https://poe2scout.com/api/items/currency/{category.value}?referenceCurrency={ref_choice.value}&page=1&perPage=25&league=Fate%20of%20the%20Vaal'
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()
                embed = self.create_embed(data, category, ref_choice)

                await interaction.followup.send(embed=embed)

            else:
                await interaction.followup.send('poe2scout API is down', ephemeral=True)
                print("Did not get a response ... poe2scout API may be down")
