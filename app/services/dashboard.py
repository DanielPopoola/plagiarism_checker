from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import AuditAction, Course, Exam, PlagiarismJob, ReviewDecision, ReviewStatus, User
from ..repositories import exam as exam_repo
from ..repositories import pair as pair_repo
from ..repositories import submission as sub_repo
from ..services.audit import log as audit

lagos = ZoneInfo("Africa/Lagos")
utc = ZoneInfo("UTC")


def get_courses(db: Session, user: User) -> list[Course]:
    from ..repositories import course as course_repo

    return course_repo.list_for_user(db, user)


def create_exam(
    db: Session,
    user: User,
    *,
    course_id: int,
    title: str,
    description: str,
    opens_at: str,
    closes_at: str,
    allowed_formats: str,
    max_file_mb: int,
    similarity_threshold: float,
) -> Exam:
    from ..models import Role
    from ..repositories import course as course_repo

    course = course_repo.get(db, course_id)
    if user.role == Role.lecturer and course.department_id != user.department_id:
        raise HTTPException(status_code=403, detail="You don't have access to that course.")
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
        raise HTTPException(status_code=400, detail="Invalid date format.") from None
    if closes <= opens:
        raise HTTPException(status_code=400, detail="Closing time must be after opening time.")
    return exam_repo.create(
        db,
        course_id=course_id,
        title=title,
        description=description or None,
        opens_at=opens,
        closes_at=closes,
        allowed_formats=allowed_formats,
        max_file_mb=max_file_mb,
        similarity_threshold=similarity_threshold,
        actor_id=user.id,
    )


def get_exam_detail(
    db: Session, exam_id: int, user: User, min_score: float, ip: str | None
) -> dict:
    exam = exam_repo.get(db, exam_id)
    exam_repo.assert_access(exam, user)
    audit(
        db,
        AuditAction.report_viewed,
        user_id=user.id,
        target_id=exam_id,
        target_type="exam",
        ip_address=ip,
    )
    job = db.query(PlagiarismJob).filter_by(exam_id=exam_id).first()
    submissions = sub_repo.list_by_exam(db, exam_id)
    pairs = pair_repo.list_by_exam(db, exam_id, min_score)
    return {
        "exam": exam,
        "job": job,
        "submissions": submissions,
        "pairs": pairs,
        "now": datetime.now(UTC).replace(tzinfo=None),
    }


def get_pair_detail(db: Session, pair_id: int, user: User) -> dict:
    pair = pair_repo.get(db, pair_id)
    sub_a = sub_repo.get(db, pair.submission_a_id)
    sub_b = sub_repo.get(db, pair.submission_b_id)
    exam_repo.assert_access(sub_a.exam, user)
    return {
        "pair": pair,
        "sub_a": sub_a,
        "sub_b": sub_b,
        "highlights_a": _highlight(
            sub_a.extracted_text or "", [(f.start_a, f.end_a) for f in pair.fragments]
        ),
        "highlights_b": _highlight(
            sub_b.extracted_text or "", [(f.start_b, f.end_b) for f in pair.fragments]
        ),
    }


def review_pair(db: Session, pair_id: int, user: User, status: str, notes: str) -> None:
    pair = pair_repo.get(db, pair_id)
    sub_a = sub_repo.get(db, pair.submission_a_id)
    exam_repo.assert_access(sub_a.exam, user)
    try:
        review_status = ReviewStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid review status") from None
    review = pair.review or ReviewDecision(pair_id=pair_id)
    review.reviewer_id = user.id
    review.status = review_status
    review.notes = notes or None
    review.decided_at = datetime.now(UTC)
    if not pair.review:
        db.add(review)
    db.commit()
    audit(db, AuditAction.review_decision, user_id=user.id, target_id=pair_id, target_type="pair")


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
