"""
tests/test_repositories.py

Direct DB-layer tests. No HTTP, no mocks — just repos + in-memory SQLite.
"""

import pytest
from datetime import timedelta

from fastapi import HTTPException

from app.repositories import (
    course as course_repo,
    department as dept_repo,
    enrollment as enroll_repo,
    exam as exam_repo,
    pair as pair_repo,
    submission as sub_repo,
    user as user_repo,
)
from app.models import JobStatus, PlagiarismJob, Role, SimilarityPair, Submission
from conftest import _now, make_user


# ---------------------------------------------------------------------------
# user repo
# ---------------------------------------------------------------------------


class TestUserRepo:
    def test_get_returns_user(self, db, student):
        assert user_repo.get(db, student.id).id == student.id

    def test_get_missing_raises_404(self, db):
        with pytest.raises(HTTPException) as exc:
            user_repo.get(db, 999999)
        assert exc.value.status_code == 404

    def test_get_by_email_found(self, db, student):
        assert user_repo.get_by_email(db, student.email).id == student.id

    def test_get_by_email_missing_returns_none(self, db):
        assert user_repo.get_by_email(db, "nobody@x.com") is None

    def test_list_all(self, db, student, lecturer):
        ids = [u.id for u in user_repo.list_all(db)]
        assert student.id in ids
        assert lecturer.id in ids

    def test_activate(self, db, inactive, admin):
        u = user_repo.activate(db, inactive.id, admin.id)
        assert u.is_active is True

    def test_deactivate(self, db, student, admin):
        u = user_repo.deactivate(db, student.id, admin.id)
        assert u.is_active is False

    def test_deactivate_self_raises_400(self, db, admin):
        with pytest.raises(HTTPException) as exc:
            user_repo.deactivate(db, admin.id, admin.id)
        assert exc.value.status_code == 400

    def test_set_role(self, db, student, admin):
        u = user_repo.set_role(db, student.id, "lecturer")
        assert u.role == Role.lecturer

    def test_set_role_invalid_raises_400(self, db, student):
        with pytest.raises(HTTPException) as exc:
            user_repo.set_role(db, student.id, "superuser")
        assert exc.value.status_code == 400

    def test_set_department(self, db, student, department):
        u = user_repo.set_department(db, student.id, department.id)
        assert u.department_id == department.id

    def test_set_department_missing_raises_404(self, db, student):
        with pytest.raises(HTTPException):
            user_repo.set_department(db, student.id, 999999)


# ---------------------------------------------------------------------------
# department repo
# ---------------------------------------------------------------------------


class TestDepartmentRepo:
    def test_get(self, db, department):
        assert dept_repo.get(db, department.id).id == department.id

    def test_get_missing_raises_404(self, db):
        with pytest.raises(HTTPException) as exc:
            dept_repo.get(db, 999999)
        assert exc.value.status_code == 404

    def test_list_all(self, db, department):
        assert any(d.id == department.id for d in dept_repo.list_all(db))

    def test_create(self, db):
        d = dept_repo.create(db, "Physics", "PHY")
        assert d.id is not None
        assert d.code == "PHY"

    def test_create_duplicate_returns_existing(self, db, department):
        result = dept_repo.create(db, "Different Name", department.code)
        assert result.id == department.id


# ---------------------------------------------------------------------------
# course repo
# ---------------------------------------------------------------------------


class TestCourseRepo:
    def test_get(self, db, course):
        assert course_repo.get(db, course.id).id == course.id

    def test_get_missing_raises_404(self, db):
        with pytest.raises(HTTPException):
            course_repo.get(db, 999999)

    def test_list_by_dept(self, db, course, department):
        ids = [c.id for c in course_repo.list_by_dept(db, department.id)]
        assert course.id in ids

    def test_list_for_admin_sees_all(self, db, course, admin):
        ids = [c.id for c in course_repo.list_for_user(db, admin)]
        assert course.id in ids

    def test_list_for_lecturer_sees_own_dept_only(self, db, course, lecturer, other_lecturer):
        own = [c.id for c in course_repo.list_for_user(db, lecturer)]
        other = [c.id for c in course_repo.list_for_user(db, other_lecturer)]
        assert course.id in own
        assert course.id not in other

    def test_assign_lecturer(self, db, course, lecturer):
        result = course_repo.assign_lecturer(db, course.id, lecturer.id)
        assert result.lecturer_id == lecturer.id

    def test_assign_non_lecturer_raises_400(self, db, course, student):
        with pytest.raises(HTTPException) as exc:
            course_repo.assign_lecturer(db, course.id, student.id)
        assert exc.value.status_code == 400

    def test_delete_returns_dept_id(self, db, department, lecturer):
        c = course_repo.create(
            db,
            title="Temp",
            code="TMP99",
            department_id=department.id,
            lecturer_id=lecturer.id,
            description=None,
            actor_id=lecturer.id,
        )
        dept_id = course_repo.delete(db, c.id)
        assert dept_id == department.id
        with pytest.raises(HTTPException):
            course_repo.get(db, c.id)


