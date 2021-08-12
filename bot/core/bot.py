import os
import discord

from dotenv import load_dotenv
from discord.ext import commands
from jishaku.flags import Flags

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..uno.game import UNO

load_dotenv()

Flags.NO_UNDERSCORE = True
Flags.NO_DM_TRACEBACK = True
Flags.HIDE = True

INTENTS = discord.Intents(
    guilds=True,
    invites=True,
    messages=True,
    reactions=True,
    typing=True
)

ALLOWED_MENTIONS = discord.AllowedMentions(
    users=True,
    roles=False,
    everyone=False,
    replied_user=False
)


class UNOBot(commands.Bot):
    def __init__(self) -> None:
        # Map channel_id's to UNO game instances
        self.uno_instances: dict[int, UNO] = {}

        super().__init__(
            command_prefix=self.__class__._get_prefix,
            case_insensitive=True,
            owner_id=414556245178056706,
            description='suspicious',
            max_messages=10,
            strip_after_prefix=True,
            intents=INTENTS,
            allowed_mentions=ALLOWED_MENTIONS,
            status=discord.Status.dnd,
            activity=discord.Activity(name='UNO', type=discord.ActivityType.playing),
            chunk_guilds_at_startup=False
        )
        self.setup()

    async def _get_prefix(self, _message: discord.Message) -> list[str]:
        return ['uno', 'Uno', 'UNO']  # Too lazy to make a decent prefix system so here you go

    def load_extensions(self) -> None:
        self.load_extension('jishaku')
        self.load_extension('bot.extensions.uno')

    def setup(self) -> None:
        self.loop.create_task(self._dispatch_first_ready())
        self.load_extensions()

    async def _dispatch_first_ready(self) -> None:
        await self.wait_until_ready()
        self.dispatch('first_ready')

    async def on_first_ready(self) -> None:
        print(f'Logged in as {self.user} (ID: {self.user.id})')

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandNotFound):
            return

        error = getattr(error, 'original', error)

        if isinstance(error, discord.NotFound) and error.code == 10062:
            return

        await ctx.send(error)
        raise error

    def run(self) -> None:
        try:
            super().run(os.environ['TOKEN'])
        except KeyError:
            raise ValueError('The "TOKEN" environment variable must be supplied.')
