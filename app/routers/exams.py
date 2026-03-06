from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, lecturer_or_admin
from ..database import get_db
from ..models import AuditAction, Course, Enrollment, Exam, Role, User
from ..schemas import ExamCreate, ExamOut
from ..services.audit import log as audit

router = APIRouter(prefix="/exams", tags=["exams"])


def _assert_course_access(course_id: int, user: User, db: Session) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if user.role == Role.lecturer and course.department_id != user.department_id:
        raise HTTPException(status_code=403, detail="Not your department")
    return course


@router.post("/", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
def create_exam(
    body: ExamCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    _assert_course_access(body.course_id, user, db)
    exam = Exam(**body.model_dump())
    db.add(exam)
    db.commit()
    db.refresh(exam)
    audit(db, AuditAction.exam_created, user_id=user.id, target_id=exam.id, target_type="exam")
    return exam


@router.get("/", response_model=list[ExamOut])
def list_exams(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if user.role == Role.admin:
        return db.query(Exam).all()
    if user.role == Role.lecturer:
        course_ids = [
            c.id for c in db.query(Course).filter_by(department_id=user.department_id).all()
        ]
        return db.query(Exam).filter(Exam.course_id.in_(course_ids)).all()
    # student: only exams for enrolled courses, within open window
    now = datetime.now(UTC).replace(tzinfo=None)
    enrolled_ids = [e.course_id for e in db.query(Enrollment).filter_by(student_id=user.id).all()]
    return (
        db.query(Exam)
        .filter(
            Exam.course_id.in_(enrolled_ids),
            Exam.opens_at <= now,
            Exam.closes_at >= now,
        )
        .all()
    )


@router.get("/{exam_id}", response_model=ExamOut)
def get_exam(
    exam_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam