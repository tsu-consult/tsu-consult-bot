from datetime import datetime
from babel.dates import format_date

def format_time(t: str) -> str:
    try:
        return datetime.strptime(t, "%H:%M:%S").strftime("%H:%M")
    except ValueError:
        return t

def format_date_verbose(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        formatted = format_date(dt, format="EEEE, d MMMM, y", locale="ru")
        return formatted[0].upper() + formatted[1:]
    except ValueError:
        return date_str
