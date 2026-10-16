from dotenv import load_dotenv # type: ignore
from discord.ext import commands # type: ignore
from discord import app_commands # type: ignore
import requests # type: ignore
import discord # type: ignore
import os
import asyncio

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
            try:
                response = await asyncio.to_thread(requests.get, url, timeout=10)
            except requests.RequestException:
                await interaction.response.send_message("Cat API is unavailable.", ephemeral=True)
                return

            if response.status_code == 200:
                data = response.json()

                if data:
                    # Posting a url is enough since Discord automatically embeds it
                    await interaction.response.send_message(data[0]['url'], ephemeral=True)

                else:
                    await interaction.response.send_message("No data from API", ephemeral=False)

            else:
                await interaction.response.send_message(f"API ERROR: {response.status_code}", ephemeral=True)

