import discord.ext.commands


class NotUsingFullyInvokeCommand(UserWarning):
    def __init__(self, command: discord.ext.commands.Command):
        super().__init__("Command not called with fully_run_command: %s", command.qualified_name)
