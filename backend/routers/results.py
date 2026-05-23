from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
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


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.get("/admin/all", response_model=List[schemas.ResultOut])
async def admin_list_results(
    exam_id: int = None,
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    q = db.query(models.Result)
    if exam_id:
        q = q.filter(models.Result.exam_id == exam_id)
    return q.offset(skip).limit(limit).all()


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
    answer = db.query(models.Answer).filter(models.Answer.id == payload.answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    
    answer.marks_obtained = payload.marks_obtained
    answer.is_correct = payload.is_correct
    answer.evaluator_comment = payload.evaluator_comment
    answer.evaluated_by = current_user.id
    
    # Recalculate result
    result = db.query(models.Result).filter(models.Result.attempt_id == answer.attempt_id).first()
    if result:
        all_answers = db.query(models.Answer).filter(
            models.Answer.attempt_id == answer.attempt_id,
            models.Answer.marks_obtained.isnot(None)
        ).all()
        total_obtained = sum(a.marks_obtained or 0 for a in all_answers)
        result.obtained_marks = max(0.0, total_obtained)
        result.percentage = max(0.0, (total_obtained / result.total_marks * 100) if result.total_marks > 0 else 0)
        result.is_passed = result.percentage >= answer.attempt.exam.pass_percentage
        result.correct_count = sum(1 for a in all_answers if a.is_correct)
        result.incorrect_count = sum(1 for a in all_answers if a.is_correct is False)
    
    db.commit()
    return {"message": "Answer evaluated successfully"}
