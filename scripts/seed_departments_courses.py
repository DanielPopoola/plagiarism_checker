"""Seed an initial admin, departments, and courses directly in the database.

This script is idempotent and safe to run repeatedly. Existing rows are reused.

Environment variables:
    SEED_ADMIN_EMAIL     (default: admin@example.com)
    SEED_ADMIN_PASSWORD  (default: admin123)
    SEED_ADMIN_NAME      (default: System Admin)
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import Course, Department, Role, User

SHARED_SOCIAL = [
    ("FRN 302", "ADVANCE FRENCH"),
    ("GNS 302", "PROJECT MANAGEMENT"),
    ("GNS 322", "INTERNATIONAL BUSINESS"),
]

CURRICULUM: dict[str, list[tuple[str, str]]] = {
    "INTERNATIONAL RELATIONS": SHARED_SOCIAL
    + [
        ("POL 331", "THE GREAT CHINESE ECONOMY"),
        ("POL 301", "WORLD POLITICS"),
        ("INR 311", "INTERNATIONAL FINANCE AND POLITICS OF FOREIGN AIDS"),
        ("INR 321", "POPULATION AND MIGRATION STUDIES"),
        ("INR 331", "ELEMENTS OF CONTEMPORARY GLOBAL ISSUES"),
        ("INR 301", "GLOBAL TERRORISM AND POLITICAL VIOLENCE"),
    ],
    "POLITICAL SCIENCE": SHARED_SOCIAL
    + [
        ("POL 331", "THE GREAT CHINESE ECONOMY"),
        ("POL 301", "WORLD POLITICS"),
        ("INR 311", "INTERNATIONAL FINANCE AND POLITICS OF FOREIGN AIDS"),
        ("INR 321", "POPULATION AND MIGRATION STUDIES"),
        ("INR 331", "ELEMENTS OF CONTEMPORARY GLOBAL ISSUES"),
        ("INR 301", "GLOBAL TERRORISM AND POLITICAL VIOLENCE"),
    ],
    "PUBLIC ADMINISTRATION": SHARED_SOCIAL
    + [
        ("POL 331", "THE GREAT CHINESE ECONOMY"),
        ("POL 301", "WORLD POLITICS"),
        ("INR 311", "INTERNATIONAL FINANCE AND POLITICS OF FOREIGN AIDS"),
        ("INR 321", "POPULATION AND MIGRATION STUDIES"),
        ("INR 331", "ELEMENTS OF CONTEMPORARY GLOBAL ISSUES"),
        ("INR 301", "GLOBAL TERRORISM AND POLITICAL VIOLENCE"),
    ],
    "BUSINESS ADMINISTRATION": SHARED_SOCIAL
    + [
        ("BUS 304", "BUSINESS PORT FOLIO MANAGEMENT"),
        ("ECN 312", "MANAGERIAL ECONOMICS"),
        ("BUS 322", "BUSINESS ETHICS AND SOCIAL RESPONSIBILITIES"),
        ("BUS 331", "ANALYSIS OF BUSINESS DECISION"),
        ("BUS 314", "COOPERATE GOVERNANCE"),
        ("HRM 304", "STRATEGIC MANAGEMENT & BUSINESS POLICY"),
    ],
}


def dept_code(name: str) -> str:
    return "".join(part[0] for part in name.split()).upper()[:6]


def get_or_create_admin(db) -> User:
    admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com")
    admin_password = os.getenv("SEED_ADMIN_PASSWORD", "admin123")
    admin_name = os.getenv("SEED_ADMIN_NAME", "System Admin")

    admin = db.query(User).filter(User.email == admin_email).first()
    if admin:
        return admin

    admin = User(
        email=admin_email,
        name=admin_name,
        role=Role.admin,
        hashed_pw=hash_password(admin_password),
        department_id=None,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def get_or_create_department(db, name: str) -> Department:
    code = dept_code(name)
    department = db.query(Department).filter(Department.name == name).first()
    if department:
        return department

    department = Department(name=name, code=code)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def create_missing_courses(db, department_id: int, lecturer_id: int, courses: list[tuple[str, str]]) -> int:
    created = 0
    for code, title in courses:
        existing = (
            db.query(Course)
            .filter(Course.department_id == department_id, Course.code == code)
            .first()
        )
        if existing:
            continue
        db.add(
            Course(
                code=code,
                title=title,
                description="Placeholder created from timetable",
                department_id=department_id,
                lecturer_id=lecturer_id,
            )
        )
        created += 1

    if created:
        db.commit()
    return created


def main() -> None:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        admin = get_or_create_admin(db)
        admin_email = admin.email

        departments_created = 0
        courses_created = 0

        for dept_name, courses in CURRICULUM.items():
            before = db.query(Department).filter(Department.name == dept_name).first()
            department = get_or_create_department(db, dept_name)
            if before is None:
                departments_created += 1
            courses_created += create_missing_courses(db, department.id, admin.id, courses)

    print(
        "Seed complete: "
        f"admin={admin_email}, "
        f"departments_created={departments_created}, "
        f"courses_created={courses_created}"
    )


if __name__ == "__main__":
    main()
