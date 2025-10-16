from datetime import datetime
from babel.dates import format_date

def convert_12_to_24(time_str: str) -> str:
    if not time_str:
        return "—"
    try:
        dt = datetime.strptime(time_str.strip(), "%I:%M %p")
        return dt.strftime("%H:%M")
    except ValueError:
        try:
            dt = datetime.strptime(time_str.strip(), "%H:%M:%S")
            return dt.strftime("%H:%M")
        except ValueError:
            return time_str

def format_time(t: str) -> str:
    try:
        return convert_12_to_24(t)
    except (ValueError, TypeError):
        return t or "—"

def format_date_verbose(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        formatted = format_date(dt, format="EEEE, d MMMM, y", locale="ru")
        return formatted[0].upper() + formatted[1:]
    except (ValueError, TypeError):
        return date_str or "—"

def format_datetime_verbose(datetime_str: str) -> str:
    try:
        dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        date_part = format_date_verbose(dt.strftime("%Y-%m-%d"))
        time_part = convert_12_to_24(dt.strftime("%I:%M %p"))
        return f"{date_part}, {time_part}"
    except (ValueError, TypeError):
        return datetime_str or "—"
