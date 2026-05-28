from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from database import get_db
import models, schemas
from utils.auth import get_current_user, get_current_admin

router = APIRouter()


@router.get("/my", response_model=List[schemas.ResultOut])
async def my_results(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return db.query(models.Result).filter(
        models.Result.user_id == current_user.id,
        models.Result.status == models.ResultStatus.PUBLISHED
    ).order_by(models.Result.created_at.desc()).all()


@router.get("/admin/all")
async def admin_list_results(
    exam_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    q = db.query(models.Result, models.User, models.Exam).join(
        models.User, models.Result.user_id == models.User.id
    ).join(
        models.Exam, models.Result.exam_id == models.Exam.id
    )
    if exam_id:
        q = q.filter(models.Result.exam_id == exam_id)

    rows = q.offset(skip).limit(limit).all()

    return [
        {
            "id":              r.Result.id,
            "attempt_id":      r.Result.attempt_id,
            "user_id":         r.Result.user_id,
            "exam_id":         r.Result.exam_id,
            "total_marks":     r.Result.total_marks,
            "obtained_marks":  r.Result.obtained_marks,
            "percentage":      r.Result.percentage,
            "is_passed":       r.Result.is_passed,
            "correct_count":   r.Result.correct_count,
            "incorrect_count": r.Result.incorrect_count,
            "unattempted_count": r.Result.unattempted_count,
            "section_scores":  r.Result.section_scores,
            "status":          r.Result.status,
            "published_at":    r.Result.published_at,
            "created_at":      r.Result.created_at,
            # Extra fields used by Results.jsx
            "candidate_name":  r.User.full_name,
            "candidate_email": r.User.email,
            "exam_title":      r.Exam.title,
            # is_published alias used by Results.jsx
            "is_published":    r.Result.status == models.ResultStatus.PUBLISHED,
        }
        for r in rows
    ]


@router.get("/attempt/{attempt_id}", response_model=schemas.ResultOut)
async def get_result_by_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    result = db.query(models.Result).filter(models.Result.attempt_id == attempt_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    if result.user_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    return result


@router.get("/{result_id}", response_model=schemas.ResultOut)
async def get_result(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    result = db.query(models.Result).filter(models.Result.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    if result.user_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    if result.status == models.ResultStatus.PENDING and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Result not yet published")
    return result


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.post("/admin/{result_id}/publish")
async def publish_result(
    result_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    result = db.query(models.Result).filter(models.Result.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    result.status = models.ResultStatus.PUBLISHED
    result.published_at = datetime.utcnow()
    db.commit()
    return {"message": "Result published"}


@router.post("/admin/evaluate")
async def evaluate_answer(
    payload: schemas.EvaluateAnswer,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin)
):
    """
    Manually grade a subjective answer.
    Schema field: marks_obtained (matches EvaluateAnswer schema).
    """
    answer = db.query(models.Answer).filter(models.Answer.id == payload.answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    answer.marks_obtained    = payload.marks_obtained
    answer.is_correct        = payload.is_correct
    answer.evaluator_comment = payload.evaluator_comment
    answer.evaluated_by      = current_user.id

    # Recalculate result totals
    result = db.query(models.Result).filter(
        models.Result.attempt_id == answer.attempt_id
    ).first()

    if result:
        all_answers = db.query(models.Answer).filter(
            models.Answer.attempt_id == answer.attempt_id,
            models.Answer.marks_obtained.isnot(None)
        ).all()
        total_obtained = sum(a.marks_obtained or 0 for a in all_answers)
        result.obtained_marks  = max(0.0, total_obtained)
        result.percentage      = max(
            0.0,
            (total_obtained / result.total_marks * 100) if result.total_marks > 0 else 0
        )
        attempt = db.query(models.Attempt).filter(
            models.Attempt.id == answer.attempt_id
        ).first()
        if attempt and attempt.exam:
            result.is_passed = result.percentage >= attempt.exam.pass_percentage
        result.correct_count   = sum(1 for a in all_answers if a.is_correct)
        result.incorrect_count = sum(1 for a in all_answers if a.is_correct is False)

    db.commit()
    return {"message": "Answer evaluated successfully"}