# ---------------------------------------------------------------------------
# enrollment repo
# ---------------------------------------------------------------------------


class TestEnrollmentRepo:
    def test_enroll(self, db, student, course, admin):
        e = enroll_repo.enroll(db, student.id, course.id, admin.id)
        assert e.student_id == student.id
        assert e.course_id == course.id

    def test_enroll_duplicate_raises_409(self, db, student, course, admin):
        enroll_repo.enroll(db, student.id, course.id, admin.id)
        with pytest.raises(HTTPException) as exc:
            enroll_repo.enroll(db, student.id, course.id, admin.id)
        assert exc.value.status_code == 409

    def test_enroll_non_student_raises_400(self, db, lecturer, course, admin):
        with pytest.raises(HTTPException) as exc:
            enroll_repo.enroll(db, lecturer.id, course.id, admin.id)
        assert exc.value.status_code == 400

    def test_unenroll(self, db, student, course, admin):
        e = enroll_repo.enroll(db, student.id, course.id, admin.id)
        course_id = enroll_repo.unenroll(db, e.id)
        assert course_id == course.id
        assert enroll_repo.get_for_student_course(db, student.id, course.id) is None

    def test_unenroll_missing_raises_404(self, db):
        with pytest.raises(HTTPException):
            enroll_repo.unenroll(db, 999999)

    def test_unenroll_by_student_course_silent_if_missing(self, db, student, course):
        # no error if not enrolled
        enroll_repo.unenroll_by_student_course(db, student.id, course.id)

    def test_list_by_student(self, db, student, course, admin):
        enroll_repo.enroll(db, student.id, course.id, admin.id)
        ids = [e.course_id for e in enroll_repo.list_by_student(db, student.id)]
        assert course.id in ids


# ---------------------------------------------------------------------------
# exam repo
# ---------------------------------------------------------------------------


class TestExamRepo:
    def test_get(self, db, open_exam):
        assert exam_repo.get(db, open_exam.id).id == open_exam.id

    def test_get_missing_raises_404(self, db):
        with pytest.raises(HTTPException):
            exam_repo.get(db, 999999)

    def test_list_by_course(self, db, open_exam, course):
        ids = [e.id for e in exam_repo.list_by_course(db, course.id)]
        assert open_exam.id in ids

    def test_list_open_for_student_includes_open(self, db, student, course, open_exam, admin):
        enroll_repo.enroll(db, student.id, course.id, admin.id)
        ids = [e.id for e in exam_repo.list_open_for_student(db, student.id)]
        assert open_exam.id in ids

    def test_list_open_excludes_closed(self, db, student, course, closed_exam, admin):
        enroll_repo.enroll(db, student.id, course.id, admin.id)
        ids = [e.id for e in exam_repo.list_open_for_student(db, student.id)]
        assert closed_exam.id not in ids

    def test_list_open_excludes_future(self, db, student, course, future_exam, admin):
        enroll_repo.enroll(db, student.id, course.id, admin.id)
        ids = [e.id for e in exam_repo.list_open_for_student(db, student.id)]
        assert future_exam.id not in ids

    def test_list_open_empty_if_not_enrolled(self, db, student, open_exam):
        assert exam_repo.list_open_for_student(db, student.id) == []

    def test_assert_access_admin_passes(self, db, open_exam, admin):
        exam_repo.assert_access(open_exam, admin)  # no exception

    def test_assert_access_wrong_dept_raises_403(self, db, open_exam, other_lecturer):
        with pytest.raises(HTTPException) as exc:
            exam_repo.assert_access(open_exam, other_lecturer)
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# submission repo
# ---------------------------------------------------------------------------


