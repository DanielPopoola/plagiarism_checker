from sqlalchemy.orm import Session

from ..models import AuditLog, Course, Department, Enrollment, User
from ..repositories import course as course_repo
from ..repositories import department as dept_repo
from ..repositories import enrollment as enroll_repo
from ..repositories import user as user_repo


def get_dashboard_stats(db: Session) -> dict:
    return {
        "total_users": db.query(User).count(),
        "total_courses": db.query(Course).count(),
        "total_departments": db.query(Department).count(),
        "total_enrollments": db.query(Enrollment).count(),
        "logs": db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(20).all(),
    }


def create_department(db: Session, name: str, code: str) -> Department:
    return dept_repo.create(db, name, code)


def create_course(
    db: Session,
    title: str,
    code: str,
    description: str,
    lecturer_id: int,
    dept_id: int,
    actor_id: int,
) -> Course:
    return course_repo.create(
        db,
        title=title,
        code=code,
        department_id=dept_id,
        lecturer_id=lecturer_id,
        description=description,
        actor_id=actor_id,
    )


def assign_lecturer(db: Session, course_id: int, lecturer_id: int) -> Course:
    return course_repo.assign_lecturer(db, course_id, lecturer_id)


def delete_course(db: Session, course_id: int) -> int:
    return course_repo.delete(db, course_id)


def toggle_user(db: Session, user_id: int, activate: bool, actor_id: int) -> User:
    return (
        user_repo.activate(db, user_id, actor_id)
        if activate
        else user_repo.deactivate(db, user_id, actor_id)
    )


def set_role(db: Session, user_id: int, role: str) -> User:
    return user_repo.set_role(db, user_id, role)


def assign_department(db: Session, user_id: int, department_id: int) -> User:
    return user_repo.set_department(db, user_id, department_id)


def enroll_student(db: Session, student_id: int, course_id: int, actor_id: int) -> Enrollment:
    return enroll_repo.enroll(db, student_id, course_id, actor_id)


def unenroll_student(db: Session, enrollment_id: int) -> int:
    return enroll_repo.unenroll(db, enrollment_id)
