from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


def _to_lagos(dt: datetime, fmt: str = "%d %b %Y %H:%M") -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo("Africa/Lagos")).strftime(fmt)


templates.env.filters["lagos"] = _to_lagos
