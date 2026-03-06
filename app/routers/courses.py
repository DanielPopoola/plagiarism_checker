from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import admin_only, lecturer_or_admin
from ..database import get_db
from ..models import AuditAction, Course, Department, Role, User
from ..schemas import CourseCreate, CourseOut
from ..services.audit import log as audit

router = APIRouter(prefix="/courses", tags=["courses"])


def _assert_course_access(course: Course, user: User) -> None:
    if user.role == Role.admin:
        return
    if course.department_id != user.department_id:
        raise HTTPException(status_code=403, detail="Not your department")


@router.post("/", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(
    body: CourseCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
):
    if not db.get(Department, body.department_id):
        raise HTTPException(status_code=404, detail="Department not found")
    course = Course(**body.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    audit(db, AuditAction.course_created, user_id=user.id, target_id=course.id, target_type="course")
    return course


@router.get("/", response_model=list[CourseOut])
def list_courses(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    if user.role == Role.admin:
        return db.query(Course).all()
    return db.query(Course).filter_by(department_id=user.department_id).all()


@router.get("/{course_id}", response_model=CourseOut)
def get_course(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    _assert_course_access(course, user)
    return course


@router.put("/{course_id}", response_model=CourseOut)
def update_course(
    course_id: int,
    body: CourseCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    for k, v in body.model_dump().items():
        setattr(course, k, v)
    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)
    db.commit()