from discord.ext import commands

from bot import UNOBot
from bot.uno.game import UNO as UNOGame


class UNO(commands.Cog):
    """
    Play UNO with friends!
    """

    def __init__(self, bot: UNOBot) -> None:
        self.bot: UNOBot = bot

    def cog_unload(self) -> None:
        self.bot.uno_instances.clear()

    @commands.command('play', aliases=['uno'])
    @commands.max_concurrency(1, commands.BucketType.user)
    async def play_uno(self, ctx: commands.Context, /) -> None:
        if ctx.channel.id in self.bot.uno_instances:
            return await ctx.send('An instance of UNO is already running in this channel.')

        game = UNOGame(ctx)
        self.bot.uno_instances[ctx.channel.id] = game

        await game.start()
        await game.wait()

        try:
            del self.bot.uno_instances[ctx.channel.id]
        except KeyError:
            pass


def setup(bot: UNOBot, /) -> None:
    bot.add_cog(UNO(bot))
