"""Create 300-level placeholder departments/courses via API.

Usage:
python scripts/seed_departments_courses.py --base-url http://localhost:8000 --email admin@test.com --password password123
"""

import argparse
from collections import defaultdict

import requests

SHARED_SOCIAL = [
    ("FRN 302", "ADVANCE FRENCH"),
    ("GNS 302", "PROJECT MANAGEMENT"),
    ("GNS 322", "INTERNATIONAL BUSINESS"),
]

CURRICULUM = {
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


def code_for_department(name: str) -> str:
    return "".join(p[0] for p in name.split()).upper()[:6]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    args = ap.parse_args()

    s = requests.Session()
    token = s.post(
        f"{args.base_url}/auth/token",
        data={"username": args.email, "password": args.password},
    ).json()["access_token"]
    s.headers.update({"Authorization": f"Bearer {token}"})

    users = s.get(f"{args.base_url}/admin/users").json()
    lecturer_id = next(u["id"] for u in users if u["role"] in ("lecturer", "admin"))

    departments = {}
    for department in CURRICULUM:
        payload = {"name": department, "code": code_for_department(department)}
        res = s.post(f"{args.base_url}/admin/departments", params=payload)
        res.raise_for_status()
        departments[department] = res.json()["id"]

    course_departments = defaultdict(set)
    course_titles = {}
    for department, courses in CURRICULUM.items():
        for code, title in courses:
            course_departments[code].add(departments[department])
            course_titles[code] = title

    existing = {c["code"]: c for c in s.get(f"{args.base_url}/courses/").json()}
    for code, department_ids in course_departments.items():
        payload = {
            "code": code,
            "title": course_titles[code],
            "description": "Placeholder created from PDF timetable",
            "lecturer_id": lecturer_id,
            "department_ids": sorted(department_ids),
        }
        if code in existing:
            s.put(f"{args.base_url}/courses/{existing[code]['id']}", json=payload).raise_for_status()
        else:
            s.post(f"{args.base_url}/courses/", json=payload).raise_for_status()

    print(f"Seeded {len(departments)} departments and {len(course_departments)} courses")


if __name__ == "__main__":
    main()
