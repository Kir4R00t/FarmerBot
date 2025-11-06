from discord.ext import commands # type: ignore
import discord # type: ignore

class OnMessageActions():
    def __init__(self, client: commands.Bot):
        self.client = client
        self.eventListener()

    def eventListener(self):
        @self.client.event
        async def on_message(message):
            msg_content = message.content.lower()
            msg_mention = message.author.mention
            
            bot_dev_id = 419571860041105410 # My discord UUID
            poe2_price_check_channel_id = 1336034291427053578
            poe1_price_check_channel_id = 1382141426103750736
            trade_site_url = 'www.pathofexile.com/trade2/'

            # Ignore all bot messages
            if message.author.bot:
                return

            # Ping --> simple check if bot is alive
            if message.author.id == bot_dev_id:
                if msg_content == 'ping':
                    await message.channel.send('pong')

            # Pricecheck channel message check
            if message.channel.id == poe2_price_check_channel_id or message.channel.id == poe1_price_check_channel_id:
                if message.attachments and trade_site_url not in msg_content:
                    embed=discord.Embed (
                        title="Your message was deleted!", 
                        description=f'{msg_mention} Please provide a valid trade link + screenshot of your item to get a price check.', 
                        color=0xff0000
                        )
                    embed.set_footer(text="See pinned message.")
                    
                    await message.channel.send(embed=embed)
                    await message.delete()
