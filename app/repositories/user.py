from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import AuditAction, Department, Role, User
from ..services.audit import log as audit


def get(db: Session, user_id: int) -> User:
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404)
    return u


def get_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter_by(email=email).first()


def list_all(db: Session) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


def activate(db: Session, user_id: int, actor_id: int) -> User:
    u = get(db, user_id)
    u.is_active = True
    db.commit()
    audit(db, AuditAction.user_activated, user_id=actor_id, target_id=u.id, target_type="user")
    db.refresh(u)
    return u


def deactivate(db: Session, user_id: int, actor_id: int) -> User:
    u = get(db, user_id)
    if u.id == actor_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    u.is_active = False
    db.commit()
    audit(db, AuditAction.user_deactivated, user_id=actor_id, target_id=u.id, target_type="user")
    db.refresh(u)
    return u


def set_role(db: Session, user_id: int, role: str) -> User:
    u = get(db, user_id)
    try:
        u.role = Role(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}") from None
    db.commit()
    db.refresh(u)
    return u


def set_department(db: Session, user_id: int, department_id: int) -> User:
    u = get(db, user_id)
    dept = db.get(Department, department_id)
    if not dept:
        raise HTTPException(status_code=404)
    u.department_id = dept.id
    db.commit()
    return u
