from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    AuditAction,
    Course,
    Enrollment,
    Exam,
    Role,
    SimilarityPair,
    Submission,
    User,
)
from ..services.audit import log as audit

router = APIRouter(prefix="/student", tags=["student"])
templates = Jinja2Templates(directory="templates")


def _require_student(user: User) -> None:
    if user.role != Role.student:
        raise HTTPException(status_code=403, detail="Students only")


# --- Dashboard ---

@router.get("/dashboard", response_class=HTMLResponse)
def student_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    now = datetime.now(UTC).replace(tzinfo=None)

    enrolled_ids = [e.course_id for e in db.query(Enrollment).filter_by(student_id=user.id).all()]
    open_exams = (
        db.query(Exam)
        .filter(
            Exam.course_id.in_(enrolled_ids),
            Exam.opens_at <= now,
            Exam.closes_at >= now,
        )
        .all()
        if enrolled_ids else []
    )
    submission_count = db.query(Submission).filter_by(student_id=user.id).count()

    return templates.TemplateResponse(
        "student/dashboard.html",
        {
            "request": request,
            "user": user,
            "open_exams": open_exams,
            "enrolled_count": len(enrolled_ids),
            "submission_count": submission_count,
        },
    )


# --- Courses ---

@router.get("/courses", response_class=HTMLResponse)
def browse_courses(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    enrolled_ids = {e.course_id for e in db.query(Enrollment).filter_by(student_id=user.id).all()}
    courses = (
        db.query(Course)
        .filter_by(department_id=user.department_id)
        .order_by(Course.code)
        .all()
    )
    return templates.TemplateResponse(
        "student/courses.html",
        {"request": request, "user": user, "courses": courses, "enrolled_ids": enrolled_ids},
    )


@router.post("/courses/{course_id}/enroll", response_class=HTMLResponse)
def enroll(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.department_id != user.department_id:
        raise HTTPException(status_code=403, detail="Course is not in your department")
    db.add(Enrollment(student_id=user.id, course_id=course_id))
    try:
        db.commit()
        audit(db, AuditAction.enrollment_created, user_id=user.id, target_id=course_id, target_type="course")
    except IntegrityError:
        db.rollback()
    return RedirectResponse(url="/student/courses", status_code=303)


@router.post("/courses/{course_id}/unenroll", response_class=HTMLResponse)
def unenroll(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    e = db.query(Enrollment).filter_by(student_id=user.id, course_id=course_id).first()
    if e:
        db.delete(e)
        db.commit()
    return RedirectResponse(url="/student/courses", status_code=303)


# --- Submit ---

@router.get("/exams/{exam_id}/submit", response_class=HTMLResponse)
def submit_form(
    exam_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    now = datetime.now(UTC).replace(tzinfo=None)
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    if not (exam.opens_at <= now <= exam.closes_at):
        raise HTTPException(status_code=400, detail="Submission window is not open")
    enrolled = db.query(Enrollment).filter_by(student_id=user.id, course_id=exam.course_id).first()
    if not enrolled:
        raise HTTPException(status_code=403, detail="You are not enrolled in this course")
    existing = db.query(Submission).filter_by(exam_id=exam_id, student_id=user.id).first()
    return templates.TemplateResponse(
        "student/submit.html",
        {"request": request, "user": user, "exam": exam, "error": None, "existing": existing},
    )


@router.post("/exams/{exam_id}/submit", response_class=HTMLResponse)
async def submit_file(
    exam_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    from ..routers.submissions import upload_submission

    # Block duplicate submission
    if db.query(Submission).filter_by(exam_id=exam_id, student_id=user.id).first():
        exam = db.get(Exam, exam_id)
        return templates.TemplateResponse(
            "student/submit.html",
            {"request": request, "user": user, "exam": exam,
             "error": "You have already submitted for this exam.", "existing": True},
            status_code=400,
        )

    form = await request.form()
    file: UploadFile = form.get("file")
    if not file:
        exam = db.get(Exam, exam_id)
        return templates.TemplateResponse(
            "student/submit.html",
            {"request": request, "user": user, "exam": exam, "error": "No file selected.", "existing": None},
            status_code=400,
        )

    try:
        await upload_submission(exam_id=exam_id, file=file, db=db, user=user)
    except HTTPException as exc:
        exam = db.get(Exam, exam_id)
        return templates.TemplateResponse(
            "student/submit.html",
            {"request": request, "user": user, "exam": exam, "error": exc.detail, "existing": None},
            status_code=exc.status_code,
        )

    audit(
        db, AuditAction.submission_upload, user_id=user.id,
        target_id=exam_id, target_type="exam",
        ip_address=request.client.host if request.client else None,
    )
    return RedirectResponse(url="/student/dashboard", status_code=303)


# --- Submissions ---

@router.get("/submissions", response_class=HTMLResponse)
def submission_list(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    submissions = (
        db.query(Submission)
        .filter_by(student_id=user.id)
        .order_by(Submission.uploaded_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "student/submissions.html",
        {"request": request, "user": user, "submissions": submissions},
    )


@router.get("/submissions/{submission_id}", response_class=HTMLResponse)
def submission_detail(
    submission_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    _require_student(user)
    sub = db.get(Submission, submission_id)
    if not sub or sub.student_id != user.id:
        raise HTTPException(status_code=404, detail="Submission not found")

    pairs = (
        db.query(SimilarityPair)
        .filter(
            (SimilarityPair.submission_a_id == submission_id)
            | (SimilarityPair.submission_b_id == submission_id)
        )
        .order_by(SimilarityPair.similarity_score.desc())
        .all()
    )
    audit(db, AuditAction.report_viewed, user_id=user.id, target_id=submission_id, target_type="submission")
    return templates.TemplateResponse(
        "student/submission.html",
        {"request": request, "user": user, "sub": sub, "exam": sub.exam, "pairs": pairs},
    )