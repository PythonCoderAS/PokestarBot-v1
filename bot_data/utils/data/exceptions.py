import discord.ext.commands


class DiscordDataException(discord.ext.commands.CommandError):
    __slots__ = ()

    exception_name = "Discord Data Exception"


class InvalidPage(DiscordDataException):
    __slots__ = ("page", "max")

    exception_name = "Invalid Page"

    def __init__(self, page: int, max_pages: int):
        super().__init__(f"The page `{page}` is an invalid page.")
        self.page = page
        self.max = max_pages
