Replay all messages between two messages.

Arguments:
* `channel`: The channel to scan for messages. Defaults to the current channel.
* `users`: The users that the messages have to be from. Defaults to all users. Multiple users can be provided, as long as they are separated by spaces.
* `after_message`: The message to start replay mode after. This message will *not* be replayed.
* `before_message`: The message to start replay mode before. This message will *not* be replayed.
* `prefix`: The message prefix. Defaults to `{prefix}`.

Message Format:
* Message Link (such as `https://discordapp.com/channels/1/2/3`, but with real IDs).
* Message ID (such as `762456412801859596`).

Examples:
* `{prefix}replay_mode between https://discordapp.com/channels/757973999446655078/757977485207011418/762514813304700979 https://discordapp.com/channels/728750698816340028/729112537634832416/762652912819896330`
* `{prefix}replay_mode between https://discordapp.com/channels/757973999446655078/757977485207011418/762514813304700979 https://discordapp.com/channels/728750698816340028/729112537634832416/762652912819896330 {prefix}help`
* `{prefix}replay_mode between #general https://discordapp.com/channels/757973999446655078/757977485207011418/762514813304700979 https://discordapp.com/channels/728750698816340028/729112537634832416/762652912819896330 {prefix}help`
* `{prefix}replay_mode between #general @PokestarBot#9763 https://discordapp.com/channels/757973999446655078/757977485207011418/762514813304700979 https://discordapp.com/channels/728750698816340028/729112537634832416/762652912819896330 {prefix}help`
* `{prefix}replay_mode between #general @PokestarBot#9763 @Rythm#3722 https://discordapp.com/channels/757973999446655078/757977485207011418/762514813304700979 https://discordapp.com/channels/728750698816340028/729112537634832416/762652912819896330 {prefix}help`
