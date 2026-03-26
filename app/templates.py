from datetime import datetime

from fastapi.templating import Jinja2Templates

from .timezone import to_wat

templates = Jinja2Templates(directory="templates")


def _to_lagos(dt: datetime, fmt: str = "%d %b %Y %H:%M") -> str:
    if dt is None:
        return ""
    return to_wat(dt).strftime(fmt)


templates.env.filters["lagos"] = _to_lagos
templates.env.globals["to_wat"] = to_wat
