from discord.ext import commands # type: ignore
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OnReady():
    def __init__(self, client: commands.Bot):
        self.client = client
        self.ready_event()

    def ready_event(self):
        @self.client.event
        async def on_ready():
            global guild
            for guild in self.client.guilds:
                if guild.name == guild:
                    break

            # Bot connection info
            logger.info(
                "%s is connected to guild: %s (id=%s)",
                self.client.user, guild.name, guild.id
            )

            # Commands sync
            try:
                logger.info("Synced commands: \n")
                synced = await self.client.tree.sync()
                logger.info("Synced %d commands:\n%s",
                            len(synced),
                            "\n".join(f"- {cmd.name} ({cmd.type})" for cmd in synced))

            except Exception as e:
                logger.ERROR(e)