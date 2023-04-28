Add a channel to the guild-channel database (must have **manage channels**).

Arguments:
* `name`: The name of the channel type. This name is not the name of the channel *on the Guild*, but rather the name of the *type of channel*. You can get a list of valid names from `{prefix}channel list`.
* `channel`: The actual channel that represents the name.

Channel Format: `#<channel-name>` / `<channel-name>` / `channel_id`

Examples:
* `{prefix}channel add bot-spam #bot-spam`
* `{prefix}channel add bot-spam #bot-stuff`
