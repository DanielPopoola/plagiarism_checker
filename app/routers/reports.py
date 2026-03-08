from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..auth import lecturer_or_admin
from ..database import get_db
from ..models import AuditAction, ReviewDecision, User
from ..repositories import exam as exam_repo
from ..repositories import pair as pair_repo
from ..repositories import submission as sub_repo
from ..schemas import PairOut, ReviewCreate, ReviewOut
from ..services.audit import log as audit

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{exam_id}/pairs", response_model=list[PairOut])
def get_pairs(
    exam_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
    min_score: float = 0.0,
):
    exam = exam_repo.get(db, exam_id)
    exam_repo.assert_access(exam, user)
    audit(
        db,
        AuditAction.report_viewed,
        user_id=user.id,
        target_id=exam_id,
        target_type="exam",
        ip_address=request.client.host if request.client else None,
    )
    return pair_repo.list_by_exam(db, exam_id, min_score)


@router.get("/pairs/{pair_id}", response_model=PairOut)
def get_pair(
    pair_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    return pair_repo.get(db, pair_id)


@router.post("/pairs/{pair_id}/review", response_model=ReviewOut)
def review_pair(
    pair_id: int,
    body: ReviewCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(lecturer_or_admin)],
):
    from datetime import UTC, datetime

    pair = pair_repo.get(db, pair_id)
    sub_a = sub_repo.get(db, pair.submission_a_id)
    exam = exam_repo.get(db, sub_a.exam_id)
    exam_repo.assert_access(exam, user)
    review = pair.review or ReviewDecision(pair_id=pair_id)
    review.reviewer_id = user.id
    review.status = body.status
    review.notes = body.notes
    review.decided_at = datetime.now(UTC)
    if not pair.review:
        db.add(review)
    db.commit()
    db.refresh(review)
    audit(db, AuditAction.review_decision, user_id=user.id, target_id=pair_id, target_type="pair")
    return review
