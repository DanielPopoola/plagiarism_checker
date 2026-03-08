from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Department
from ..services import auth as auth_svc
from ..templates import templates

router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    email: str = Form(...),
    password: str = Form(...),
):
    ip = request.client.host if request.client else None
    try:
        user, token = auth_svc.login(db, email, password, ip)
    except HTTPException as exc:
        return templates.TemplateResponse(
            "auth/login.html", {"request": request, "error": str(exc.detail)}, status_code=400
        )
    response = RedirectResponse(url=auth_svc.redirect_after_login(user.role), status_code=302)
    from ..config import settings

    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )
    return response


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    departments = db.query(Department).order_by(Department.name).all()
    return templates.TemplateResponse(
        "auth/register.html", {"request": request, "error": None, "departments": departments}
    )


@router.post("/register")
async def register_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    department_id: int | None = Form(None),
):
    try:
        auth_svc.register(db, email, name, password, role, department_id)
    except Exception as exc:
        return templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "error": str(exc.detail),
                "departments": db.query(Department).order_by(Department.name).all(),
            },
            status_code=400,
        )
    return RedirectResponse(url="/login", status_code=302)


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response
