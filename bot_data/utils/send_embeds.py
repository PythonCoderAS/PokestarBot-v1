import copy
import datetime
from typing import Callable, List, Optional, Pattern, Tuple, Union

import discord.ext.commands

from .break_into_groups import break_into_groups


async def generate_embeds(embed: discord.Embed, groups: List[str], *, first_name: str = "\u200b",
                          timestamp: Union[datetime.datetime, type(discord.Embed.Empty)] = discord.Embed.Empty,
                          title: Union[str, type(discord.Embed.Empty)] = discord.Embed.Empty,
                          color: Union[discord.Color, type(discord.Embed.Empty)] = discord.Embed.Empty,
                          description: Union[str, type(discord.Embed.Empty)] = discord.Embed.Empty,
                          do_before_send: Callable[[discord.Embed], discord.Embed] = None):
    embeds = []
    orig_embed = embed
    if not title:
        title = embed.title + " (continued)"
    first_loop = (6000 - len(embed)) // 1024
    first_groups = groups[:first_loop]
    groups = groups[first_loop:]
    embed.add_field(name=first_name, value=first_groups.pop(0), inline=False)
    for group in first_groups:
        embed.add_field(name="\u200b", value=group, inline=False)
    embed = do_before_send(embed) if do_before_send else embed
    embeds.append(embed)
    while groups:
        batch = groups[:4]
        groups = groups[4:]
        embed = discord.Embed(timestamp=timestamp, title=title, color=color, description=description)
        for item in filter(lambda slot: slot.startswith("_") and slot != "_fields", discord.Embed.__slots__):
            if hasattr(orig_embed, item):
                setattr(embed, item, getattr(orig_embed, item))
        for group in batch:
            embed.add_field(name="\u200b", value=group, inline=False)
        embed = do_before_send(embed) if do_before_send else embed
        embeds.append(embed)
    return embeds


async def send_embeds(ctx: discord.abc.Messageable, embed: discord.Embed, groups: List[str], *,
                      first_name: str = "\u200b",
                      timestamp: Union[datetime.datetime, type(discord.Embed.Empty)] = discord.Embed.Empty,
                      title: Union[str, type(discord.Embed.Empty)] = discord.Embed.Empty,
                      color: Union[discord.Color, type(discord.Embed.Empty)] = discord.Embed.Empty,
                      description: Union[str, type(discord.Embed.Empty)] = discord.Embed.Empty,
                      do_before_send: Callable[[discord.Embed], discord.Embed] = None):
    return [await ctx.send(embed=embed_to_send) for embed_to_send in
            await generate_embeds(embed, groups, first_name=first_name, timestamp=timestamp, title=title, color=color, description=description,
                                  do_before_send=do_before_send)]


async def generate_embeds_fields(embed: discord.Embed, fields: List[Union[Tuple[str, str], str]], *, field_name: str = "\u200b",
                                 timestamp: Union[datetime.datetime, type(discord.Embed.Empty)] = discord.Embed.Empty,
                                 title: Union[str, type(discord.Embed.Empty)] = discord.Embed.Empty,
                                 color: Union[discord.Color, type(discord.Embed.Empty)] = discord.Embed.Empty,
                                 description: Union[str, type(discord.Embed.Empty)] = discord.Embed.Empty,
                                 heading: str = "", template: str = "", ending: str = "", line_template: str = "",
                                 do_before_send: Callable[[discord.Embed], discord.Embed] = None, inline_fields: bool = True,
                                 regex: Optional[Pattern[str]] = None):
    embeds = []
    orig_embed = embed
    for num, field in enumerate(fields.copy()):
        if not isinstance(field, tuple):
            fields[num] = (field_name, field)
    if not title:
        title = embed.title + " (continued)"
    if not color:
        color = embed.colour
    while fields:
        data = fields.pop(0)
        key, value = data
        key = str(key)
        value = str(value)
        groups = await break_into_groups(value, heading=heading, template=template, ending=ending, line_template=line_template, regex=regex)
        inline = inline_fields
        if len(groups) > 1:
            inline = False
        if (len(embed.fields) + len(groups)) <= 25:
            for num, value in enumerate(groups, start=1):
                new_embed = copy.deepcopy(embed)
                new_embed.add_field(name=key if num <= 1 else "\u200b", value=value, inline=inline)
                if len(new_embed) > 6000:
                    embed = do_before_send(embed) if do_before_send else embed
                    embeds.append(embed)
                    embed = discord.Embed(timestamp=timestamp, title=title, color=color, description=description)
                    for item in filter(lambda slot: slot.startswith("_") and slot != "_fields", discord.Embed.__slots__):
                        if hasattr(orig_embed, item):
                            setattr(embed, item, getattr(orig_embed, item))
                    embed.add_field(name=key if num <= 1 else "\u200b", value=value, inline=inline)
                else:
                    embed = new_embed
        else:
            if len(embed.fields) > 0:
                embed = do_before_send(embed) if do_before_send else embed
                embeds.append(embed)
                embed = discord.Embed(timestamp=timestamp, title=title, color=color, description=description)
                for item in filter(lambda slot: slot.startswith("_") and slot != "_fields", discord.Embed.__slots__):
                    if hasattr(orig_embed, item):
                        setattr(embed, item, getattr(orig_embed, item))
            for num, value in enumerate(groups, start=1):
                new_embed = copy.deepcopy(embed)
                new_embed.add_field(name=key if num <= 1 else "\u200b", value=value, inline=inline)
                if len(new_embed) > 6000 or len(new_embed.fields) > 25:
                    embed = do_before_send(embed) if do_before_send else embed
                    embeds.append(embed)
                    embed = discord.Embed(timestamp=timestamp, title=title, color=color, description=description)
                    for item in filter(lambda slot: slot.startswith("_") and slot != "_fields", discord.Embed.__slots__):
                        if hasattr(orig_embed, item):
                            setattr(embed, item, getattr(orig_embed, item))
                    embed.add_field(name=key if num <= 1 else "\u200b", value=value, inline=inline)
                else:
                    embed = new_embed
    if len(embed.fields) > 0:
        embed = do_before_send(embed) if do_before_send else embed
        embeds.append(embed)
    return embeds


async def send_embeds_fields(ctx: discord.abc.Messageable, embed: discord.Embed, fields: List[Union[Tuple[str, str], str]], *,
                             field_name: str = "\u200b",
                             timestamp: Union[datetime.datetime, type(discord.Embed.Empty)] = discord.Embed.Empty,
                             title: Union[str, type(discord.Embed.Empty)] = discord.Embed.Empty,
                             color: Union[discord.Color, type(discord.Embed.Empty)] = discord.Embed.Empty,
                             description: Union[str, type(discord.Embed.Empty)] = discord.Embed.Empty,
                             heading: str = "", template: str = "", ending: str = "", line_template: str = "",
                             do_before_send: Callable[[discord.Embed], discord.Embed] = None, inline_fields: bool = True,
                             regex: Optional[Pattern[str]] = None):
    return [await ctx.send(embed=embed_to_send) for embed_to_send in
            await generate_embeds_fields(embed, fields, field_name=field_name, timestamp=timestamp, title=title, color=color, description=description,
                                         heading=heading, template=template, ending=ending, line_template=line_template,
                                         do_before_send=do_before_send, inline_fields=inline_fields, regex=regex)]
