from discord.ext import commands # type: ignore

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
            print(
                f'{self.client.user} is connected to the following guild:\n'
                f'{guild.name}(id: {guild.id})'
            )

            # Commands sync
            try:
                print("Synced commands: \n")
                synced = await self.client.tree.sync()
                for x in synced:
                    print(f'{x}\n')
                if synced is None:
                    print(f'{x} is not synced\n')

            except Exception as error:
                print(error)