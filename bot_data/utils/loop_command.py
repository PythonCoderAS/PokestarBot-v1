import discord.ext.commands
import discord.ext.tasks

from .custom_context import HubContext
from .embed import Embed


def define_loop_subcommands(loop: discord.ext.tasks.Loop, loop_command: discord.ext.commands.Group):
    @loop_command.command(brief="Start the loop")
    @discord.ext.commands.is_owner()
    @discord.ext.commands.dm_only()
    async def start(ctx: HubContext):
        await ctx.bot.execute(ctx.hub.capture_message, "Loop started!",
                              scope=ctx.bot.scope_from_context(ctx, tag_data={"loop_name": loop.coro.__name__}))
        loop.start()
        await ctx.send(embed=Embed(ctx, title="Loop Started", description="The loop has been started.", color=discord.Color.green()))

    @loop_command.command(brief="Stop the loop")
    @discord.ext.commands.is_owner()
    @discord.ext.commands.dm_only()
    async def stop(ctx: HubContext):
        await ctx.bot.execute(ctx.hub.capture_message, "Loop stopped!",
                              scope=ctx.bot.scope_from_context(ctx, tag_data={"loop_name": loop.coro.__name__}))
        loop.stop()
        await ctx.send(embed=Embed(ctx, title="Loop Stopped", description="The loop has been stopped.", color=discord.Color.green()))

    @loop_command.command(brief="Restart the loop")
    @discord.ext.commands.is_owner()
    @discord.ext.commands.dm_only()
    async def restart(ctx: HubContext):
        await ctx.bot.execute(ctx.hub.capture_message, "Loop restarted!",
                              scope=ctx.bot.scope_from_context(ctx, tag_data={"loop_name": loop.coro.__name__}))
        loop.restart()
        await ctx.send(embed=Embed(ctx, title="Loop Restarted", description="The loop has been restarted.", color=discord.Color.green()))


def loop_command_deco(loop: discord.ext.tasks.Loop):
    def wrapper(loop_command: discord.ext.commands.Group):
        define_loop_subcommands(loop, loop_command)
        return loop_command

    return wrapper
