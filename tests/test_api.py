"""
tests/test_api.py — API-level tests using FastAPI TestClient + real SQLite.

Patches:
  - app.tasks.analysis.run_plagiarism_analysis  (Celery task, imported inside handler)
  - app.routers.submissions.extract_text        (avoids real file I/O)
  - app.routers.submissions._save_file          (avoids disk writes for non-upload tests)
"""

import io
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.models import AuditAction, AuditLog, JobStatus, PlagiarismJob, ReviewStatus, Submission
from conftest import auth, txt_upload, oversized_upload, _user, make_user


def _now():
    return datetime.now(timezone.utc)


# Patch targets — task is imported inside the function body, so patch at source
TASK_PATH    = "app.tasks.analysis.run_plagiarism_analysis"
EXTRACT_PATH = "app.routers.submissions.extract_text"
SAVE_PATH    = "app.routers.submissions._save_file"


def _mock_task():
    m = MagicMock()
    m.delay.return_value.id = "celery-test-id"
    return m


# ---------------------------------------------------------------------------
# Exams — CRUD
# ---------------------------------------------------------------------------

class TestExamCRUD:
    def _payload(self, course_id):
        return {
            "course_id": course_id,
            "title": "Final Essay",
            "opens_at": (_now() + timedelta(hours=1)).isoformat(),
            "closes_at": (_now() + timedelta(hours=25)).isoformat(),
            "allowed_formats": "pdf,docx,txt",
            "max_file_mb": 10,
            "similarity_threshold": 0.4,
        }

    def test_lecturer_creates_exam(self, client, lecturer, course):
        r = client.post("/exams/", json=self._payload(course.id), headers=auth(lecturer))
        assert r.status_code == 201
        assert r.json()["title"] == "Final Essay"

    def test_create_exam_wrong_course_returns_403(self, client, other_lecturer, course):
        r = client.post("/exams/", json=self._payload(course.id), headers=auth(other_lecturer))
        assert r.status_code == 403

    def test_closes_at_before_opens_at_returns_422(self, client, lecturer, course):
        payload = self._payload(course.id)
        payload["closes_at"] = (_now() - timedelta(hours=1)).isoformat()
        r = client.post("/exams/", json=payload, headers=auth(lecturer))
        assert r.status_code == 422

    def test_lecturer_lists_only_own_exams(self, client, other_lecturer, open_exam):
        r = client.get("/exams/", headers=auth(other_lecturer))
        ids = [e["id"] for e in r.json()]
        assert open_exam.id not in ids

    def test_lecturer_gets_own_exam(self, client, lecturer, open_exam):
        r = client.get(f"/exams/{open_exam.id}", headers=auth(lecturer))
        assert r.status_code == 200
        assert r.json()["id"] == open_exam.id

    def test_lecturer_blocked_from_other_exam(self, client, other_lecturer, open_exam):
        r = client.get(f"/exams/{open_exam.id}", headers=auth(other_lecturer))
        assert r.status_code == 403

    def test_nonexistent_exam_returns_404(self, client, lecturer):
        r = client.get("/exams/999999", headers=auth(lecturer))
        assert r.status_code == 404

    def test_student_sees_only_open_exams(self, client, student, open_exam, closed_exam, future_exam):
        r = client.get("/exams/", headers=auth(student))
        ids = [e["id"] for e in r.json()]
        assert open_exam.id in ids
        assert closed_exam.id not in ids
        assert future_exam.id not in ids


# ---------------------------------------------------------------------------
# Submissions — upload
# ---------------------------------------------------------------------------

