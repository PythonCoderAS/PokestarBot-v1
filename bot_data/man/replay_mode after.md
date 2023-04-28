Replay all messages after a certain message.

Arguments:
* `channel`: The channel to scan for messages. Defaults to the current channel.
* `users`: The users that the messages have to be from. Defaults to all users. Multiple users can be provided, as long as they are separated by spaces.
* `message`: The message to start replay mode after. This message will *not* be replayed.
* `prefix`: The message prefix. Defaults to `{prefix}`.

Message Format:
* Message Link (such as `https://discordapp.com/channels/1/2/3`, but with real IDs).
* Message ID (such as `762456412801859596`).

Examples:
* `{prefix}replay_mode after https://discordapp.com/channels/757973999446655078/757977485207011418/762514813304700979`
* `{prefix}replay_mode after https://discordapp.com/channels/757973999446655078/757977485207011418/762514813304700979 {prefix}help`
* `{prefix}replay_mode after #general https://discordapp.com/channels/757973999446655078/757977485207011418/762514813304700979 {prefix}help`
* `{prefix}replay_mode after #general https://discordapp.com/channels/757973999446655078/757977485207011418/762514813304700979`
* `{prefix}replay_mode after #general @PokestarBot#9763 https://discordapp.com/channels/757973999446655078/757977485207011418/762514813304700979 {prefix}help`
* `{prefix}replay_mode after #general @PokestarBot#9763 https://discordapp.com/channels/757973999446655078/757977485207011418/762514813304700979`
* `{prefix}replay_mode after #general @PokestarBot#9763 @Rythm#3722 https://discordapp.com/channels/757973999446655078/757977485207011418/762514813304700979 {prefix}help`
* `{prefix}replay_mode after #general @PokestarBot#9763 @Rythm#3722 https://discordapp.com/channels/757973999446655078/757977485207011418/762514813304700979`
