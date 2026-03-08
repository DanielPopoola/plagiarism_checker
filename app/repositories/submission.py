from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import JobStatus, PlagiarismJob, Submission


def get(db: Session, submission_id: int) -> Submission:
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(status_code=404)
    return s


def list_by_exam(db: Session, exam_id: int) -> list[Submission]:
    return (
        db.query(Submission)
        .filter_by(exam_id=exam_id)
        .order_by(Submission.uploaded_at.desc())
        .all()
    )


def list_by_student(db: Session, student_id: int) -> list[Submission]:
    return (
        db.query(Submission)
        .filter_by(student_id=student_id)
        .order_by(Submission.uploaded_at.desc())
        .all()
    )


def get_for_student_exam(db: Session, exam_id: int, student_id: int) -> Submission | None:
    return db.query(Submission).filter_by(exam_id=exam_id, student_id=student_id).first()


def create(
    db: Session,
    exam_id: int,
    student_id: int,
    file_path: str,
    original_filename: str | None,
    extracted_text: str,
) -> Submission:
    sub = Submission(
        exam_id=exam_id,
        student_id=student_id,
        file_path=file_path,
        original_filename=original_filename,
        extracted_text=extracted_text,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def upsert_job(db: Session, exam_id: int) -> PlagiarismJob:
    job = db.query(PlagiarismJob).filter_by(exam_id=exam_id).first()
    if job:
        job.status = JobStatus.pending
        job.error = None
        job.celery_id = None
        job.finished_at = None
        job.queued_at = datetime.now(UTC)
    else:
        job = PlagiarismJob(exam_id=exam_id)
        db.add(job)
    db.commit()
    db.refresh(job)
    return job
