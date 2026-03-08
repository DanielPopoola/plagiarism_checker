from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, lecturer_or_admin
from ..database import get_db
from ..models import PlagiarismJob, Role, User
from ..repositories import submission as sub_repo
from ..schemas import JobOut, SubmissionOut
from ..services import submission as sub_svc

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("/{exam_id}", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
async def upload_submission(
    exam_id: int,
    file: UploadFile,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if user.role != Role.student:
        raise HTTPException(status_code=403, detail="Only students can submit")
    return sub_svc.upload(db, exam_id, file, user, ip=None)


@router.get("/{exam_id}", response_model=list[SubmissionOut])
def list_submissions(
    exam_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    from ..repositories import exam as exam_repo

    exam = exam_repo.get(db, exam_id)
    if exam.lecturer_id != user.id and user.role != Role.admin:
        raise HTTPException(status_code=403, detail="Not your exam")
    return sub_repo.list_by_exam(db, exam_id)


@router.get("/{exam_id}/job", response_model=JobOut)
def get_job_status(
    exam_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    job = db.query(PlagiarismJob).filter_by(exam_id=exam_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="No analysis job found for this exam")
    return job
