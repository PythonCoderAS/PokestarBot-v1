Get a chat log of all messages before the specified message.

Arguments:
* `channel`: The channel where the messages are located. Defaults to the current channel.
* `message`: The message to get messages from before. This message will *not* be included.
* `number`: The number of messages to get. Defaults to all messages.

Channel Format: `#<channel-name>` / `<channel-name>` / `channel_id`

Message Format:
* Message Link (such as `https://discordapp.com/channels/1/2/3`, but with real IDs).
* Message ID (such as `762456412801859596`).

Examples:
* `{prefix}chat_log before https://discordapp.com/channels/757973999446655078/761054274296873011/762137632620019722`
* `{prefix}chat_log before #general https://discordapp.com/channels/757973999446655078/761054274296873011/762137632620019722`
* `{prefix}chat_log before https://discordapp.com/channels/757973999446655078/761054274296873011/762137632620019722 30`
* `{prefix}chat_log before #general https://discordapp.com/channels/757973999446655078/761054274296873011/762137632620019722 30`
