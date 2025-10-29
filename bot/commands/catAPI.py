from dotenv import load_dotenv # type: ignore
from discord.ext import commands # type: ignore
from discord import app_commands # type: ignore
import requests # type: ignore
import discord # type: ignore
import os

class CatApi():
    def __init__(self, client: commands.Bot):
        self.client = client
        self.cat_api()

    def cat_api(self):
        @self.client.tree.command(name="gibcat", description="Get a random image of a cat :3")
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
                    