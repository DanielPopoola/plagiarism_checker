from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import AuditAction, Course, Enrollment, Role, User
from ..services.audit import log as audit


def list_by_student(db: Session, student_id: int) -> list[Enrollment]:
    return db.query(Enrollment).filter_by(student_id=student_id).all()


def list_by_course(db: Session, course_id: int) -> list[Enrollment]:
    return db.query(Enrollment).filter_by(course_id=course_id).all()


def get_for_student_course(db: Session, student_id: int, course_id: int) -> Enrollment | None:
    return db.query(Enrollment).filter_by(student_id=student_id, course_id=course_id).first()


def enroll(db: Session, student_id: int, course_id: int, actor_id: int) -> Enrollment:
    student = db.get(User, student_id)
    if not student or student.role != Role.student:
        raise HTTPException(status_code=400, detail="User is not a student")
    if not db.get(Course, course_id):
        raise HTTPException(status_code=404, detail="Course not found")
    e = Enrollment(student_id=student_id, course_id=course_id)
    db.add(e)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Already enrolled") from None
    audit(
        db,
        AuditAction.enrollment_created,
        user_id=actor_id,
        target_id=course_id,
        target_type="course",
    )
    db.refresh(e)
    return e


def unenroll(db: Session, enrollment_id: int) -> int:
    e = db.get(Enrollment, enrollment_id)
    if not e:
        raise HTTPException(status_code=404)
    course_id = e.course_id
    db.delete(e)
    db.commit()
    return course_id


def unenroll_by_student_course(db: Session, student_id: int, course_id: int) -> None:
    e = get_for_student_course(db, student_id, course_id)
    if e:
        db.delete(e)
        db.commit()
