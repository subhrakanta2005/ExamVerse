from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
import random

from database import get_db
import models, schemas
from utils.auth import get_current_user, get_current_admin
from services.grading import auto_grade_attempt

router = APIRouter()


def check_exam_access(exam: models.Exam, user: models.User, db: Session):
    if not exam.is_active:
        raise HTTPException(status_code=403, detail="Exam is not active")
    now = datetime.utcnow()
    if exam.start_time and now < exam.start_time:
        raise HTTPException(status_code=403, detail="Exam has not started yet")
    if exam.end_time and now > exam.end_time:
        raise HTTPException(status_code=403, detail="Exam has ended")

    if not exam.is_public:
        assigned = db.query(models.ExamAssignment).filter(
            models.ExamAssignment.exam_id == exam.id,
            models.ExamAssignment.user_id == user.id
        ).first()
        if not assigned:
            raise HTTPException(status_code=403, detail="You are not assigned to this exam")

    attempt_count = db.query(models.Attempt).filter(
        models.Attempt.exam_id == exam.id,
        models.Attempt.user_id == user.id,
        models.Attempt.status != models.AttemptStatus.IN_PROGRESS
    ).count()
    if attempt_count >= exam.max_attempts:
        raise HTTPException(status_code=403, detail="Maximum attempts reached")


@router.post("/start", response_model=schemas.AttemptOut)
async def start_attempt(
    payload: schemas.AttemptCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    exam = db.query(models.Exam).options(
        joinedload(models.Exam.sections).joinedload(models.Section.questions)
    ).filter(models.Exam.id == payload.exam_id).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    check_exam_access(exam, current_user, db)

    existing = db.query(models.Attempt).filter(
        models.Attempt.exam_id == payload.exam_id,
        models.Attempt.user_id == current_user.id,
        models.Attempt.status == models.AttemptStatus.IN_PROGRESS
    ).first()
    if existing:
        return existing

    question_ids = []
    for section in sorted(exam.sections, key=lambda s: s.order):
        q_ids = [q.id for q in sorted(section.questions, key=lambda q: q.order)]
        if exam.shuffle_questions:
            random.shuffle(q_ids)
        question_ids.extend(q_ids)

    attempt = models.Attempt(
        exam_id=payload.exam_id,
        user_id=current_user.id,
        question_order=question_ids
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


@router.get("/my")
async def my_attempts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Return candidate's attempts enriched with exam_title.
    AttemptHistory.jsx uses attempt.exam_title to display the exam name.
    """
    attempts = db.query(models.Attempt).filter(
        models.Attempt.user_id == current_user.id
    ).order_by(models.Attempt.started_at.desc()).all()

    result = []
    for a in attempts:
        exam = db.query(models.Exam).filter(models.Exam.id == a.exam_id).first()
        result.append({
            "id":                a.id,
            "exam_id":           a.exam_id,
            "exam_title":        exam.title if exam else f"Exam #{a.exam_id}",
            "user_id":           a.user_id,
            "status":            a.status,
            "started_at":        a.started_at,
            "submitted_at":      a.submitted_at,
            "time_spent_seconds":a.time_spent_seconds,
            "tab_switch_count":  a.tab_switch_count,
            "question_order":    a.question_order,
        })
    return result


@router.get("/{attempt_id}", response_model=schemas.AttemptOut)
async def get_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    attempt = db.query(models.Attempt).filter(models.Attempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.user_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    return attempt


@router.get("/{attempt_id}/answers", response_model=List[schemas.AnswerOut])
async def get_attempt_answers(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    attempt = db.query(models.Attempt).filter(models.Attempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.user_id != current_user.id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    return attempt.answers


@router.post("/{attempt_id}/answer")
async def save_answer(
    attempt_id: int,
    payload: schemas.AnswerSubmit,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    attempt = db.query(models.Attempt).filter(
        models.Attempt.id == attempt_id,
        models.Attempt.user_id == current_user.id,
        models.Attempt.status == models.AttemptStatus.IN_PROGRESS
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Active attempt not found")

    question = db.query(models.Question).join(models.Section).filter(
        models.Question.id == payload.question_id,
        models.Section.exam_id == attempt.exam_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in this exam")

    answer = db.query(models.Answer).filter(
        models.Answer.attempt_id == attempt_id,
        models.Answer.question_id == payload.question_id
    ).first()

    if answer:
        answer.selected_option_ids = payload.selected_option_ids
        answer.text_answer = payload.text_answer
        answer.numeric_answer = payload.numeric_answer
        answer.file_url = payload.file_url
        answer.match_answer = payload.match_answer
        answer.is_marked_review = payload.is_marked_review
    else:
        answer = models.Answer(
            attempt_id=attempt_id,
            question_id=payload.question_id,
            selected_option_ids=payload.selected_option_ids,
            text_answer=payload.text_answer,
            numeric_answer=payload.numeric_answer,
            file_url=payload.file_url,
            match_answer=payload.match_answer,
            is_marked_review=payload.is_marked_review
        )
        db.add(answer)

    attempt.current_question_id = payload.question_id
    db.commit()
    return {"message": "Answer saved"}


@router.post("/{attempt_id}/tab-switch")
async def record_tab_switch(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    attempt = db.query(models.Attempt).filter(
        models.Attempt.id == attempt_id,
        models.Attempt.user_id == current_user.id,
        models.Attempt.status == models.AttemptStatus.IN_PROGRESS
    ).first()
    if attempt:
        attempt.tab_switch_count += 1
        db.commit()
    return {"tab_switch_count": attempt.tab_switch_count if attempt else 0}


@router.post("/{attempt_id}/submit", response_model=schemas.ResultOut)
async def submit_attempt(
    attempt_id: int,
    auto_submit: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    attempt = db.query(models.Attempt).filter(
        models.Attempt.id == attempt_id,
        models.Attempt.user_id == current_user.id,
        models.Attempt.status == models.AttemptStatus.IN_PROGRESS
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Active attempt not found")

    attempt.status = models.AttemptStatus.AUTO_SUBMITTED if auto_submit else models.AttemptStatus.SUBMITTED
    attempt.submitted_at = datetime.utcnow()
    db.commit()

    result = auto_grade_attempt(attempt_id, db)
    return result


# ── Admin: All attempts ──────────────────────────────────────────────────────

@router.get("/admin/all", response_model=List[schemas.AttemptOut])
async def admin_list_attempts(
    exam_id: Optional[int] = None,
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    q = db.query(models.Attempt)
    if exam_id:
        q = q.filter(models.Attempt.exam_id == exam_id)
    return q.offset(skip).limit(limit).all()
