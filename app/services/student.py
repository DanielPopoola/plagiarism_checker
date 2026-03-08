from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import AuditAction, Course, Submission, User
from ..repositories import enrollment as enroll_repo
from ..repositories import exam as exam_repo
from ..repositories import pair as pair_repo
from ..repositories import submission as sub_repo
from ..services.audit import log as audit


def get_dashboard_data(db: Session, user: User) -> dict:
    open_exams = exam_repo.list_open_for_student(db, user.id)
    enrolled_count = len(enroll_repo.list_by_student(db, user.id))
    submission_count = db.query(Submission).filter_by(student_id=user.id).count()
    return {
        "open_exams": open_exams,
        "enrolled_count": enrolled_count,
        "submission_count": submission_count,
    }


def browse_courses(db: Session, user: User) -> dict:
    enrolled_ids = {e.course_id for e in enroll_repo.list_by_student(db, user.id)}
    courses = (
        db.query(Course).filter_by(department_id=user.department_id).order_by(Course.code).all()
    )
    return {"courses": courses, "enrolled_ids": enrolled_ids}


def get_course_detail(db: Session, course_id: int, user: User) -> dict:
    from datetime import UTC, datetime

    now = datetime.now(UTC).replace(tzinfo=None)
    course = db.get(Course, course_id)
    if not course or course.department_id != user.department_id:
        raise HTTPException(status_code=404)
    enrolled = enroll_repo.get_for_student_course(db, user.id, course_id)
    exams = exam_repo.list_by_course(db, course_id) if enrolled else []
    submitted_exam_ids = (
        {
            s.exam_id
            for s in db.query(Submission)
            .filter(Submission.student_id == user.id, Submission.exam_id.in_([e.id for e in exams]))
            .all()
        }
        if exams
        else set()
    )
    return {
        "course": course,
        "enrolled": enrolled,
        "exams": exams,
        "submitted_exam_ids": submitted_exam_ids,
        "now": now,
    }


def enroll_student(db: Session, course_id: int, user: User) -> None:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404)
    if course.department_id != user.department_id:
        raise HTTPException(status_code=403, detail="Course is not in your department")
    from sqlalchemy.exc import IntegrityError

    from ..models import Enrollment

    db.add(Enrollment(student_id=user.id, course_id=course_id))
    try:
        db.commit()
        audit(
            db,
            AuditAction.enrollment_created,
            user_id=user.id,
            target_id=course_id,
            target_type="course",
        )
    except IntegrityError:
        db.rollback()


def unenroll_student(db: Session, course_id: int, user: User) -> None:
    enroll_repo.unenroll_by_student_course(db, user.id, course_id)


def get_submit_form_data(db: Session, exam_id: int, user: User) -> dict:
    from datetime import UTC, datetime

    now = datetime.now(UTC).replace(tzinfo=None)
    exam = exam_repo.get(db, exam_id)
    if not (exam.opens_at <= now <= exam.closes_at):
        raise HTTPException(status_code=400, detail="Submission window is not open")
    if not enroll_repo.get_for_student_course(db, user.id, exam.course_id):
        raise HTTPException(status_code=403, detail="You are not enrolled in this course")
    existing = sub_repo.get_for_student_exam(db, exam_id, user.id)
    return {"exam": exam, "existing": existing}


def get_submission_detail(db: Session, submission_id: int, user: User) -> dict:
    sub = sub_repo.get(db, submission_id)
    if sub.student_id != user.id:
        raise HTTPException(status_code=404)
    pairs = pair_repo.list_by_submission(db, submission_id)
    audit(
        db,
        AuditAction.report_viewed,
        user_id=user.id,
        target_id=submission_id,
        target_type="submission",
    )
    return {"sub": sub, "exam": sub.exam, "pairs": pairs}
