from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import admin_only, lecturer_or_admin
from ..database import get_db
from ..models import Department, Role, User
from ..repositories import course as course_repo
from ..schemas import CourseCreate, CourseOut

router = APIRouter(prefix="/courses", tags=["courses"])


@router.post("/", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(
    body: CourseCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
):
    if not db.get(Department, body.department_id):
        raise HTTPException(status_code=404, detail="Department not found")
    return course_repo.create(
        db,
        title=body.title,
        code=body.code,
        department_id=body.department_id,
        lecturer_id=body.lecturer_id,
        description=body.description,
        actor_id=user.id,
    )


@router.get("/", response_model=list[CourseOut])
def list_courses(
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(lecturer_or_admin)]
):
    return course_repo.list_for_user(db, user)


@router.get("/{course_id}", response_model=CourseOut)
def get_course(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    course = course_repo.get(db, course_id)
    if user.role == Role.lecturer and course.department_id != user.department_id:
        raise HTTPException(status_code=403, detail="Not your department")
    return course


@router.put("/{course_id}", response_model=CourseOut)
def update_course(
    course_id: int,
    body: CourseCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
):
    course = course_repo.get(db, course_id)
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
    course_repo.delete(db, course_id)
