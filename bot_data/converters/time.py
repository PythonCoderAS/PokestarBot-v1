import datetime
import re
from typing import Dict, Optional

import discord.ext.commands
import pytz
from ..utils import HubContext

NY = pytz.timezone("America/New_York")


class TimeConverter(discord.ext.commands.Converter):
    DATE_REGEX = re.compile(r"^([0-9]{1,2})([/-])([0-9]{1,2})(?:[/-])([0-9]{2,4})")
    TIME_REGEX = re.compile(r"^([0-9]{1,2})([:-])([0-9]{1,2})(?:[:-])([0-9]{1,2})((?: |)[AP]M|)")
    WORD_DATA = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}

    @staticmethod
    def day_data(day) -> Dict[int, int]:
        return {day: 7, (day + 1) % 7: 6, (day + 2) % 7: 5, (day + 3) % 7: 4, (day + 4) % 7: 3, (day + 5) % 7: 2, (day + 6) % 7: 1}

    @staticmethod
    def convert_offset(dt: datetime.datetime) -> datetime.datetime:
        offset = NY.utcoffset(datetime.datetime.utcnow())
        return dt - offset

    @staticmethod
    def ny_time(dt: Optional[datetime.datetime] = None) -> datetime.datetime:
        dt = dt or datetime.datetime.utcnow()
        offset = NY.utcoffset(datetime.datetime.utcnow())
        return dt + offset

    @classmethod
    def day(cls, days: float = 0) -> datetime.datetime:
        base_dt = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC).astimezone(tz=NY)
        data = base_dt.year, base_dt.month, base_dt.day
        return cls.convert_offset(datetime.datetime(*data)) - datetime.timedelta(days=days)

    @classmethod
    def get_weekday(cls, weekday: str) -> datetime.datetime:
        val = cls.WORD_DATA[weekday]
        current_day = cls.day().weekday()
        return cls.day(cls.day_data(current_day)[val])

    async def convert(self, ctx: HubContext, argument: str) -> datetime.datetime:
        now = self.ny_time()
        if argument.lower() == "today":
            day = self.day()
            YMD = day.strptime("%D")
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Returning 12:00 AM on {YMD} in NY time.", data=ctx.bot.datetime_data(day))
        elif argument.lower() == "yesterday":
            ctx.hub.add_breadcrumb(category="Argument Parsing", message="Returning 12:00 AM yesterday in NY time.", data=ctx.bot.datetime_data(day))
            day = self.day(1)
            YMD = day.strptime("%D")
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Returning 12:00 AM on {YMD} in NY time.", data=ctx.bot.datetime_data(day))
        elif argument.lower() in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
            day = self.get_weekday(argument.lower())
            YMD = day.strptime("%D")
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Returning 12:00 AM on {YMD} in NY time.", data=ctx.bot.datetime_data(day))
        elif argument.isdecimal():
            num = float(argument)
            day = self.day(num)
            date = day.strftime("%D %I:%M:%S %p")
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Returning {date} in NY time.", data=ctx.bot.datetime_data(day))
        elif " " in argument:
            date, sep, time = argument.upper().partition(" ")
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Identified date and time portions", level="debug", data={"date": date, "time": time})
            if match := self.DATE_REGEX.match(argument.upper()): # Date Time
                month, d_symbol, day, year = match.group(1, 2, 3, 4)
                if len(year) == 3:
                    raise discord.ext.commands.BadArgument("Year cannot be 3 digits.")
                month = month.zfill(2)
                day = day.zfill(2)
                year = year.zfill(4)
                date_format = "%m{0}%d{0}%Y".format(d_symbol)
            else: # Time <AM/PM>
                if match := self.TIME_REGEX.match(argument.upper()):
                    hour, t_symbol, minute, second, am_or_pm = match.group(1, 2, 3, 4, 5)
                    hour = hour.zfill(2)
                    minute = minute.zfill(0)
                    second = second.zfill(0)
                    if am_or_pm:
                        if " " == am_or_pm[0]:
                            time_format = "%I{0}%M{0}%S %p".format(t_symbol)
                        else:
                            time_format = "%I{0}%M{0}%S %p".format(t_symbol)
                    else:
                        if int(hour) >= 12 and (now.hour - 12) >= 0:
                            time_format = "%I{0}%M{0}%S %p".format(t_symbol)
                            am_or_pm = "PM"
                        else:
                            time_format = "%H{0}%M{0}%S".format(t_symbol)
                    am_or_pm = am_or_pm.lstrip()
                    dt = datetime.datetime.strptime(f"{hour}{t_symbol}{minute}{t_symbol}{second} {am_or_pm}".rstrip(), time_format)
                    final_dt = dt.replace(year=now.year, month=now.month, day=now.day)
                    final_dt_parsed = final_dt.strftime("%D %I:%M:%S %p")
                    ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Returning {final_dt_parsed} in NY time.", data=ctx.bot.datetime_data(final_dt))
                    return final_dt
                else:
                    raise discord.ext.commands.BadArgument("Date argument is invalid.")
            if match2 := self.TIME_REGEX.match(time):
                hour, t_symbol, minute, second, am_or_pm = match2.group(1, 2, 3, 4, 5)
                hour = hour.zfill(2)
                minute = minute.zfill(0)
                second = second.zfill(0)
                if am_or_pm:
                    if " " == am_or_pm[0]:
                        time_format = "%I{0}%M{0}%S %p".format(t_symbol)
                    else:
                        time_format = "%I{0}%M{0}%S %p".format(t_symbol)
                else:
                    if abs((now - self.convert_offset(datetime.datetime(int(year), int(month), int(day)))).days) > 0:
                        raise discord.ext.commands.BadArgument("Ambiguous time format, provide AM or PM.")
                    if int(hour) <= 12 and (now.hour - 12 - int(hour)) >= 0:
                        time_format = "%I{0}%M{0}%S %p".format(t_symbol)
                        am_or_pm = "PM"
                    else:
                        time_format = "%H{0}%M{0}%S".format(t_symbol)
            else:
                raise discord.ext.commands.BadArgument("Time argument is invalid.")
            am_or_pm = am_or_pm.lstrip()
            combined_format = date_format + " " + time_format
            final_dt = datetime.datetime.strptime(
                f"{month}{d_symbol}{day}{d_symbol}{year} {hour}{t_symbol}{minute}{t_symbol}{second} {am_or_pm}".rstrip(),
                combined_format)
            final_dt_parsed = final_dt.strftime("%D %I:%M:%S %p")
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Returning {final_dt_parsed} in NY time.", data=ctx.bot.datetime_data(final_dt))
            return final_dt
        elif match := self.DATE_REGEX.match(argument.upper()):
            month, d_symbol, day, year = match.group(1, 2, 3, 4)
            if len(year) == 3:
                raise discord.ext.commands.BadArgument("Year cannot be 3 digits.")
            month = month.zfill(2)
            day = day.zfill(2)
            if len(year) == 2:
                year = "20" + year
            date_format = "%m{0}%d{0}%Y".format(d_symbol)
            final_dt = datetime.datetime.strptime(f"{month}{d_symbol}{day}{d_symbol}{year}", date_format)
            final_dt_parsed = final_dt.strftime("%D %I:%M:%S %p")
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Returning {final_dt_parsed} in NY time.",
                                   data=ctx.bot.datetime_data(final_dt))
            return final_dt
        elif match := self.TIME_REGEX.match(argument.upper()):
            hour, t_symbol, minute, second, am_or_pm = match.group(1, 2, 3, 4, 5)
            hour = hour.zfill(2)
            minute = minute.zfill(0)
            second = second.zfill(0)
            if am_or_pm:
                if " " == am_or_pm[0]:
                    time_format = "%I{0}%M{0}%S %p".format(t_symbol)
                else:
                    time_format = "%I{0}%M{0}%S %p".format(t_symbol)
            else:
                if int(hour) <= 12 and (now.hour - 12 - int(hour)) >= 0:
                    time_format = "%I{0}%M{0}%S %p".format(t_symbol)
                    am_or_pm = "AM"
                else:
                    time_format = "%H{0}%M{0}%S".format(t_symbol)
            am_or_pm = am_or_pm.lstrip()
            dt = datetime.datetime.strptime(f"{hour}{t_symbol}{minute}{t_symbol}{second} {am_or_pm}".rstrip(), time_format)
            final_dt = dt.replace(year=now.year, month=now.month, day=now.day)
            final_dt_parsed = final_dt.strftime("%D %I:%M:%S %p")
            ctx.hub.add_breadcrumb(category="Argument Parsing", message=f"Returning {final_dt_parsed} in NY time.",
                                   data=ctx.bot.datetime_data(final_dt))
        else:
            raise discord.ext.commands.BadArgument("Date format does not match any given date format.")
