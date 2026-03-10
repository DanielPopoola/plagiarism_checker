import os
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuditAction, Exam, Submission, User
from ..repositories import submission as sub_repo
from ..services.audit import log as audit
from ..services.crypto import decrypt_file, encrypt_file
from ..services.extraction import extract_text


def upload(db: Session, exam_id: int, file: UploadFile, user: User, ip: str | None) -> Submission:
    from datetime import UTC, datetime

    from ..repositories import exam as exam_repo

    exam = exam_repo.get(db, exam_id)
    now = datetime.now(UTC).replace(tzinfo=None)
    if not (exam.opens_at <= now <= exam.closes_at):
        raise HTTPException(status_code=400, detail="Submission window is not open")

    file_path = _save_file(file, exam)
    encrypt_file(file_path)
    raw_bytes = decrypt_file(file_path)
    ext = file_path.rsplit(".", 1)[-1].lower()
    text = extract_text(raw_bytes, ext)

    sub = sub_repo.upsert(
        db,
        exam_id=exam_id,
        student_id=user.id,
        file_path=file_path,
        original_filename=file.filename,
        extracted_text=text,
    )

    job = sub_repo.upsert_job(db, exam_id)
    from ..tasks.analysis import run_plagiarism_analysis

    task = run_plagiarism_analysis.delay(exam_id)
    job.celery_id = task.id
    db.commit()

    audit(
        db,
        AuditAction.submission_upload,
        user_id=user.id,
        target_id=exam_id,
        target_type="exam",
        ip_address=ip,
    )
    return sub


def _save_file(file: UploadFile, exam: Exam) -> str:
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in exam.allowed_formats.split(","):
        raise HTTPException(status_code=400, detail=f"File type .{ext} not allowed for this exam")
    dest_dir = os.path.join(settings.upload_dir, str(exam.id))
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{uuid.uuid4()}.{ext}")
    max_bytes = exam.max_file_mb * 1024 * 1024
    size = 0
    with open(dest, "wb") as f:
        while chunk := file.file.read(8192):
            size += len(chunk)
            if size > max_bytes:
                f.close()
                os.remove(dest)
                raise HTTPException(
                    status_code=413, detail=f"File exceeds {exam.max_file_mb}MB limit"
                )
            f.write(chunk)
    return dest