class TestSubmissionRepo:
    def test_get(self, db, submission):
        assert sub_repo.get(db, submission.id).id == submission.id

    def test_get_missing_raises_404(self, db):
        with pytest.raises(HTTPException):
            sub_repo.get(db, 999999)

    def test_list_by_exam(self, db, submission, open_exam):
        ids = [s.id for s in sub_repo.list_by_exam(db, open_exam.id)]
        assert submission.id in ids

    def test_list_by_student(self, db, submission, student):
        ids = [s.id for s in sub_repo.list_by_student(db, student.id)]
        assert submission.id in ids

    def test_get_for_student_exam(self, db, submission, open_exam, student):
        s = sub_repo.get_for_student_exam(db, open_exam.id, student.id)
        assert s.id == submission.id

    def test_get_for_student_exam_missing_returns_none(self, db, open_exam, admin):
        assert sub_repo.get_for_student_exam(db, open_exam.id, admin.id) is None

    def test_upsert_job_creates_on_first_call(self, db, open_exam):
        job = sub_repo.upsert_job(db, open_exam.id)
        assert job.exam_id == open_exam.id
        assert job.status == JobStatus.pending

    def test_upsert_job_resets_on_second_call(self, db, open_exam):
        job1 = sub_repo.upsert_job(db, open_exam.id)
        job1.status = JobStatus.completed
        db.commit()
        job2 = sub_repo.upsert_job(db, open_exam.id)
        assert job2.id == job1.id
        assert job2.status == JobStatus.pending

    def test_upsert_job_single_record(self, db, open_exam):
        sub_repo.upsert_job(db, open_exam.id)
        sub_repo.upsert_job(db, open_exam.id)
        count = db.query(PlagiarismJob).filter_by(exam_id=open_exam.id).count()
        assert count == 1


# ---------------------------------------------------------------------------
# pair repo
# ---------------------------------------------------------------------------


class TestPairRepo:
    def _seed_pair(self, db, sub_a, sub_b, score=0.8):
        p = SimilarityPair(
            submission_a_id=sub_a.id,
            submission_b_id=sub_b.id,
            similarity_score=score,
            jaccard_score=0.6,
            originality_score=round(1 - score, 2),
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return p

    def _extra_sub(self, db, exam, email):
        u = make_user(db, email, "Extra", Role.student)
        s = Submission(
            exam_id=exam.id, student_id=u.id, file_path="u/x.txt", extracted_text="content " * 20
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        return s

    def test_get(self, db, submission, open_exam):
        s2 = self._extra_sub(db, open_exam, "pair_get@test.com")
        p = self._seed_pair(db, submission, s2)
        assert pair_repo.get(db, p.id).id == p.id

    def test_get_missing_raises_404(self, db):
        with pytest.raises(HTTPException):
            pair_repo.get(db, 999999)

    def test_list_by_exam(self, db, submission, open_exam):
        s2 = self._extra_sub(db, open_exam, "pair_list@test.com")
        p = self._seed_pair(db, submission, s2, score=0.7)
        ids = [x.id for x in pair_repo.list_by_exam(db, open_exam.id)]
        assert p.id in ids

    def test_list_by_exam_min_score_filter(self, db, submission, open_exam):
        s2 = self._extra_sub(db, open_exam, "pair_low@test.com")
        self._seed_pair(db, submission, s2, score=0.1)
        results = pair_repo.list_by_exam(db, open_exam.id, min_score=0.5)
        assert all(p.similarity_score >= 0.5 for p in results)

    def test_list_by_exam_sorted_desc(self, db, submission, open_exam):
        subs = [self._extra_sub(db, open_exam, f"sort_{i}@test.com") for i in range(3)]
        for s, score in zip(subs, [0.9, 0.5, 0.3]):
            self._seed_pair(db, submission, s, score=score)
        results = pair_repo.list_by_exam(db, open_exam.id)
        scores = [p.similarity_score for p in results]
        assert scores == sorted(scores, reverse=True)

    def test_list_by_exam_empty_if_no_submissions(self, db, open_exam):
        from app.models import Exam
        from datetime import UTC, datetime

        empty_exam = Exam(
            course_id=open_exam.course_id,
            title="Empty",
            opens_at=_now() - timedelta(hours=1),
            closes_at=_now() + timedelta(hours=1),
        )
        db.add(empty_exam)
        db.commit()
        assert pair_repo.list_by_exam(db, empty_exam.id) == []

    def test_list_by_submission_both_sides(self, db, submission, open_exam):
        s2 = self._extra_sub(db, open_exam, "pair_both@test.com")
        p = self._seed_pair(db, submission, s2)
        # appears when queried from either side
        from_a = [x.id for x in pair_repo.list_by_submission(db, submission.id)]
        from_b = [x.id for x in pair_repo.list_by_submission(db, s2.id)]
        assert p.id in from_a
        assert p.id in from_b
