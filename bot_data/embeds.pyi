# This file represents the syntax for the generate_embed function.

# File structure: When you call `%embed list` or `%embed pre_create`, a bunch of folders are made, titled `g_<guild_id>`.
# Each folder is for the embeds of that guild. All files with underscores are excluded, but any other Python file is considered a valid embed file.
# The embed's name (the one used in `%embed <name>` will become the name of the module that contains it.

from typing import List, Optional, TYPE_CHECKING, Tuple, Union, overload

import discord

if TYPE_CHECKING:
    from .bot import PokestarBot

# All modules have one function, `generate_embed`, that is responsible for generating the embed (or the data) to be then sent to the caller. The
# `%embed` function calls this function and then deals with the returned data. The `generate_embed` function cannot actually send the embed, as the
# sole argument to it is the PokestarBot instance. This allows fetching of guilds and channels and users/members.

# The original format returns a List of Tuples. Each Tuple contains two arguments. One of them is the content to send (or None), and the other is the embed to send (or None). To indicate that the original format is being returned, the direct return is a tuple of `False, <data>` where <data> is the List of Tuples.
# Example return: (False, [(None, discord.Embed(title="Example", description="Hello World!"))])
@overload
async def generate_embed(bot: "PokestarBot") -> Tuple[bool, List[Tuple[Optional[str], Optional[discord.Embed]]]]: ...

# The new format returns a Tuple of a starting Embed and a List of fields. The fields match the same types as the `fields` parameter of `send_embeds_fields` accepts. To indicate that the new format is being returned, the direct return is a tuple of `Tuple, <data>` where <data> is the Tuple of an Embed and fields.
# Example return: (True, (discord.Embed(title="Example", description="Hello World!"), [("Hello", "World!")]))
@overload
async def generate_embed(bot: "PokestarBot") -> Tuple[bool, Tuple[discord.Embed, List[Union[Tuple[str, str], str]]]]: ...

async def generate_embed(bot: "PokestarBot") -> tuple: ...
