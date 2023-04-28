Get a chat log of all messages between the specified times.

Arguments:
* `channel`: The channel where the messages are located. Defaults to the current channel.
* `number`: The number of messages to get. Defaults to all messages.
* `after_time`: Chat messages after this time will be saved.
* `before_time`: Chat messages before this time will be saved.

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
* `{prefix}chat_log between_time yesterday today`
* `{prefix}chat_log between_time #general yesterday today`
* `{prefix}chat_log between_time #general 50 today`
* `{prefix}chat_log between_time sunday tuesday`
* `{prefix}chat_log between_time 5 2`
* `{prefix}chat_log between_time 9/2/20 9/5/20`
* `{prefix}chat_log between_time 23:00:00 23:30:00`
* `{prefix}chat_log between_time "11:00:00 PM" "11:30:00 PM"`
* `{prefix}chat_log between_time "9/2/20 11:00:00 PM" "9/5/20 11:30:00 PM"`
