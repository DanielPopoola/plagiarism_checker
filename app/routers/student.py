from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import AuditAction, Exam, Role, SimilarityPair, Submission, User
from ..services.audit import log as audit

router = APIRouter(prefix="/student", tags=["student"])
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
def student_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if user.role != Role.student:
        raise HTTPException(status_code=403, detail="Students only")

    from datetime import UTC, datetime

    from ..models import Enrollment

    now = datetime.now(UTC).replace(tzinfo=None)
    enrolled_course_ids = [
        e.course_id for e in db.query(Enrollment).filter_by(student_id=user.id).all()
    ]
    open_exams = (
        db.query(Exam)
        .filter(
            Exam.course_id.in_(enrolled_course_ids),
            Exam.opens_at <= now,
            Exam.closes_at >= now,
        )
        .all()
        if enrolled_course_ids
        else []
    )
    submissions = (
        db.query(Submission)
        .filter_by(student_id=user.id)
        .order_by(Submission.uploaded_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "student/dashboard.html",
        {
            "request": request,
            "user": user,
            "open_exams": open_exams,
            "submissions": submissions,
        },
    )


@router.get("/exams/{exam_id}/submit", response_class=HTMLResponse)
def submit_form(
    exam_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if user.role != Role.student:
        raise HTTPException(status_code=403, detail="Students only")

    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    from datetime import UTC, datetime

    now = datetime.now(UTC).replace(tzinfo=None)
    if not (exam.opens_at <= now <= exam.closes_at):
        raise HTTPException(status_code=400, detail="Submission window is not open")

    return templates.TemplateResponse(
        "student/submit.html",
        {"request": request, "user": user, "exam": exam, "error": None},
    )


@router.post("/exams/{exam_id}/submit", response_class=HTMLResponse)
async def submit_file(
    exam_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if user.role != Role.student:
        raise HTTPException(status_code=403, detail="Students only")

    from ..routers.submissions import upload_submission

    form = await request.form()
    file: UploadFile = form.get("file")
    if not file:
        exam = db.get(Exam, exam_id)
        return templates.TemplateResponse(
            "student/submit.html",
            {"request": request, "user": user, "exam": exam, "error": "No file selected."},
            status_code=400,
        )

    try:
        await upload_submission(exam_id=exam_id, file=file, db=db, user=user)
    except HTTPException as exc:
        exam = db.get(Exam, exam_id)
        return templates.TemplateResponse(
            "student/submit.html",
            {"request": request, "user": user, "exam": exam, "error": exc.detail},
            status_code=exc.status_code,
        )

    audit(
        db,
        AuditAction.submission_upload,
        user_id=user.id,
        target_id=exam_id,
        target_type="exam",
        ip_address=request.client.host if request.client else None,
    )
    return RedirectResponse(url="/student/dashboard", status_code=303)


@router.get("/submissions/{submission_id}", response_class=HTMLResponse)
def submission_detail(
    submission_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if user.role != Role.student:
        raise HTTPException(status_code=403, detail="Students only")

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

    audit(
        db,
        AuditAction.report_viewed,
        user_id=user.id,
        target_id=submission_id,
        target_type="submission",
    )

    return templates.TemplateResponse(
        "student/submission.html",
        {
            "request": request,
            "user": user,
            "sub": sub,
            "exam": sub.exam,
            "pairs": pairs,
        },
    )