class TestSubmissionUpload:
    def test_student_uploads_valid_txt(self, client, student, open_exam):
        with patch(TASK_PATH, _mock_task()), \
             patch(SAVE_PATH, return_value="uploads/1/essay.txt"), \
             patch(EXTRACT_PATH, return_value="extracted text content"):
            r = client.post(f"/submissions/{open_exam.id}",
                            files=[txt_upload()], headers=auth(student))
        assert r.status_code == 201
        assert r.json()["exam_id"] == open_exam.id
        assert r.json()["student_id"] == student.id

    def test_submission_stores_extracted_text(self, client, db, student, open_exam):
        extracted = "the mitochondria is the powerhouse of the cell"
        with patch(TASK_PATH, _mock_task()), \
             patch(SAVE_PATH, return_value="uploads/1/essay.txt"), \
             patch(EXTRACT_PATH, return_value=extracted):
            client.post(f"/submissions/{open_exam.id}",
                        files=[txt_upload()], headers=auth(student))
        sub = db.query(Submission).filter_by(exam_id=open_exam.id, student_id=student.id).first()
        assert sub is not None
        assert sub.extracted_text == extracted

    def test_submission_triggers_analysis_job(self, client, student, open_exam):
        mock_task = _mock_task()
        with patch(TASK_PATH, mock_task), \
             patch(SAVE_PATH, return_value="uploads/1/essay.txt"), \
             patch(EXTRACT_PATH, return_value="content"):
            client.post(f"/submissions/{open_exam.id}",
                        files=[txt_upload()], headers=auth(student))
        mock_task.delay.assert_called_once_with(open_exam.id)

    def test_lecturer_cannot_submit(self, client, lecturer, open_exam):
        r = client.post(f"/submissions/{open_exam.id}",
                        files=[txt_upload()], headers=auth(lecturer))
        assert r.status_code == 403

    def test_submission_rejected_outside_window_closed(self, client, student, closed_exam):
        r = client.post(f"/submissions/{closed_exam.id}",
                        files=[txt_upload()], headers=auth(student))
        assert r.status_code == 400

    def test_submission_rejected_outside_window_future(self, client, student, future_exam):
        r = client.post(f"/submissions/{future_exam.id}",
                        files=[txt_upload()], headers=auth(student))
        assert r.status_code == 400

    def test_disallowed_file_format_rejected(self, client, student, open_exam):
        # open_exam allows pdf,docx,txt — csv must be rejected by _save_file
        r = client.post(
            f"/submissions/{open_exam.id}",
            files=[("file", ("essay.csv", io.BytesIO(b"col1,col2"), "text/csv"))],
            headers=auth(student),
        )
        assert r.status_code == 400

    def test_oversized_file_rejected(self, client, student, open_exam):
        r = client.post(
            f"/submissions/{open_exam.id}",
            files=[oversized_upload(mb=15)],
            headers=auth(student),
        )
        assert r.status_code == 413

    def test_nonexistent_exam_returns_404(self, client, student):
        r = client.post("/submissions/999999",
                        files=[txt_upload()], headers=auth(student))
        assert r.status_code == 404

    def test_upserts_job_on_resubmission(self, client, db, student, open_exam):
        with patch(TASK_PATH, _mock_task()), \
             patch(SAVE_PATH, return_value="uploads/1/a.txt"), \
             patch(EXTRACT_PATH, return_value="first content"):
            client.post(f"/submissions/{open_exam.id}",
                        files=[txt_upload("first " * 20)], headers=auth(student))
        with patch(TASK_PATH, _mock_task()), \
             patch(SAVE_PATH, return_value="uploads/1/b.txt"), \
             patch(EXTRACT_PATH, return_value="second content"):
            client.post(f"/submissions/{open_exam.id}",
                        files=[txt_upload("second " * 20)], headers=auth(student))
        jobs = db.query(PlagiarismJob).filter_by(exam_id=open_exam.id).all()
        assert len(jobs) == 1
        assert jobs[0].status == JobStatus.pending


# ---------------------------------------------------------------------------
# Submissions — list & job status
# ---------------------------------------------------------------------------

class TestSubmissionRead:
    def test_lecturer_lists_submissions(self, client, lecturer, open_exam, submission):
        r = client.get(f"/submissions/{open_exam.id}", headers=auth(lecturer))
        assert r.status_code == 200
        assert any(s["id"] == submission.id for s in r.json())

    def test_lecturer_blocked_from_other_exam_submissions(self, client, other_lecturer, open_exam):
        r = client.get(f"/submissions/{open_exam.id}", headers=auth(other_lecturer))
        assert r.status_code == 403

    def test_job_status_returned(self, client, db, lecturer, open_exam):
        job = PlagiarismJob(exam_id=open_exam.id, status=JobStatus.completed)
        db.add(job)
        db.commit()
        r = client.get(f"/submissions/{open_exam.id}/job", headers=auth(lecturer))
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_no_job_returns_404(self, client, lecturer, open_exam):
        r = client.get(f"/submissions/{open_exam.id}/job", headers=auth(lecturer))
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Reports — pairs & review
# ---------------------------------------------------------------------------

