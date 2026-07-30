import discord
from discord.ext import commands

# "https://api.poe2scout.com/poe2/Leagues/Runes%20of%20Aldur/Items/PriceHistory"
# Add one-time "fake edit" to stop the message from jumping

def create_menu_embed() -> discord.Embed:
    return discord.Embed(
        title="PoE2 Market Menu",
        description="Choose a page below.",
        color=discord.Color.gold(),
    )


def create_page_embed(title: str, content: str) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=content,
        color=discord.Color.gold(),
    )


class PageView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id

    @discord.ui.button(
        label="Back to menu",
        emoji="⬅️",
        style=discord.ButtonStyle.secondary,
    )
    async def back_to_menu(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.edit_message(
            embed=create_menu_embed(),
            view=MenuView(self.owner_id),
        )


class MenuView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id

    @discord.ui.button(
        label="Prices",
        style=discord.ButtonStyle.primary,
    )
    async def prices(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.edit_message(
            embed=create_page_embed(
                "Prices",
                "Currency prices would be displayed here.",
            ),
            view=PageView(self.owner_id),
        )

    @discord.ui.button(
        label="Top Gainers",
        style=discord.ButtonStyle.success,
    )
    async def gainers(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.edit_message(
            embed=create_page_embed(
                "Top Gainers",
                "Top gainers would be displayed here.",
            ),
            view=PageView(self.owner_id),
        )

    @discord.ui.button(
        label="Top Losers",
        style=discord.ButtonStyle.danger,
    )
    async def losers(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.edit_message(
            embed=create_page_embed(
                "Top Losers",
                "Top losers would be displayed here.",
            ),
            view=PageView(self.owner_id),
        )


class PaginationTest:
    def __init__(self, client: commands.Bot):
        self.client = client
        self.register_command()

    def register_command(self):
        @self.client.tree.command(
            name="market-menu",
            description="Open the test market menu",
        )
        async def market_menu(
            interaction: discord.Interaction,
        ):
            await interaction.response.send_message(
                embed=create_menu_embed(),
                view=MenuView(interaction.user.id),
            )