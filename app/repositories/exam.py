from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import AuditAction, Enrollment, Exam, Role, User
from ..services.audit import log as audit
from ..timezone import utc_naive


def get(db: Session, exam_id: int) -> Exam:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404)
    return exam


def list_by_course(db: Session, course_id: int) -> list[Exam]:
    return db.query(Exam).filter_by(course_id=course_id).order_by(Exam.opens_at.desc()).all()


def list_open_for_student(db: Session, student_id: int) -> list[Exam]:
    now = utc_naive(datetime.now(UTC))
    enrolled_ids = [
        e.course_id for e in db.query(Enrollment).filter_by(student_id=student_id).all()
    ]
    if not enrolled_ids:
        return []
    return (
        db.query(Exam)
        .filter(Exam.course_id.in_(enrolled_ids), Exam.opens_at <= now, Exam.closes_at >= now)
        .all()
    )


def create(
    db: Session,
    *,
    course_id: int,
    title: str,
    description: str | None,
    opens_at: datetime,
    closes_at: datetime,
    allowed_formats: str,
    max_file_mb: int,
    similarity_threshold: float,
    actor_id: int,
) -> Exam:
    exam = Exam(
        course_id=course_id,
        title=title,
        description=description,
        opens_at=opens_at,
        closes_at=closes_at,
        allowed_formats=allowed_formats,
        max_file_mb=max_file_mb,
        similarity_threshold=similarity_threshold,
    )
    db.add(exam)
    db.commit()
    audit(db, AuditAction.exam_created, user_id=actor_id, target_id=exam.id, target_type="exam")
    return exam


def assert_access(exam: Exam, user: User) -> None:
    if user.role == Role.admin:
        return
    if exam.course.department_id != user.department_id:
        raise HTTPException(status_code=403, detail="Not your department")
