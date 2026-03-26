from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, lecturer_or_admin
from ..database import get_db
from ..models import Role, User
from ..repositories import exam as exam_repo
from ..schemas import ExamCreate, ExamOut
from ..timezone import to_utc_naive

router = APIRouter(prefix="/exams", tags=["exams"])


@router.post("/", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
def create_exam(
    body: ExamCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    from ..repositories import course as course_repo

    course = course_repo.get(db, body.course_id)
    if user.role == Role.lecturer and course.department_id != user.department_id:
        raise HTTPException(status_code=403, detail="Not your department")
    payload = body.model_dump()
    payload["opens_at"] = to_utc_naive(payload["opens_at"])
    payload["closes_at"] = to_utc_naive(payload["closes_at"])
    return exam_repo.create(db, **payload, actor_id=user.id)


@router.get("/", response_model=list[ExamOut])
def list_exams(
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]
):
    if user.role == Role.admin:
        from ..models import Exam

        return db.query(Exam).all()
    if user.role == Role.lecturer:
        from ..repositories import course as course_repo

        course_ids = [c.id for c in course_repo.list_for_user(db, user)]
        from ..models import Exam

        return db.query(Exam).filter(Exam.course_id.in_(course_ids)).all()
    return exam_repo.list_open_for_student(db, user.id)


@router.get("/{exam_id}", response_model=ExamOut)
def get_exam(
    exam_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    exam = exam_repo.get(db, exam_id)
    exam_repo.assert_access(exam, user)
    return exam
