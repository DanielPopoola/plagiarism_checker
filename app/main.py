from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .auth import get_current_user_optional
from .database import Base, engine, get_db
from .models import User
from .routers import admin, auth, courses, dashboard, exams, reports, student, submissions
from .schemas import TokenOut, UserCreate, UserOut
from .services.auth import login, register
from .templates import templates

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Plagiarism Detection System")

for router in [
    auth.router,
    courses.router,
    exams.router,
    submissions.router,
    reports.router,
    dashboard.router,
    student.router,
    admin.router,
]:
    app.include_router(router)


@app.get("/")
def root(
    request: Request,
    user: Annotated[User | None, Depends(get_current_user_optional)],
):
    if user:
        redirect_map = {"student": "/student/dashboard", "admin": "/admin/"}
        return RedirectResponse(url=redirect_map.get(user.role, "/dashboard/"))
    return templates.TemplateResponse("landing.html", {"request": request})


@app.post("/auth/token", response_model=TokenOut)
def login_api(
    db: Annotated[Session, Depends(get_db)], form: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    try:
        user, token = login(db, form.username, form.password, ip=None)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials"
        ) from None
    return {"access_token": token, "token_type": "bearer"}


@app.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register_api(body: UserCreate, db: Annotated[Session, Depends(get_db)]):
    return register(db, body.email, body.name, body.password, body.role, body.department_id)
