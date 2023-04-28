import enum
import os
import re
from typing import Any, Callable, Coroutine, Union

import discord

from .creds import bot_client_id, github_token, support_code
from .version import bot_version  # NOQA


# const.py
class CHANNEL_TYPE(enum.IntEnum):
    TEXT_CHANNEL = 0
    CATEGORY_CHANNEL = 1
    VOICE_CHANNEL = 2


# bot.py
invalid_spoiler = re.compile(r"(?<!\|)(\|\|[^|]+\||\|[^|]+\|\|)(?!\|)", flags=re.UNICODE | re.MULTILINE | re.IGNORECASE)
url_regex = re.compile(
    r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s("
    r")<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))",
    flags=re.UNICODE | re.IGNORECASE)
warning_on_invalid_spoiler = "You seem to have posted improperly tagged spoilers. As a convenience, the bot has removed the spoiler for you in " \
                             "order to avoid accidentally spoiling other people. The next two messages contain the message and the raw markdown " \
                             "for it. If the message is >1000 characters, the raw markdown might not send. If the bot has made a mistake, " \
                             "send the *exact* same message again and it will not be removed. You can copy-paste and send the Markdown text in " \
                             "order to send the *exact* same message."
warning_on_failure = "You seem to have posted improperly tagged spoilers. The bot has tried to delete your message, but was forbidden from doing " \
                     "so. Please try to properly mark spoilers. Note that the spoiler syntax is `||<content>||`, where `<content>` is what you " \
                     "want to be spoilered. Another option to mark spoilers is to start your message with `/spoiler`, but note that this spoilers " \
                     "your *entire* message. You *cannot* use `/spoiler` partway into a message."
quote = re.compile(r"^[\s>]+")
bad_argument_regex = re.compile(r'Converting to "([\S]+)" failed for parameter "([\S]+)".')
on_reaction_func_type = Callable[
    [discord.Message, Union[discord.PartialEmoji, discord.Emoji], Union[discord.Member, discord.User]], Coroutine[None, None, Any]]

# utils/post_issue.py
GITHUB_HEADERS = {"Accept": "application/vnd.github.v3+json", "Authorization": f"token {github_token}"}

# help.py
help_file_dir = os.path.abspath(os.path.join(__file__, "..", "man"))
help_file_template = "* `{}{}`: **{}**"
support_line = f"*Need help? Join the bot support server: https://discord.gg/{support_code}* • *Invite the bot: [Link](" \
               f"https://discord.com/oauth2/authorize?client_id={bot_client_id}&permissions=8&scope=bot)* • *GitHub Repo: " \
               f"https://github.com/PythonCoderAS/PokestarBot*\n\n"

# converters/MAL.py
ANIME_REGEX = re.compile(r"https://myanimelist.net/anime/([0-9]+)")
ANIMELIST_REGEX = re.compile(r"https://myanimelist.net/animelist/([^\s/]+)")
MANGALIST_REGEX = re.compile(r"https://myanimelist.net/mangalist/([^\s/]+)")

# mal.py
MAL_API_PATH = "https://api.myanimelist.net/v2"
MAL_HEADERS = {"Content-Type": "application/json"}
MAL_ANIME_FIELDS = ['id', 'title', 'main_picture', 'alternative_titles', 'start_date', 'end_date', 'synopsis', 'mean', 'rank', 'popularity',
                    'num_list_users', 'num_scoring_users', 'nsfw', 'created_at', 'updated_at', 'media_type', 'status', 'genres', 'my_list_status',
                    'num_episodes', 'start_season', 'broadcast', 'source', 'average_episode_duration', 'rating']

# management.py
log_line = re.compile(r"\((DEBUG|INFO|WARNING|ERROR|CRITICAL)\):")
channel_types = {
    "Generic Bot Channels": {
        "announcements": ("Shows important announcements from the bot. Used to announce winners in Waifu Wars.", CHANNEL_TYPE.TEXT_CHANNEL),
        "bot-spam": ("The channel where bot commands are used. The bot should be able to speak here. This channel is used to alert users without "
                     "breaking the flow of another channel.", CHANNEL_TYPE.TEXT_CHANNEL)
    },
    "Misc. Bot Services": {
        "anime-and-manga-updates": ("Needed for the Anime and Manga Updates system to work.", CHANNEL_TYPE.TEXT_CHANNEL),
        "message-goals": ("Shows alerts every time a certain amount of messages are sent to a channel or by a user.", CHANNEL_TYPE.TEXT_CHANNEL),
        "admin-log": ("The channel where events are logged that should only be seen by mods/admins (invite usage information, "
                      "role additions/deletions, etc.)", CHANNEL_TYPE.TEXT_CHANNEL),
        "private-channel": ("A **discord category** in order to house any private channels. Otherwise will not go into any categories at all.",
                            CHANNEL_TYPE.CATEGORY_CHANNEL)
    },
    "Reddit Services": {
        "modqueue": ("The channel where new items of a subreddit's moderation queue are sent. Unneeded unless you're pairing a subreddit to"
                     "this Guild.", CHANNEL_TYPE.TEXT_CHANNEL),
        "unmoderated": ("The channel where new items of a subreddit's unmoderated list are sent. Unneeded unless you're pairing a subreddit to"
                        "this Guild.", CHANNEL_TYPE.TEXT_CHANNEL),
        "modlog": ("The channel where new items of a subreddit's moderation log are sent. Unneeded unless you're pairing a subreddit to this"
                   "Guild.", CHANNEL_TYPE.TEXT_CHANNEL)
    }
}
hideable_channel_types = {"admin-log"}
writeable_channel_types = {"bot-spam", *channel_types.get("Reddit Services", {})}
option_types = {
    "bot_spam": ("Commands in Bot Spam Channel Only", True,
                 "Ensure commands only get executed in a provided channel. This does not count the message expansion commands."),
    "color": ("Color on Join", False, "Assign members a random color role on join. (Requires the `admin-log` Guild-Channel mapping)"),
    "snapshot": ("Snapshot on Leave", True, "Generates a snapshot of a user when they leave or get kicked/banned."),
    "submission": (
        "Expand Submission Links", True,
        "Treat any links to reddit submissions as if they were called with the `submission` command, and expands them."),
    "comment": (
        "Expand Comment Links", True, "Treat any links to reddit comments as if they were called with the `comment` command, and expands them."),
    "subreddit": ("Expand Subreddit Links", False,
                  "Treat any links to reddit subreddits (a direct link or `r/<name>`) as if they were called with the `subreddit` command, "
                  "and expands them, **but leaves out the subreddit's description**."),
    "user": ("Expand User Links", False,
             "Treat any links to reddit users (a direct link or `u/<name>`) as if they were called with the `user` command, and expands them."),
    "message_txt": ("Expand message.txt Files", True, "Any message.txt files that are sent will have the contents displayed using Embeds."),
    "mangadex": ("Expand MangaDex Links", True,
                 "Treat any links to mangadex manga (not chapters) as if they were called with the `mangadex` command, and expand them."),
    "guyamoe": ("Expand guya.moe Links", True,
                "Treat any links to guya.moe manga (not chapters) as if they were called with the `guyamoe` command, and expand them."),
    "nyaasi": ("Expand nyaa.si Links", True,
               "Treat any links to nyaa.si torrents by HorribleSubs as if they were called with the `nyaasi` command, and expand them."),
    "invalid_spoiler": ("Delete Invalid Spoilers", True,
                        "If a message with an invalid spoiler tag (such as `||test|`) is sent, it will be deleted and the user will be warned. A "
                        "copy of the message is also sent. If the bot has made an error, they can send the exact same message again, "
                        "and it won't get deleted by the bot."),
    "paisley_delete": ("Delete `-ad` messages from Paisley Park", True,
                       "If the bot sees a message with `-ad` from Paisley Park, it will delete the message silently."),
    "warn_mass_delete": ("Warn Before Mass Delete", True, "Warn the user and prompt for confirmation when calling a mass delete command."),
    "warn_replay": ("Warn Before Replay Mode", True, "Warn the user and prompt for confirmation when calling a replay mode command."),
    "warn_kick": ("Warn Before Kick", True, "Warn the user and prompt for confirmation before mass-kicking users."),
    "invite_track": ("Track Invite Usage", True,
                     "Similar to InviteManager, track invites, and who joins using which invite. Requires the admin-log Guild-Channel mapping.")
}

# reddit.py
subreddit = re.compile("r/([A-Za-z0-9_]{1,21})")
user = re.compile("(?:user|u)/([A-Za-z0-9_]{1,32})")
blockquote = re.compile(r"^>([^\s>])", re.MULTILINE | re.IGNORECASE | re.UNICODE)

# redditmod.py
submittable_actions = {
    "approvelink": "Approved Submission",
    "approvecomment": "Approved Comment",
    "ignorereports": "Ignored Reports For Item",
    "removelink": "Removed Link",
    "removecomment": "Removed Comment",
    "sticky": "Stickied Item",
    "distinguish": "Distinguished Item",
    "spamcomment": "Spam Comment",
    "spamlink": "Spam Link",
    "unsticky": "Unstickied Item",
    "lock": "Locked Item",
    "unlock": "Unlocked Item",
    "marknsfw": "Marked Item as NSFW",
    "unignorereports": "Unignored Reports For Item",
    "spoiler": "Marked Item As Spoiler",
    "unspoiler": "Unmarked Item As Spoiler",
    "editflair": "Edit Flair Of Item"
}
user_actions = {
    "addcontributor": "Add Contributor",
    "banuser": "Ban User",
    "muteuser": "Mute User",
    "removecontributor": "Remove Contributor",
    "acceptmoderatorinvite": "Accept Moderator Invite",
    "invitemoderator": "Invite Moderator",
    "unbanuser": "Unban User",
    "unmuteuser": "Unmute User",
    "setpermissions": "Set User Permissions"
}

# role.py
user_template_role = "* {}\n"
role_template_role = "* **{}**: {} members\n"
discord_colors = {
    'blue': '#3498db', 'blurple': '#7289da', 'dark_blue': '#206694', 'dark_gold': '#c27c0e', 'dark_gray': '#607d8b', 'dark_green': '#1f8b4c',
    'dark_grey': '#607d8b', 'dark_magenta': '#ad1457', 'dark_orange': '#a84300', 'dark_purple': '#71368a', 'dark_red': '#992d22',
    'dark_teal': '#11806a', 'darker_gray': '#546e7a', 'darker_grey': '#546e7a', 'default': '#000000', 'gold': '#f1c40f', 'green': '#2ecc71',
    'greyple': '#99aab5', 'light_gray': '#979c9f', 'light_grey': '#979c9f', 'lighter_gray': '#95a5a6', 'lighter_grey': '#95a5a6',
    'magenta': '#e91e63', 'orange': '#e67e22', 'purple': '#9b59b6', 'red': '#e74c3c', 'teal': '#1abc9c'
}
css_colors = {
    'aliceblue': '#f0f8ff', 'antiquewhite': '#faebd7', 'aqua': '#00ffff', 'aquamarine': '#7fffd4', 'azure': '#f0ffff', 'beige': '#f5f5dc',
    'bisque': '#ffe4c4', 'black': '#000000', 'blanchedalmond': '#ffebcd', 'blueviolet': '#8a2be2', 'brown': '#a52a2a', 'burlywood': '#deb887',
    'cadetblue': '#5f9ea0', 'chartreuse': '#7fff00', 'chocolate': '#d2691e', 'coral': '#ff7f50', 'cornflowerblue': '#6495ed', 'cornsilk': '#fff8dc',
    'crimson': '#dc143c', 'cyan': '#00ffff', 'darkblue': '#00008b', 'darkcyan': '#008b8b', 'darkgoldenrod': '#b8860b', 'darkgray': '#a9a9a9',
    'darkgrey': '#a9a9a9', 'darkgreen': '#006400', 'darkkhaki': '#bdb76b', 'darkmagenta': '#8b008b', 'darkolivegreen': '#556b2f',
    'darkorange': '#ff8c00', 'darkorchid': '#9932cc', 'darkred': '#8b0000', 'darksalmon': '#e9967a', 'darkseagreen': '#8fbc8f',
    'darkslateblue': '#483d8b', 'darkslategray': '#2f4f4f', 'darkslategrey': '#2f4f4f', 'darkturquoise': '#00ced1', 'darkviolet': '#9400d3',
    'deeppink': '#ff1493', 'deepskyblue': '#00bfff', 'dimgray': '#696969', 'dimgrey': '#696969', 'dodgerblue': '#1e90ff', 'firebrick': '#b22222',
    'floralwhite': '#fffaf0', 'forestgreen': '#228b22', 'fuchsia': '#ff00ff', 'gainsboro': '#dcdcdc', 'ghostwhite': '#f8f8ff', 'goldenrod': '#daa520',
    'gray': '#808080', 'grey': '#808080', 'greenyellow': '#adff2f', 'honeydew': '#f0fff0', 'hotpink': '#ff69b4', 'indianred': '#cd5c5c',
    'indigo': '#4b0082', 'ivory': '#fffff0', 'khaki': '#f0e68c', 'lavender': '#e6e6fa', 'lavenderblush': '#fff0f5', 'lawngreen': '#7cfc00',
    'lemonchiffon': '#fffacd', 'lightblue': '#add8e6', 'lightcoral': '#f08080', 'lightcyan': '#e0ffff', 'lightgoldenrodyellow': '#fafad2',
    'lightgray': '#d3d3d3', 'lightgrey': '#d3d3d3', 'lightgreen': '#90ee90', 'lightpink': '#ffb6c1', 'lightsalmon': '#ffa07a',
    'lightseagreen': '#20b2aa', 'lightskyblue': '#87cefa', 'lightslategray': '#778899', 'lightslategrey': '#778899', 'lightsteelblue': '#b0c4de',
    'lightyellow': '#ffffe0', 'lime': '#00ff00', 'limegreen': '#32cd32', 'linen': '#faf0e6', 'maroon': '#800000', 'mediumaquamarine': '#66cdaa',
    'mediumblue': '#0000cd', 'mediumorchid': '#ba55d3', 'mediumpurple': '#9370db', 'mediumseagreen': '#3cb371', 'mediumslateblue': '#7b68ee',
    'mediumspringgreen': '#00fa9a', 'mediumturquoise': '#48d1cc', 'mediumvioletred': '#c71585', 'midnightblue': '#191970', 'mintcream': '#f5fffa',
    'mistyrose': '#ffe4e1', 'moccasin': '#ffe4b5', 'navajowhite': '#ffdead', 'navy': '#000080', 'oldlace': '#fdf5e6', 'olive': '#808000',
    'olivedrab': '#6b8e23', 'orangered': '#ff4500', 'orchid': '#da70d6', 'palegoldenrod': '#eee8aa', 'palegreen': '#98fb98',
    'paleturquoise': '#afeeee', 'palevioletred': '#db7093', 'papayawhip': '#ffefd5', 'peachpuff': '#ffdab9', 'peru': '#cd853f', 'pink': '#ffc0cb',
    'plum': '#dda0dd', 'powderblue': '#b0e0e6', 'rebeccapurple': '#663399', 'rosybrown': '#bc8f8f', 'royalblue': '#4169e1', 'saddlebrown': '#8b4513',
    'salmon': '#fa8072', 'sandybrown': '#f4a460', 'seagreen': '#2e8b57', 'seashell': '#fff5ee', 'sienna': '#a0522d', 'silver': '#c0c0c0',
    'skyblue': '#87ceeb', 'slateblue': '#6a5acd', 'slategray': '#708090', 'slategrey': '#708090', 'snow': '#fffafa', 'springgreen': '#00ff7f',
    'steelblue': '#4682b4', 'tan': '#d2b48c', 'thistle': '#d8bfd8', 'tomato': '#ff6347', 'turquoise': '#40e0d0', 'violet': '#ee82ee',
    'wheat': '#f5deb3', 'white': '#ffffff', 'whitesmoke': '#f5f5f5', 'yellow': '#ffff00', 'yellowgreen': '#9acd32'
}
color_str_set = set("#0123456789abcdef")
bland_colors = {'ghostwhite', 'slategrey', 'azure', 'default', 'white', 'ivory', 'mistyrose', 'darkgrey', 'papayawhip', 'oldlace', 'dark_gray',
                'seashell', 'slategray', 'gainsboro', 'lighter_gray', 'cornsilk', 'floralwhite', 'aliceblue', 'linen', 'honeydew', 'beige', 'snow',
                'black', 'blanchedalmond', 'lavenderblush', 'light_gray', 'darkgray', 'whitesmoke', 'bisque', 'light_grey', 'darker_grey',
                'lighter_grey', 'dark_grey', 'mintcream', 'antiquewhite', 'darker_gray', 'lavender', 'wheat', 'navajowhite'}

# stats.py
stats_template = "* **{}**{}: **{}** messages (max **{}** messages)"

# time.py
strftime_format = "%A, %B %d, %Y at %I:%M:%S %p"

# updates.py
guyamoe = re.compile(r"https://(?:www\.|)guya\.moe/read/manga/([^/\s]+)")
mangadex = re.compile(r"https://(?:www\.|)mangadex\.org/(?:title|manga)/([0-9]+)")
nyaasi = re.compile(r"https://nyaa.si/(?:view|download)/([0-9]+)")


# waifu.py
page_regex = re.compile(r"^Page ([0-9]+) of ([0-9]+) ")

# waifu_old.py
class Status(enum.IntEnum):
    ALL = 0
    OPEN = 1
    VOTABLE = 2
    LOCKED = 4
    CLOSED = 3
