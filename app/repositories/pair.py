from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import SimilarityPair, Submission


def get(db: Session, pair_id: int) -> SimilarityPair:
    p = db.get(SimilarityPair, pair_id)
    if not p:
        raise HTTPException(status_code=404)
    return p


def list_by_exam(db: Session, exam_id: int, min_score: float = 0.0) -> list[SimilarityPair]:
    sub_ids = [s.id for s in db.query(Submission.id).filter_by(exam_id=exam_id)]
    if not sub_ids:
        return []
    return (
        db.query(SimilarityPair)
        .filter(
            SimilarityPair.submission_a_id.in_(sub_ids),
            SimilarityPair.similarity_score >= min_score,
        )
        .order_by(SimilarityPair.similarity_score.desc())
        .all()
    )


def list_by_submission(db: Session, submission_id: int) -> list[SimilarityPair]:
    return (
        db.query(SimilarityPair)
        .filter(
            (SimilarityPair.submission_a_id == submission_id)
            | (SimilarityPair.submission_b_id == submission_id)
        )
        .order_by(SimilarityPair.similarity_score.desc())
        .all()
    )
