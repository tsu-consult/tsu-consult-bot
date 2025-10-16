from datetime import datetime

def format_time(t: str) -> str:
    try:
        return datetime.strptime(t, "%H:%M:%S").strftime("%H:%M")
    except ValueError:
        return t