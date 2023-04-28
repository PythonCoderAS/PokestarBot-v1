from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

import discord.ext.commands.view
import sentry_sdk
from .custom_hub import CustomHub

if TYPE_CHECKING:
    from ..bot import PokestarBot


class DummyObject:
    __slots__ = ()

    def __getattr__(self, item):
        return None


obj = DummyObject()


class HubContext(discord.ext.commands.Context):

    bot: "PokestarBot"
    message: Optional[discord.Message]
    args: List[Any]
    kwargs: Dict[str, Any]
    prefix: Optional[str]
    command: Optional[discord.ext.commands.Command]
    view: Optional[discord.ext.commands.view.StringView]
    invoked_with: Optional[str]
    invoked_subcommand: Optional[discord.ext.commands.Command]
    subcommand_passed: Optional[str]
    command_failed: bool

    
    def set_to_dict(self, name: str, value: Any):
        self.__dict__[name] = value

    @property
    def cog(self) -> Optional[discord.ext.commands.Cog]:
        return super().cog

    @property
    def guild(self) -> Optional[discord.Guild]:
        return super().guild
    
    @guild.setter
    def guild(self, value: discord.Guild):
        self.set_to_dict("guild", value)

    @property
    def channel(self) -> Union[discord.TextChannel, discord.DMChannel]:
        return super().channel

    @channel.setter
    def channel(self, value: Union[discord.TextChannel, discord.DMChannel]):
        self.set_to_dict("channel", value)

    @property
    def author(self) -> Union[discord.Member, discord.User]:
        return super().author

    @author.setter
    def author(self, value: Union[discord.Member, discord.User]):
        self.set_to_dict("author", value)

    @property
    def me(self) -> Union[discord.Member, discord.ClientUser]:
        return super().me
    
    @me.setter
    def me(self, value: Union[discord.Member, discord.ClientUser]):
        self.set_to_dict("me", value)

    @property
    def voice_client(self) -> Optional[discord.VoiceClient]:
        return super().voice_client
    
    def __init__(self, **attrs):
        super().__init__(**attrs)
        self.hub = CustomHub(sentry_sdk.Hub.current)
        self.bot.hubs.append(self.hub)


class CustomContext(HubContext):
    _author: Optional[Union[discord.User, discord.Member]]
    _channel: Optional[discord.TextChannel]
    _cog: Optional[discord.ext.commands.Cog]
    _guild: Optional[discord.Guild]

    def __init__(self, **attrs):
        super().__init__(**({"message": obj, **attrs}))
        self._author = self._channel = self._cog = self._guild = None

    @property
    def author(self) -> Union[discord.User, discord.Member]:
        return self._author or super().author

    @author.setter
    def author(self, new_author: Union[discord.User, discord.Member]):
        self._author = new_author

    @property
    def channel(self) -> discord.TextChannel:
        return self._channel or super().channel

    @channel.setter
    def channel(self, new_channel: discord.TextChannel):
        self._channel = new_channel
        if not self._state:
            self._state = new_channel._state

    @property
    def cog(self):
        return self._cog or super().cog

    @cog.setter
    def cog(self, cog: discord.ext.commands.Cog):
        self._cog = cog

    @property
    def guild(self):
        return self._guild or super().guild

    @guild.setter
    def guild(self, guild: discord.Guild):
        self._guild = guild
        if not self._state:
            self._state = guild._state
