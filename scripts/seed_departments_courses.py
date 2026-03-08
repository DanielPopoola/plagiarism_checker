"""Seed departments and courses via the API.

Each department gets its own set of courses. Shared course codes (e.g. GNS 302)
are created once per department they appear in — they are no longer deduplicated
across departments, since a course now belongs to exactly one department.

Usage:
    python scripts/seed_departments_courses.py \
        --base-url http://localhost:8000 \
        --email admin@test.com \
        --password password123
"""

import argparse
import requests

SHARED_SOCIAL = [
    ("FRN 302", "ADVANCE FRENCH"),
    ("GNS 302", "PROJECT MANAGEMENT"),
    ("GNS 322", "INTERNATIONAL BUSINESS"),
]

CURRICULUM: dict[str, list[tuple[str, str]]] = {
    "INTERNATIONAL RELATIONS": SHARED_SOCIAL + [
        ("POL 331", "THE GREAT CHINESE ECONOMY"),
        ("POL 301", "WORLD POLITICS"),
        ("INR 311", "INTERNATIONAL FINANCE AND POLITICS OF FOREIGN AIDS"),
        ("INR 321", "POPULATION AND MIGRATION STUDIES"),
        ("INR 331", "ELEMENTS OF CONTEMPORARY GLOBAL ISSUES"),
        ("INR 301", "GLOBAL TERRORISM AND POLITICAL VIOLENCE"),
    ],
    "POLITICAL SCIENCE": SHARED_SOCIAL + [
        ("POL 331", "THE GREAT CHINESE ECONOMY"),
        ("POL 301", "WORLD POLITICS"),
        ("INR 311", "INTERNATIONAL FINANCE AND POLITICS OF FOREIGN AIDS"),
        ("INR 321", "POPULATION AND MIGRATION STUDIES"),
        ("INR 331", "ELEMENTS OF CONTEMPORARY GLOBAL ISSUES"),
        ("INR 301", "GLOBAL TERRORISM AND POLITICAL VIOLENCE"),
    ],
    "PUBLIC ADMINISTRATION": SHARED_SOCIAL + [
        ("POL 331", "THE GREAT CHINESE ECONOMY"),
        ("POL 301", "WORLD POLITICS"),
        ("INR 311", "INTERNATIONAL FINANCE AND POLITICS OF FOREIGN AIDS"),
        ("INR 321", "POPULATION AND MIGRATION STUDIES"),
        ("INR 331", "ELEMENTS OF CONTEMPORARY GLOBAL ISSUES"),
        ("INR 301", "GLOBAL TERRORISM AND POLITICAL VIOLENCE"),
    ],
    "BUSINESS ADMINISTRATION": SHARED_SOCIAL + [
        ("BUS 304", "BUSINESS PORT FOLIO MANAGEMENT"),
        ("ECN 312", "MANAGERIAL ECONOMICS"),
        ("BUS 322", "BUSINESS ETHICS AND SOCIAL RESPONSIBILITIES"),
        ("BUS 331", "ANALYSIS OF BUSINESS DECISION"),
        ("BUS 314", "COOPERATE GOVERNANCE"),
        ("HRM 304", "STRATEGIC MANAGEMENT & BUSINESS POLICY"),
    ],
}


def dept_code(name: str) -> str:
    return "".join(p[0] for p in name.split()).upper()[:6]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    args = ap.parse_args()

    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + s.post(
        f"{args.base_url}/auth/token",
        data={"username": args.email, "password": args.password},
    ).json()["access_token"]

    # Pick any lecturer/admin to assign as default course lecturer
    users = s.get(f"{args.base_url}/admin/users").json()
    lecturer_id = next(u["id"] for u in users if u["role"] in ("lecturer", "admin"))

    total_courses = 0

    for dept_name, courses in CURRICULUM.items():
        # Create department
        res = s.post(
            f"{args.base_url}/admin/departments",
            params={"name": dept_name, "code": dept_code(dept_name)},
        )
        res.raise_for_status()
        dept_id = res.json()["id"]

        # Create every course directly under this department
        for code, title in courses:
            res = s.post(
                f"{args.base_url}/courses/",
                json={
                    "code": code,
                    "title": title,
                    "description": "Placeholder created from timetable",
                    "department_id": dept_id,
                    "lecturer_id": lecturer_id,
                },
            )
            res.raise_for_status()
            total_courses += 1

    print(f"Seeded {len(CURRICULUM)} departments and {total_courses} courses")


if __name__ == "__main__":
    main()