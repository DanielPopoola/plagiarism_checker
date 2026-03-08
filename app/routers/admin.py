from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..auth import admin_only
from ..database import get_db
from ..models import Role, User
from ..repositories import course as course_repo
from ..repositories import department as dept_repo
from ..repositories import user as user_repo
from ..schemas import DepartmentOut, UserOut
from ..services import admin as admin_svc
from ..templates import templates

router = APIRouter(prefix="/admin", tags=["admin"])


# ── JSON API ──────────────────────────────────────────────────────────────────


@router.get("/users", response_model=list[UserOut])
def list_users(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(admin_only)]):
    return user_repo.list_all(db)


@router.patch("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(admin_only)],
):
    return admin_svc.toggle_user(db, user_id, activate=False, actor_id=admin.id)


@router.patch("/users/{user_id}/activate", response_model=UserOut)
def activate_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(admin_only)],
):
    return admin_svc.toggle_user(db, user_id, activate=True, actor_id=admin.id)


@router.patch("/users/{user_id}/role", response_model=UserOut)
def change_role(
    user_id: int,
    role: str,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(admin_only)],
):
    return admin_svc.set_role(db, user_id, role)


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(admin_only)]
):
    return dept_repo.list_all(db)


@router.post("/departments")
def create_department_api(
    name: str,
    code: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
):
    return admin_svc.create_department(db, name, code)


@router.post("/enrollments")
def enroll_student(
    student_id: int,
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(admin_only)],
):
    return admin_svc.enroll_student(db, student_id, course_id, admin.id)


@router.delete("/enrollments/{enrollment_id}", status_code=204)
def unenroll_student(
    enrollment_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(admin_only)],
):
    admin_svc.unenroll_student(db, enrollment_id)


# ── HTML Pages ────────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
def admin_index(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
):
    stats = admin_svc.get_dashboard_stats(db)
    return templates.TemplateResponse(
        "admin/index.html", {"request": request, "user": user, **stats}
    )


@router.get("/users-list", response_class=HTMLResponse)
def admin_users(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
):
    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "user": user,
            "users": user_repo.list_all(db),
            "departments": dept_repo.list_all(db),
        },
    )


@router.get("/departments-list", response_class=HTMLResponse)
def admin_departments(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
):
    return templates.TemplateResponse(
        "admin/departments.html",
        {
            "request": request,
            "user": user,
            "departments": dept_repo.list_all(db),
        },
    )


@router.get("/departments-list/{dept_id}", response_class=HTMLResponse)
def admin_department_detail(
    dept_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
):
    dept = dept_repo.get(db, dept_id)
    lecturers = (
        db.query(User).filter(User.role.in_([Role.lecturer, Role.admin])).order_by(User.name).all()
    )
    return templates.TemplateResponse(
        "admin/department.html",
        {
            "request": request,
            "user": user,
            "dept": dept,
            "courses": course_repo.list_by_dept(db, dept_id),
            "lecturers": lecturers,
        },
    )


@router.get("/courses-list/{course_id}", response_class=HTMLResponse)
def admin_course_detail(
    course_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
):
    course = course_repo.get(db, course_id)
    lecturers = (
        db.query(User).filter(User.role.in_([Role.lecturer, Role.admin])).order_by(User.name).all()
    )
    students = db.query(User).filter_by(role=Role.student).order_by(User.name).all()
    enrolled_ids = {e.student_id for e in course.enrollments}
    return templates.TemplateResponse(
        "admin/course.html",
        {
            "request": request,
            "user": user,
            "course": course,
            "lecturers": lecturers,
            "students": students,
            "enrolled_ids": enrolled_ids,
        },
    )


# ── HTML Form POSTs ───────────────────────────────────────────────────────────


@router.post("/departments/new", response_class=HTMLResponse)
async def create_department(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
    name: str = Form(...),
    code: str = Form(...),
):
    admin_svc.create_department(db, name, code)
    return RedirectResponse(url="/admin/departments-list", status_code=303)


@router.post("/courses/new", response_class=HTMLResponse)
async def create_course(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
    title: str = Form(...),
    code: str = Form(...),
    description: str = Form(""),
    lecturer_id: int = Form(...),
    dept_id: int = Form(...),
):
    admin_svc.create_course(db, title, code, description, lecturer_id, dept_id, user.id)
    return RedirectResponse(url=f"/admin/departments-list/{dept_id}", status_code=303)


@router.post("/courses/{course_id}/lecturer", response_class=HTMLResponse)
async def assign_course_lecturer(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
    lecturer_id: int = Form(...),
):
    admin_svc.assign_lecturer(db, course_id, lecturer_id)
    return RedirectResponse(url=f"/admin/courses-list/{course_id}", status_code=303)


@router.post("/courses/{course_id}/delete", response_class=HTMLResponse)
async def delete_course(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
):
    dept_id = admin_svc.delete_course(db, course_id)
    return RedirectResponse(url=f"/admin/departments-list/{dept_id}", status_code=303)


@router.post("/enrollments/new", response_class=HTMLResponse)
async def enroll_student_form(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
    student_id: int = Form(...),
    course_id: int = Form(...),
):
    admin_svc.enroll_student(db, student_id, course_id, user.id)
    return RedirectResponse(url=f"/admin/courses-list/{course_id}", status_code=303)


@router.post("/enrollments/{enrollment_id}/delete", response_class=HTMLResponse)
async def unenroll_student_form(
    enrollment_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
):
    course_id = admin_svc.unenroll_student(db, enrollment_id)
    return RedirectResponse(url=f"/admin/courses-list/{course_id}", status_code=303)


@router.post("/users/{user_id}/department", response_class=HTMLResponse)
async def assign_user_department(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(admin_only)],
    department_id: int = Form(...),
):
    admin_svc.assign_department(db, user_id, department_id)
    return RedirectResponse(url="/admin/users-list", status_code=303)
