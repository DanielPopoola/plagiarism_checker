from datetime import datetime

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .timezone import to_wat

templates = Jinja2Templates(directory="templates")

_template_response = templates.TemplateResponse


def _compat_template_response(*args, **kwargs):
    """Support both old and new Starlette TemplateResponse signatures.

    Old call style used across the app:
        TemplateResponse("name.html", {"request": request, ...}, status_code=...)

    New Starlette call style:
        TemplateResponse(request, "name.html", {...}, status_code=...)
    """
    if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], dict):
        name = args[0]
        context = args[1]
        request = kwargs.pop("request", None) or context.get("request")
        if not isinstance(request, Request):
            raise ValueError(
                "Template context must include a valid 'request' object when using "
                "TemplateResponse(name, context, ...)"
            )
        return _template_response(request, name, context, *args[2:], **kwargs)
    return _template_response(*args, **kwargs)


templates.TemplateResponse = _compat_template_response


def _to_lagos(dt: datetime, fmt: str = "%d %b %Y %H:%M") -> str:
    if dt is None:
        return ""
    return to_wat(dt).strftime(fmt)


templates.env.filters["lagos"] = _to_lagos
templates.env.globals["to_wat"] = to_wat
