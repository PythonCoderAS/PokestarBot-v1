import warnings
from typing import Any

import discord.ext.commands

from .custom_warnings import NotUsingFullyInvokeCommand
from .custom_context import HubContext

class CustomMixin:
    """Mixin to do the custom behaviors."""

    async def __call__(self, *args, bypass=False, **kwargs):
        if not bypass:
            warnings.warn(NotUsingFullyInvokeCommand(self))
        return await super().__call__(*args, **kwargs)

    def __init__(self, func, significant: bool = False, not_channel_locked: bool = False, **kwargs):
        if type(self) is CustomMixin:
            raise Exception("Cannot initialize the CustomMixin class.")
        self.significant = significant
        self.not_channel_locked = not_channel_locked
        kwargs = {"cooldown_after_parsing": True, **kwargs}
        super().__init__(func, **kwargs)
        alias_list = [self.name] + list(self.aliases)
        self.aliases.extend([item.replace("_", "") for item in alias_list])
        self.aliases.extend([item.replace("_", "-") for item in alias_list])
        self.aliases = list(set(self.aliases))
        if self.name in self.aliases:
            self.aliases.remove(self.name)

    async def fully_run_command(self, ctx: HubContext, *args: Any, **kwargs: Any):
        ctx.hub.add_breadcrumb(category="Command Run", message=f"Invoking command {self.name}")
        if not await self.can_run(ctx):
            raise discord.ext.commands.CheckFailure("Check functions failed")
        self._prepare_cooldowns(ctx)
        return await self(ctx, *args, **kwargs, bypass=True)


class CustomCommand(CustomMixin, discord.ext.commands.Command):
    pass


class CustomGroup(CustomMixin, discord.ext.commands.Group):

    def command(self, *args, **kwargs):
        def decorator(func):
            kwargs.setdefault('parent', self)
            result = discord.ext.commands.command(*args, **kwargs)(func)  # Use patched version from patch()
            self.add_command(result)
            return result

        return decorator

    def group(self, *args, **kwargs):
        def decorator(func):
            kwargs.setdefault('parent', self)
            result = discord.ext.commands.group(*args, **kwargs)(func)  # Use patched version from patch()
            self.add_command(result)
            return result

        return decorator


def patch():
    """Patch the discord.ext.commands.command() and discord.ext.commands.group() decorators to use the classes defined above"""

    import functools
    if not isinstance(discord.ext.commands.command, functools.partial):  # Prevent double-partial-ing
        command = functools.partial(discord.ext.commands.command, cls=CustomCommand)
        discord.ext.commands.command = command
    if not isinstance(discord.ext.commands.group, functools.partial):  # Prevent double-partial-ing
        group = functools.partial(discord.ext.commands.group, cls=CustomGroup)
        discord.ext.commands.group = group
