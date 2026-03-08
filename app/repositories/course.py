from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import AuditAction, Course, Role, User
from ..services.audit import log as audit


def get(db: Session, course_id: int) -> Course:
    c = db.get(Course, course_id)
    if not c:
        raise HTTPException(status_code=404)
    return c


def list_by_dept(db: Session, department_id: int) -> list[Course]:
    return db.query(Course).filter_by(department_id=department_id).order_by(Course.code).all()


def list_for_user(db: Session, user: User) -> list[Course]:
    if user.role == Role.admin:
        return db.query(Course).order_by(Course.code).all()
    return list_by_dept(db, user.department_id)


def create(
    db: Session,
    title: str,
    code: str,
    department_id: int,
    lecturer_id: int,
    description: str | None,
    actor_id: int,
) -> Course:
    lecturer = db.get(User, lecturer_id)
    if not lecturer or lecturer.role not in (Role.lecturer, Role.admin):
        raise HTTPException(status_code=400, detail="Selected user is not a lecturer")
    course = Course(
        title=title,
        code=code,
        description=description or None,
        department_id=department_id,
        lecturer_id=lecturer_id,
    )
    db.add(course)
    db.commit()
    audit(
        db, AuditAction.course_created, user_id=actor_id, target_id=course.id, target_type="course"
    )
    return course


def assign_lecturer(db: Session, course_id: int, lecturer_id: int) -> Course:
    course = get(db, course_id)
    lecturer = db.get(User, lecturer_id)
    if not lecturer or lecturer.role not in (Role.lecturer, Role.admin):
        raise HTTPException(status_code=400, detail="Selected user is not a lecturer")
    course.lecturer_id = lecturer.id
    db.commit()
    return course


def delete(db: Session, course_id: int) -> int:
    course = get(db, course_id)
    dept_id = course.department_id
    db.delete(course)
    db.commit()
    return dept_id
