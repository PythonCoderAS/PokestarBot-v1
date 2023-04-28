Get a chat log of all messages before the specified time.

Arguments:
* `channel`: The channel where the messages are located. Defaults to the current channel.
* `number`: The number of messages to get. Defaults to all messages.
* `time`: The time to delete before. Can be provided in multiple formats.

__**Note: All times in NY time. This defaults to EDT (UTC-4) during Daylight Savings and EST (UTC-5) otherwise. Refer to a [Timezone Converter](https://www.thetimezoneconverter.com/) for conversions.**__

Channel Format: `#<channel-name>` / `<channel-name>` / `channel_id`

Time Formats:
* Date only: `M/D/YY` / `MM/DD/YYYY` / `M-D-YY` / `MN-DD-YYYY` (Assumed to begin at midnight for that day)
* Time only: `H:M:S` / `HH:MM:SS` / `H-M-S` / `HH-MM-SS` / `H:M:S AM/PM` / `HH:MM:SS AM/PM` / `H-M-S AM/PM` / `HH-MM-SS AM/PM` / `H:M:SAM/PM` / `HH:MM:SSAM/PM` / `H-M-SAM/PM` / `HH-MM-SSAM/PM` (Assumed to be today)
Note: If AM/PM is not provided, it is assumed to be 24-hour time.
* Date and time: A combination of the Date and Time only formats, with Date before time.
* Today: `today` (Assumed to begin at midnight for that day)
* Yesterday: `yesterday`
* Day of the week: `Sunday` / `Monday` / `Tuesday` / `Wednesday` / `Thursday` / `Friday` / `Saturday` (Assumed to begin at midnight for that day)
* X days ago: `x` where x is a number. (Assumed to begin at midnight for that day)

Examples:
* `{prefix}chat_log before_time today`
* `{prefix}chat_log before_time #general today`
* `{prefix}chat_log before_time 5 today`
* `{prefix}chat_log before_time #general 5 today`
* `{prefix}chat_log before_time yesterday`
* `{prefix}chat_log before_time sunday`
* `{prefix}chat_log before_time 5`
* `{prefix}chat_log before_time 9/2/20`
* `{prefix}chat_log before_time 23:00:00`
* `{prefix}chat_log before_time 11:00:00 PM`
* `{prefix}chat_log before_time 9/2/20 07:00:00 PM`
