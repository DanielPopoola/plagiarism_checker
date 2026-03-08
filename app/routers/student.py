from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Role, User
from ..services import student as student_svc
from ..services import submission as sub_svc
from ..templates import templates

router = APIRouter(prefix="/student", tags=["student"])


def _require_student(user: User) -> None:
    if user.role != Role.student:
        raise HTTPException(status_code=403, detail="Students only")


@router.get("/dashboard", response_class=HTMLResponse)
def student_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    ctx = student_svc.get_dashboard_data(db, user)
    return templates.TemplateResponse(
        "student/dashboard.html", {"request": request, "user": user, **ctx}
    )


@router.get("/courses", response_class=HTMLResponse)
def browse_courses(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    ctx = student_svc.browse_courses(db, user)
    return templates.TemplateResponse(
        "student/courses.html", {"request": request, "user": user, **ctx}
    )


@router.get("/courses/{course_id}", response_class=HTMLResponse)
def course_detail(
    course_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    ctx = student_svc.get_course_detail(db, course_id, user)
    return templates.TemplateResponse(
        "student/course.html", {"request": request, "user": user, **ctx}
    )


@router.post("/courses/{course_id}/enroll", response_class=HTMLResponse)
def enroll(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    student_svc.enroll_student(db, course_id, user)
    return RedirectResponse(url="/student/courses", status_code=303)


@router.post("/courses/{course_id}/unenroll", response_class=HTMLResponse)
def unenroll(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    student_svc.unenroll_student(db, course_id, user)
    return RedirectResponse(url="/student/courses", status_code=303)


@router.get("/exams/{exam_id}/submit", response_class=HTMLResponse)
def submit_form(
    exam_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    ctx = student_svc.get_submit_form_data(db, exam_id, user)
    return templates.TemplateResponse(
        "student/submit.html", {"request": request, "user": user, "error": None, **ctx}
    )


@router.post("/exams/{exam_id}/submit", response_class=HTMLResponse)
async def submit_file(
    exam_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    form = await request.form()
    file: UploadFile = form.get("file")

    def _err(msg: str, status: int = 400):
        from ..repositories import exam as exam_repo

        exam = exam_repo.get(db, exam_id)
        return templates.TemplateResponse(
            "student/submit.html",
            {"request": request, "user": user, "exam": exam, "error": msg, "existing": None},
            status_code=status,
        )

    if not file:
        return _err("No file selected.")
    try:
        sub_svc.upload(db, exam_id, file, user, request.client.host if request.client else None)
    except HTTPException as exc:
        return _err(exc.detail, exc.status_code)
    return RedirectResponse(url="/student/dashboard", status_code=303)


@router.get("/submissions", response_class=HTMLResponse)
def submission_list(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    from ..repositories import submission as sub_repo

    submissions = sub_repo.list_by_student(db, user.id)
    return templates.TemplateResponse(
        "student/submissions.html", {"request": request, "user": user, "submissions": submissions}
    )


@router.get("/submissions/{submission_id}", response_class=HTMLResponse)
def submission_detail(
    submission_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    ctx = student_svc.get_submission_detail(db, submission_id, user)
    return templates.TemplateResponse(
        "student/submission.html", {"request": request, "user": user, **ctx}
    )
