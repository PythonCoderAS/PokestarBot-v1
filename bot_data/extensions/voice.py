import asyncio
import logging
import os
import platform
from typing import Optional, TYPE_CHECKING

import discord.ext.commands
import discord.ext.tasks
import pyttsx3

from . import PokestarBotCog
from ..utils import Embed, StopCommand, loop_command_deco

if TYPE_CHECKING:
    from ..bot import PokestarBot

logger = logging.getLogger(__name__)


class Voice(PokestarBotCog):

    @property
    def voice_players(self):
        return self.bot.voice_players

    def __init__(self, bot: "PokestarBot"):
        super().__init__(bot)
        self.bot.voice_players = {}
        self.clean_up_voice_clients.start()
        self.cleanup_mp3s.start()

    async def get_audio_file(self, message: str, message_id: int):
        if platform.system().lower() == 'darwin':
            return await self.use_pyttsx3(message, message_id)
        else:
            return await self.use_espeak_ng(message, message_id)

    async def use_pyttsx3(self, message: str, message_id: int):
        engine = pyttsx3.init()
        engine.save_to_file(message, str(message_id) + ".mp3")
        engine.runAndWait()
        return str(message_id) + ".mp3"

    async def use_espeak_ng(self, message: str, message_id: int):
        subprocess = await asyncio.create_subprocess_exec("espeak-ng", "-v", "us-mbrola-1", "-w", str(message_id) + ".wav",
                                                          '"{}"'.format(message.replace('"', '\\"')))
        await subprocess.wait()
        return str(message_id) + ".wav"

    @discord.ext.commands.command(brief="Say something in a voice channel", usage="message", aliases=["announce"])
    @discord.ext.commands.guild_only()
    async def say(self, ctx: discord.ext.commands.Context, *, message: str):
        voice_channel: Optional[discord.VoiceChannel] = getattr(ctx.author.voice, "channel", None)
        if voice_channel is None:
            embed = Embed(ctx, title="Not In Voice Channel", description="The calling user is not in a voice channel.", color=discord.Color.red())
            return await ctx.send(embed=embed)
        voice_client: Optional[discord.VoiceClient] = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice_client and voice_client.is_connected():
            if voice_client.is_playing() or voice_client.is_paused():
                embed = Embed(ctx, title="Already Playing",
                              description="The bot is already playing (or paused) in the server. Wait for it to finish playing, or stop playback.",
                              color=discord.Color.red())
                embed.add_field(name="Voice Channel", value=str(voice_client.channel))
                return await ctx.send(embed=embed)
            elif voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)
        else:
            voice_client = await voice_channel.connect()
        embed = Embed(ctx, title="Generating TTS audio", color=discord.Color.green())
        await ctx.send(embed=embed)
        filename = await self.get_audio_file(ctx.author.display_name + " says: " + message, ctx.message.id)
        self.voice_players[voice_channel] = ctx.author
        embed = Embed(ctx, title="Playing Message", description=ctx.author.display_name + " says: " + message, color=discord.Color.green())
        await ctx.send(embed=embed)
        voice_client.play(discord.FFmpegOpusAudio(filename, bitrate=int(voice_channel.bitrate / 1000)))

    async def voice_validation(self, ctx: discord.ext.commands.Context, word: str):
        voice_channel: Optional[discord.VoiceChannel] = getattr(ctx.author.voice, "channel", None)
        if voice_channel is None:
            embed = Embed(ctx, title="Not In Voice Channel", description="The calling user is not in a voice channel.", color=discord.Color.red())
            await ctx.send(embed=embed)
            raise StopCommand
        voice_client: Optional[discord.VoiceClient] = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if not (voice_client and voice_client.is_connected()):
            embed = Embed(ctx, title="Not Connected", description="The bot is not connected to the Guild.", color=discord.Color.red())
            await ctx.send(embed=embed)
            raise StopCommand
        if voice_client.channel != voice_channel:
            embed = Embed(ctx, title="Channel Mismatch",
                          description=f"The bot is playing/paused in a different channel. Join that channel to {word.lower()} playback.",
                          color=discord.Color.red())
            embed.add_field(name="Voice Channel", value=str(voice_client.channel))
            await ctx.send(embed=embed)
            raise StopCommand
        if not (self.voice_players[voice_channel] == ctx.author or voice_channel.permissions_for(ctx.author).mute_members):
            embed = Embed(ctx, title=f"Unable to {word.title()}",
                          description=f"Only the user who started the playback or a person with the `Mute Members` permission for the voice channel "
                                      f"can {word.lower()} playback.",
                          color=discord.Color.red())
            embed.add_field(name="Voice Channel", value=str(voice_client.channel))
            await ctx.send(embed=embed)
            raise StopCommand
        return voice_channel, voice_client

    @discord.ext.commands.command(brief="Stop bot's playback")
    @discord.ext.commands.guild_only()
    async def stop(self, ctx: discord.ext.commands.Context):
        voice_channel, voice_client = await self.voice_validation(ctx, "stop")
        voice_client.stop()
        embed = Embed(ctx, title="Stopped Playback", description="Playback has been stopped.", color=discord.Color.green())
        embed.add_field(name="Voice Channel", value=str(voice_client.channel))
        embed.add_field(name="Starting User", value=self.voice_players[voice_channel].mention)
        return await ctx.send(embed=embed)

    @discord.ext.commands.command(brief="Pause bot's playback")
    @discord.ext.commands.guild_only()
    async def pause(self, ctx: discord.ext.commands.Context):
        voice_channel, voice_client = await self.voice_validation(ctx, "pause")
        voice_client.pause()
        embed = Embed(ctx, title="Paused Playback", description="Playback has been paused.", color=discord.Color.green())
        embed.add_field(name="Voice Channel", value=str(voice_client.channel))
        embed.add_field(name="Starting User", value=self.voice_players[voice_channel].mention)
        return await ctx.send(embed=embed)

    @discord.ext.commands.command(brief="Resume bot's playback")
    @discord.ext.commands.guild_only()
    async def resume(self, ctx: discord.ext.commands.Context):
        voice_channel, voice_client = await self.voice_validation(ctx, "resume")
        voice_client.pause()
        embed = Embed(ctx, title="Resumed Playback", description="Playback has been resumed.", color=discord.Color.green())
        embed.add_field(name="Voice Channel", value=str(voice_client.channel))
        embed.add_field(name="Starting User", value=self.voice_players[voice_channel].mention)
        return await ctx.send(embed=embed)

    @discord.ext.tasks.loop(minutes=10)
    async def cleanup_mp3s(self):
        for file in os.listdir(os.getcwd()):
            if file.endswith(".mp3") or file.endswith(".wav"):
                os.remove(file)

    @cleanup_mp3s.error
    async def on_cleanup_mp3s_error(self, exception: BaseException):
        return await self.bot.on_error("cleanup_mp3s")

    @discord.ext.tasks.loop(minutes=1)
    async def clean_up_voice_clients(self):
        await self.bot.wait_until_ready()
        for client in self.bot.voice_clients:
            client: discord.VoiceClient
            if not client.is_playing() and client.is_connected():
                await client.disconnect(force=True)

    @clean_up_voice_clients.error
    async def on_clean_up_voice_clients_error(self, exception: BaseException):
        await self.bot.on_error("clean_up_voice_clients")

    @loop_command_deco(clean_up_voice_clients)
    @discord.ext.commands.group(brief="Get the cleanup loop statistics")
    @discord.ext.commands.is_owner()
    @discord.ext.commands.dm_only()
    async def cleanup_loop(self, ctx: discord.ext.commands.Context):
        await self.bot.loop_stats(ctx, self.clean_up_voice_clients, "Clean Up Voice Clients")

    @loop_command_deco(cleanup_mp3s)
    @discord.ext.commands.group(brief="Get the mp3 loop statistics")
    @discord.ext.commands.is_owner()
    @discord.ext.commands.dm_only()
    async def mp3_loop(self, ctx: discord.ext.commands.Context):
        await self.bot.loop_stats(ctx, self.cleanup_mp3s, "Clean Up mp3s")


def setup(bot: "PokestarBot"):
    bot.add_cog(Voice(bot))
    logger.info("Loaded the Voice extension.")


def teardown(_bot: "PokestarBot"):
    logger.warning("Unloading the Voice extension.")
