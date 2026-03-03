"""
tests/test_auth.py

Tests for: app/auth.py, /auth/token, /auth/register endpoints
Covers: token creation, password hashing, JWT decode, role guards,
        inactive users, missing tokens, wrong roles.
"""

import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.auth import (
    create_token, hash_password, verify_password,
    _decode_token,
)
from app.config import settings
from app.models import Role

from conftest import auth


# ---------------------------------------------------------------------------
# Unit: password hashing
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        assert hash_password("secret") != "secret"

    def test_correct_password_verifies(self):
        h = hash_password("correct")
        assert verify_password("correct", h) is True

    def test_wrong_password_fails(self):
        h = hash_password("correct")
        assert verify_password("wrong", h) is False

    def test_same_password_produces_different_hashes(self):
        # bcrypt salts — two hashes of the same password must differ
        assert hash_password("pw") != hash_password("pw")


# ---------------------------------------------------------------------------
# Unit: JWT creation and decoding
# ---------------------------------------------------------------------------

class TestJWT:
    def test_token_contains_user_id_and_role(self, student):
        token = create_token(student.id, student.role)
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        assert payload["sub"] == str(student.id)
        assert payload["role"] == Role.student

    def test_token_expires_in_configured_window(self, student):
        token = create_token(student.id, student.role)
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
        assert abs((exp - expected).total_seconds()) < 5

    def test_decode_returns_correct_user(self, db, student):
        token = create_token(student.id, student.role)
        user = _decode_token(token, db)
        assert user.id == student.id

    def test_decode_raises_on_tampered_token(self, db, student):
        from fastapi import HTTPException
        token = create_token(student.id, student.role) + "garbage"
        with pytest.raises(HTTPException) as exc:
            _decode_token(token, db)
        assert exc.value.status_code == 401

    def test_decode_raises_on_inactive_user(self, db, inactive):
        from fastapi import HTTPException
        token = create_token(inactive.id, inactive.role)
        with pytest.raises(HTTPException) as exc:
            _decode_token(token, db)
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# API: POST /auth/token  (OAuth2 form login)
# ---------------------------------------------------------------------------

class TestTokenEndpoint:
    def test_valid_credentials_return_token(self, client, lecturer):
        r = client.post("/auth/token",
                        data={"username": "lecturer@test.com", "password": "password123"})
        assert r.status_code == 200
        assert "access_token" in r.json()
        assert r.json()["token_type"] == "bearer"

    def test_wrong_password_returns_401(self, client, lecturer):
        r = client.post("/auth/token",
                        data={"username": "lecturer@test.com", "password": "wrong"})
        assert r.status_code == 401

    def test_unknown_email_returns_401(self, client):
        r = client.post("/auth/token",
                        data={"username": "nobody@test.com", "password": "password123"})
        assert r.status_code == 401

    def test_returned_token_is_valid_jwt(self, client, lecturer):
        r = client.post("/auth/token",
                        data={"username": "lecturer@test.com", "password": "password123"})
        token = r.json()["access_token"]
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        assert payload["sub"] == str(lecturer.id)


# ---------------------------------------------------------------------------
# API: POST /auth/register
# ---------------------------------------------------------------------------

class TestRegisterEndpoint:
    def test_new_user_created(self, client):
        r = client.post("/auth/register",
                        json={"email": "new@test.com", "name": "New",
                              "password": "pass1234", "role": "student"})
        assert r.status_code == 201
        assert r.json()["email"] == "new@test.com"

    def test_duplicate_email_returns_400(self, client, student):
        r = client.post("/auth/register",
                        json={"email": "student@test.com", "name": "Dup",
                              "password": "pass1234", "role": "student"})
        assert r.status_code == 400

    def test_password_is_stored_hashed(self, client, db):
        client.post("/auth/register",
                    json={"email": "hashed@test.com", "name": "H",
                          "password": "plaintext", "role": "student"})
        from app.models import User
        user = db.query(User).filter_by(email="hashed@test.com").first()
        assert user.hashed_pw != "plaintext"


# ---------------------------------------------------------------------------
# Role guards: require_role / lecturer_or_admin / admin_only
# ---------------------------------------------------------------------------

class TestRoleGuards:
    def test_student_cannot_create_exam(self, client, student, course):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        r = client.post("/exams/", json={
            "course_id": course.id, "title": "Test",
            "opens_at": (now + timedelta(hours=1)).isoformat(),
            "closes_at": (now + timedelta(hours=25)).isoformat(),
        }, headers=auth(student))
        assert r.status_code == 403

    def test_student_cannot_list_submissions(self, client, student, open_exam):
        r = client.get(f"/submissions/{open_exam.id}", headers=auth(student))
        assert r.status_code == 403

    def test_student_cannot_access_reports(self, client, student, open_exam):
        r = client.get(f"/reports/{open_exam.id}/pairs", headers=auth(student))
        assert r.status_code == 403

    def test_student_cannot_access_admin(self, client, student):
        r = client.get("/admin/users", headers=auth(student))
        assert r.status_code == 403

    def test_lecturer_cannot_access_admin(self, client, lecturer):
        r = client.get("/admin/users", headers=auth(lecturer))
        assert r.status_code == 403

    def test_unauthenticated_request_returns_401(self, client, open_exam):
        r = client.get(f"/reports/{open_exam.id}/pairs")
        assert r.status_code == 401

    def test_lecturer_blocked_from_other_lecturers_exam(self, client, other_lecturer, open_exam):
        # open_exam belongs to `lecturer`, not `other_lecturer`
        r = client.get(f"/reports/{open_exam.id}/pairs", headers=auth(other_lecturer))
        assert r.status_code == 403

    def test_admin_can_access_all_users(self, client, admin, student, lecturer):
        r = client.get("/admin/users", headers=auth(admin))
        assert r.status_code == 200
        emails = [u["email"] for u in r.json()]
        assert "student@test.com" in emails
        assert "lecturer@test.com" in emails