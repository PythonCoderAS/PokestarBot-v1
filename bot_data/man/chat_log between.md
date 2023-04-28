Get a chat log of all messages between the specified messages.

Arguments:
* `channel`: The channel where the messages are located. Defaults to the current channel.
* `after_message`: The message at the top. This message will *not* be included.
* `before_message`: The message at the bottom. This message will *not* be included.
* `number`: The number of messages to get. Defaults to all messages.

Examples:
* `{prefix}chat_log between https://discordapp.com/channels/728750698816340028/728756333150470195/752159027886161990 https://discordapp.com/channels/728750698816340028/728756333150470195/752159669681913886`
* `{prefix}chat_log between #general https://discordapp.com/channels/728750698816340028/728756333150470195/752159027886161990 https://discordapp.com/channels/728750698816340028/728756333150470195/752159669681913886`
* `{prefix}chat_log between #general 50 https://discordapp.com/channels/728750698816340028/728756333150470195/752159027886161990 https://discordapp.com/channels/728750698816340028/728756333150470195/752159669681913886`