class TestReports:
    def _seed_pair(self, db, sub_a, sub_b, score=0.85):
        from app.models import SimilarityPair
        p = SimilarityPair(submission_a_id=sub_a.id, submission_b_id=sub_b.id,
                           similarity_score=score, jaccard_score=0.7,
                           originality_score=round(1 - score, 2))
        db.add(p)
        db.commit()
        db.refresh(p)
        return p

    def _extra_sub(self, db, exam, email):
        from app.models import Role
        u = make_user(db, email, "Extra", Role.student)
        s = Submission(exam_id=exam.id, student_id=u.id,
                       file_path="u/x.txt", extracted_text="content " * 20)
        db.add(s)
        db.commit()
        db.refresh(s)
        return s

    def test_lecturer_gets_pairs(self, client, db, lecturer, open_exam, submission):
        s2 = self._extra_sub(db, open_exam, "p2@test.com")
        pair = self._seed_pair(db, submission, s2)
        r = client.get(f"/reports/{open_exam.id}/pairs", headers=auth(lecturer))
        assert r.status_code == 200
        assert any(p["id"] == pair.id for p in r.json())

    def test_pairs_sorted_by_similarity_desc(self, client, db, lecturer, open_exam, submission):
        from app.models import SimilarityPair, Role
        subs = [self._extra_sub(db, open_exam, f"sort{i}@test.com") for i in range(3)]
        for sub, score in zip(subs, [0.9, 0.5, 0.3]):
            db.add(SimilarityPair(submission_a_id=submission.id, submission_b_id=sub.id,
                                  similarity_score=score, jaccard_score=0.0,
                                  originality_score=1 - score))
        db.commit()
        r = client.get(f"/reports/{open_exam.id}/pairs", headers=auth(lecturer))
        scores = [p["similarity_score"] for p in r.json()]
        assert scores == sorted(scores, reverse=True)

    def test_min_score_filter_applied(self, client, db, lecturer, open_exam, submission):
        s2 = self._extra_sub(db, open_exam, "low@test.com")
        self._seed_pair(db, submission, s2, score=0.1)
        r = client.get(f"/reports/{open_exam.id}/pairs?min_score=0.5", headers=auth(lecturer))
        assert all(p["similarity_score"] >= 0.5 for p in r.json())

    def test_other_lecturer_blocked_from_reports(self, client, other_lecturer, open_exam):
        r = client.get(f"/reports/{open_exam.id}/pairs", headers=auth(other_lecturer))
        assert r.status_code == 403

    @pytest.mark.parametrize("status", ["reviewed", "suspected", "cleared"])
    def test_review_decision_persists(self, client, db, lecturer, open_exam, submission, status):
        s2 = self._extra_sub(db, open_exam, f"rev_{status}@test.com")
        pair = self._seed_pair(db, submission, s2)
        r = client.post(f"/reports/pairs/{pair.id}/review",
                        json={"status": status, "notes": "test note"},
                        headers=auth(lecturer))
        assert r.status_code == 200
        assert r.json()["status"] == status

    def test_review_access_logged(self, client, db, lecturer, open_exam):
        client.get(f"/reports/{open_exam.id}/pairs", headers=auth(lecturer))
        log = db.query(AuditLog).filter_by(
            action=AuditAction.report_viewed, target_id=open_exam.id
        ).first()
        assert log is not None
        assert log.user_id == lecturer.id


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

class TestAuthEndpoints:
    def test_valid_login_returns_token(self, client, lecturer):
        r = client.post("/auth/token",
                        data={"username": "lecturer@test.com", "password": "password123"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_wrong_password_returns_401(self, client, lecturer):
        r = client.post("/auth/token",
                        data={"username": "lecturer@test.com", "password": "wrong"})
        assert r.status_code == 401

    def test_register_new_user(self, client):
        r = client.post("/auth/register",
                        json={"email": "new@test.com", "name": "New",
                              "password": "pass1234", "role": "student"})
        assert r.status_code == 201

    def test_duplicate_email_returns_400(self, client, student):
        r = client.post("/auth/register",
                        json={"email": "student@test.com", "name": "Dup",
                              "password": "pass1234", "role": "student"})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Role guards
# ---------------------------------------------------------------------------

class TestRoleGuards:
    def test_student_cannot_create_exam(self, client, student, course):
        r = client.post("/exams/", json={
            "course_id": course.id, "title": "T",
            "opens_at": (_now() + timedelta(hours=1)).isoformat(),
            "closes_at": (_now() + timedelta(hours=25)).isoformat(),
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

    def test_unauthenticated_returns_401(self, client, open_exam):
        r = client.get(f"/reports/{open_exam.id}/pairs")
        assert r.status_code == 401

    def test_lecturer_blocked_from_other_exam_reports(self, client, other_lecturer, open_exam):
        r = client.get(f"/reports/{open_exam.id}/pairs", headers=auth(other_lecturer))
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

class TestAdmin:
    def test_admin_lists_all_users(self, client, admin, student, lecturer):
        r = client.get("/admin/users", headers=auth(admin))
        assert r.status_code == 200
        emails = [u["email"] for u in r.json()]
        assert "student@test.com" in emails

    def test_admin_deactivates_user(self, client, db, admin, student):
        r = client.patch(f"/admin/users/{student.id}/deactivate", headers=auth(admin))
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    def test_admin_cannot_deactivate_self(self, client, admin):
        r = client.patch(f"/admin/users/{admin.id}/deactivate", headers=auth(admin))
        assert r.status_code == 400

    def test_admin_activates_user(self, client, admin, inactive):
        r = client.patch(f"/admin/users/{inactive.id}/activate", headers=auth(admin))
        assert r.status_code == 200
        assert r.json()["is_active"] is True

    def test_admin_changes_role(self, client, admin, student):
        r = client.patch(f"/admin/users/{student.id}/role?role=lecturer", headers=auth(admin))
        assert r.status_code == 200
        assert r.json()["role"] == "lecturer"

    def test_deactivation_audit_logged(self, client, db, admin, student):
        client.patch(f"/admin/users/{student.id}/deactivate", headers=auth(admin))
        log = db.query(AuditLog).filter_by(
            action=AuditAction.user_deactivated, target_id=student.id
        ).first()
        assert log is not None
        assert log.user_id == admin.id