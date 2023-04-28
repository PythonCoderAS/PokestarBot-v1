import discord.ext.commands


def admin_or_bot_owner():
    return discord.ext.commands.check_any(discord.ext.commands.has_guild_permissions(administrator=True), discord.ext.commands.is_owner())
