from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..auth import lecturer_or_admin
from ..database import get_db
from ..models import ReviewStatus, User
from ..services import dashboard as dash_svc
from ..templates import templates

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
def dashboard_home(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    return templates.TemplateResponse(
        "dashboard/home.html",
        {
            "request": request,
            "user": user,
            "courses": dash_svc.get_courses(db, user),
        },
    )


@router.get("/courses/{course_id}", response_class=HTMLResponse)
def course_detail(
    course_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    from fastapi import HTTPException

    from ..models import Role
    from ..repositories import course as course_repo

    course = course_repo.get(db, course_id)
    if user.role == Role.lecturer and course.department_id != user.department_id:
        raise HTTPException(status_code=403)
    return templates.TemplateResponse(
        "dashboard/course.html", {"request": request, "user": user, "course": course}
    )


@router.get("/exams/new", response_class=HTMLResponse)
def new_exam_form(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
    course_id: int | None = None,
):
    return templates.TemplateResponse(
        "dashboard/exam_new.html",
        {
            "request": request,
            "user": user,
            "courses": dash_svc.get_courses(db, user),
            "error": None,
            "preselect_course": course_id,
        },
    )


@router.post("/exams/new", response_class=HTMLResponse)
async def create_exam(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
    course_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    opens_at: str = Form(...),
    closes_at: str = Form(...),
    allowed_formats: str = Form("pdf,docx,txt"),
    max_file_mb: int = Form(10),
    similarity_threshold: float = Form(0.4),
):
    from fastapi import HTTPException

    try:
        exam = dash_svc.create_exam(
            db,
            user,
            course_id=course_id,
            title=title,
            description=description,
            opens_at=opens_at,
            closes_at=closes_at,
            allowed_formats=allowed_formats,
            max_file_mb=max_file_mb,
            similarity_threshold=similarity_threshold,
        )
    except HTTPException as exc:
        return templates.TemplateResponse(
            "dashboard/exam_new.html",
            {
                "request": request,
                "user": user,
                "courses": dash_svc.get_courses(db, user),
                "error": exc.detail,
                "preselect_course": course_id,
            },
            status_code=400,
        )
    return RedirectResponse(url=f"/dashboard/exams/{exam.id}", status_code=303)


@router.get("/exams/{exam_id}", response_class=HTMLResponse)
def exam_detail(
    exam_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
    min_score: float = 0.3,
):
    ip = request.client.host if request.client else None
    ctx = dash_svc.get_exam_detail(db, exam_id, user, min_score, ip)
    return templates.TemplateResponse(
        "dashboard/exam.html", {"request": request, "user": user, **ctx}
    )


@router.get("/pairs/{pair_id}", response_class=HTMLResponse)
def pair_detail(
    pair_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    ctx = dash_svc.get_pair_detail(db, pair_id, user)
    return templates.TemplateResponse(
        "dashboard/pair.html",
        {
            "request": request,
            "user": user,
            "review_statuses": [s.value for s in ReviewStatus],
            **ctx,
        },
    )


@router.post("/pairs/{pair_id}/review", response_class=HTMLResponse)
def review_pair(
    pair_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
    status: str = Form(...),
    notes: str = Form(""),
):
    dash_svc.review_pair(db, pair_id, user, status, notes)
    return RedirectResponse(url=f"/dashboard/pairs/{pair_id}", status_code=303)
