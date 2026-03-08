from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..auth import create_token, hash_password, verify_password
from ..models import AuditAction, Department, Role, User
from ..repositories import user as user_repo
from ..services.audit import log as audit


def login(db: Session, email: str, password: str, ip: str | None) -> tuple[User, str]:
    user = user_repo.get_by_email(db, email)
    if not user or not verify_password(password, user.hashed_pw):
        audit(db, AuditAction.login, detail={"email": email, "success": False}, ip_address=ip)
        raise HTTPException(status_code=400, detail="Invalid email or password")
    audit(db, AuditAction.login, user_id=user.id, detail={"success": True}, ip_address=ip)
    return user, create_token(user.id, user.role)


def register(
    db: Session, email: str, name: str, password: str, role: str, department_id: int | None
) -> User:
    if user_repo.get_by_email(db, email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_role = Role(role) if role in Role._value2member_map_ else Role.student
    chosen_dept = db.get(Department, department_id) if department_id else None
    if user_role == Role.student and not chosen_dept:
        raise HTTPException(status_code=400, detail="Students must select a department")
    user = User(
        email=email,
        name=name,
        role=user_role,
        department_id=chosen_dept.id if chosen_dept else None,
        hashed_pw=hash_password(password),
    )
    db.add(user)
    db.commit()
    audit(db, AuditAction.user_created, user_id=user.id, target_id=user.id, target_type="user")
    return user


def redirect_after_login(role: Role) -> str:
    return {Role.student: "/student/dashboard", Role.admin: "/admin/"}.get(role, "/dashboard/")
