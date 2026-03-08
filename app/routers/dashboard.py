from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..auth import lecturer_or_admin
from ..database import get_db
from ..models import (
    AuditAction,
    Course,
    Exam,
    PlagiarismJob,
    ReviewDecision,
    ReviewStatus,
    Role,
    SimilarityPair,
    Submission,
    User,
)
from ..services.audit import log as audit
from ..templates import templates

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

lagos = ZoneInfo("Africa/Lagos")
utc = ZoneInfo("UTC")


def _dept_courses(user: User, db: Session) -> list[Course]:
    if user.role == Role.admin:
        return db.query(Course).order_by(Course.code).all()
    return db.query(Course).filter_by(department_id=user.department_id).order_by(Course.code).all()


def _assert_exam_access(exam: Exam, user: User) -> None:
    if user.role == Role.admin:
        return
    if exam.course.department_id != user.department_id:
        raise HTTPException(status_code=403, detail="Not your department")


def _highlight(text: str, spans: list[tuple[int, int]]) -> list[dict]:
    if not text or not spans:
        return [{"text": text, "highlighted": False}]
    spans = sorted(set(spans))
    result, pos = [], 0
    for start, end in spans:
        if pos < start:
            result.append({"text": text[pos:start], "highlighted": False})
        result.append({"text": text[start:end], "highlighted": True})
        pos = end
    if pos < len(text):
        result.append({"text": text[pos:], "highlighted": False})
    return result


# --- Home ---


@router.get("/", response_class=HTMLResponse)
def dashboard_home(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    courses = _dept_courses(user, db)
    return templates.TemplateResponse(
        "dashboard/home.html",
        {"request": request, "user": user, "courses": courses},
    )


# --- Course detail ---


@router.get("/courses/{course_id}", response_class=HTMLResponse)
def course_detail(
    course_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404)
    if user.role == Role.lecturer and course.department_id != user.department_id:
        raise HTTPException(status_code=403, detail="Not your department")
    return templates.TemplateResponse(
        "dashboard/course.html",
        {"request": request, "user": user, "course": course},
    )


# --- Exam creation ---


@router.get("/exams/new", response_class=HTMLResponse)
def new_exam_form(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
    course_id: int | None = None,
):
    courses = _dept_courses(user, db)
    return templates.TemplateResponse(
        "dashboard/exam_new.html",
        {
            "request": request,
            "user": user,
            "courses": courses,
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
    courses = _dept_courses(user, db)

    def _err(msg: str):
        return templates.TemplateResponse(
            "dashboard/exam_new.html",
            {
                "request": request,
                "user": user,
                "courses": courses,
                "error": msg,
                "preselect_course": course_id,
            },
            status_code=400,
        )

    course = db.get(Course, course_id)
    if not course:
        return _err("Course not found.")
    if user.role == Role.lecturer and course.department_id != user.department_id:
        return _err("You don't have access to that course.")

    try:
        opens = (
            datetime.fromisoformat(opens_at)
            .replace(tzinfo=lagos)
            .astimezone(utc)
            .replace(tzinfo=None)
        )
        closes = (
            datetime.fromisoformat(closes_at)
            .replace(tzinfo=lagos)
            .astimezone(utc)
            .replace(tzinfo=None)
        )
    except ValueError:
        return _err("Invalid date format.")

    if closes <= opens:
        return _err("Closing time must be after opening time.")

    exam = Exam(
        course_id=course_id,
        title=title,
        description=description or None,
        opens_at=opens,
        closes_at=closes,
        allowed_formats=allowed_formats,
        max_file_mb=max_file_mb,
        similarity_threshold=similarity_threshold,
    )
    db.add(exam)
    db.commit()
    audit(db, AuditAction.exam_created, user_id=user.id, target_id=exam.id, target_type="exam")
    return RedirectResponse(url=f"/dashboard/exams/{exam.id}", status_code=303)


# --- Exam detail ---


@router.get("/exams/{exam_id}", response_class=HTMLResponse)
def exam_detail(
    exam_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
    min_score: float = 0.3,
):
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404)
    _assert_exam_access(exam, user)

    audit(
        db,
        AuditAction.report_viewed,
        user_id=user.id,
        target_id=exam_id,
        target_type="exam",
        ip_address=request.client.host if request.client else None,
    )

    job = db.query(PlagiarismJob).filter_by(exam_id=exam_id).first()
    submissions = (
        db.query(Submission)
        .filter_by(exam_id=exam_id)
        .order_by(Submission.uploaded_at.desc())
        .all()
    )
    sub_ids = [s.id for s in submissions]
    pairs = (
        db.query(SimilarityPair)
        .filter(
            SimilarityPair.submission_a_id.in_(sub_ids),
            SimilarityPair.similarity_score >= min_score,
        )
        .order_by(SimilarityPair.similarity_score.desc())
        .all()
        if sub_ids
        else []
    )

    return templates.TemplateResponse(
        "dashboard/exam.html",
        {
            "request": request,
            "user": user,
            "exam": exam,
            "job": job,
            "submissions": submissions,
            "pairs": pairs,
            "min_score": min_score,
            "now": datetime.now(UTC).replace(tzinfo=None),
        },
    )


# --- Pair detail ---


@router.get("/pairs/{pair_id}", response_class=HTMLResponse)
def pair_detail(
    pair_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    pair = db.get(SimilarityPair, pair_id)
    if not pair:
        raise HTTPException(status_code=404)

    sub_a = db.get(Submission, pair.submission_a_id)
    sub_b = db.get(Submission, pair.submission_b_id)
    if not sub_a or not sub_b:
        raise HTTPException(status_code=404)

    _assert_exam_access(sub_a.exam, user)

    highlights_a = _highlight(
        sub_a.extracted_text or "", [(f.start_a, f.end_a) for f in pair.fragments]
    )
    highlights_b = _highlight(
        sub_b.extracted_text or "", [(f.start_b, f.end_b) for f in pair.fragments]
    )

    return templates.TemplateResponse(
        "dashboard/pair.html",
        {
            "request": request,
            "user": user,
            "pair": pair,
            "sub_a": sub_a,
            "sub_b": sub_b,
            "highlights_a": highlights_a,
            "highlights_b": highlights_b,
        },
    )


# --- Pair review ---


@router.post("/pairs/{pair_id}/review", response_class=HTMLResponse)
def review_pair(
    pair_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
    status: str = Form(...),
    notes: str = Form(""),
):
    pair = db.get(SimilarityPair, pair_id)
    if not pair:
        raise HTTPException(status_code=404)

    sub_a = db.get(Submission, pair.submission_a_id)
    _assert_exam_access(sub_a.exam, user)

    try:
        review_status = ReviewStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid review status") from ValueError

    review = pair.review or ReviewDecision(pair_id=pair_id)
    review.reviewer_id = user.id
    review.status = review_status
    review.notes = notes or None
    review.decided_at = datetime.now(UTC)
    if not pair.review:
        db.add(review)
    db.commit()

    audit(db, AuditAction.review_decision, user_id=user.id, target_id=pair_id, target_type="pair")
    return RedirectResponse(url=f"/dashboard/pairs/{pair_id}", status_code=303)
