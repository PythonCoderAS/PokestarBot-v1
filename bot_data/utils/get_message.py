import inspect
import types

import discord.ext.commands


def get_context_variables(break_on_message: bool = True):
    frame = inspect.currentframe()
    user = channel = command = msg = ctx = None
    while frame.f_back is not None:
        for key, value in frame.f_locals.copy().items():
            if isinstance(value, discord.ext.commands.Context):
                user = value.author
                channel = value.channel
                command = value.command
                msg = value.message
                ctx = value
                break
            elif isinstance(value, discord.Message):
                if break_on_message:
                    user = value.author
                    channel = value.channel
                    msg = value
                    break
                else:
                    msg = value
        frame = frame.f_back
    if msg and not command:
        user = msg.author
        channel = msg.channel
    return user, channel, command, msg, ctx


def get_context_variables_from_traceback(traceback: types.TracebackType, break_on_message: bool = True):
    user = channel = command = msg = ctx = None
    while traceback.tb_next is not None:
        frame = traceback.tb_frame
        for key, value in frame.f_locals.copy().items():
            if isinstance(value, discord.ext.commands.Context):
                user = value.author
                channel = value.channel
                command = value.command
                msg = value.message
                ctx = value
                break
            elif isinstance(value, discord.Message):
                if break_on_message:
                    user = value.author
                    channel = value.channel
                    msg = value
                    break
                else:
                    msg = value
        traceback = traceback.tb_next
    if msg and not command:
        user = msg.author
        channel = msg.channel
    return user, channel, command, msg, ctx
