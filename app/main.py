from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .routers import admin, auth, courses, dashboard, exams, reports, student, submissions
from .schemas import TokenOut, UserCreate, UserOut
from .services.auth import login, register

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
def root():
    return RedirectResponse(url="/login")


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
