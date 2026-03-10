from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Department


def get(db: Session, dept_id: int) -> Department:
    d = db.get(Department, dept_id)
    if not d:
        raise HTTPException(status_code=404)
    return d


def list_all(db: Session) -> list[Department]:
    return db.query(Department).order_by(Department.name).all()


def create(db: Session, name: str, code: str) -> Department:
    try:
        with db.begin_nested():  # savepoint — rolls back only to here on failure
            dept = Department(name=name.strip(), code=code.strip().upper())
            db.add(dept)
        db.commit()
    except IntegrityError:
        return (
            db.query(Department)
            .filter((Department.code == code.strip().upper()) | (Department.name == name.strip()))
            .first()
        )
    db.refresh(dept)
    return dept
