from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
import models, schemas
from utils.auth import get_current_admin

router = APIRouter()


@router.get("/analytics/overview")
async def admin_overview(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    total_users = db.query(func.count(models.User.id)).scalar()
    total_exams = db.query(func.count(models.Exam.id)).scalar()
    total_attempts = db.query(func.count(models.Attempt.id)).filter(
        models.Attempt.status != models.AttemptStatus.IN_PROGRESS
    ).scalar()
    total_results = db.query(func.count(models.Result.id)).scalar()
    
    return {
        "total_users": total_users,
        "total_exams": total_exams,
        "total_attempts": total_attempts,
        "total_results": total_results
    }


@router.get("/analytics/exam/{exam_id}", response_model=schemas.ExamAnalytics)
async def exam_analytics(
    exam_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    
    attempts_q = db.query(models.Attempt).filter(
        models.Attempt.exam_id == exam_id,
        models.Attempt.status != models.AttemptStatus.IN_PROGRESS
    )
    total_attempts = attempts_q.count()
    completed = attempts_q.filter(
        models.Attempt.status.in_([models.AttemptStatus.SUBMITTED, models.AttemptStatus.AUTO_SUBMITTED])
    ).count()
    
    results = db.query(models.Result).filter(models.Result.exam_id == exam_id).all()
    avg_score = sum(r.percentage for r in results) / len(results) if results else 0
    pass_rate = sum(1 for r in results if r.is_passed) / len(results) * 100 if results else 0
    highest = max((r.percentage for r in results), default=0)
    lowest = min((r.percentage for r in results), default=0)
    
    return schemas.ExamAnalytics(
        exam_id=exam_id,
        exam_title=exam.title if exam else "Unknown",
        total_attempts=total_attempts,
        completed_attempts=completed,
        average_score=round(avg_score, 2),
        pass_rate=round(pass_rate, 2),
        highest_score=round(highest, 2),
        lowest_score=round(lowest, 2)
    )


@router.get("/analytics/leaderboard/{exam_id}")
async def exam_leaderboard(
    exam_id: int,
    limit: int = 10,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    results = db.query(models.Result, models.User).join(
        models.User, models.Result.user_id == models.User.id
    ).filter(
        models.Result.exam_id == exam_id
    ).order_by(models.Result.obtained_marks.desc()).limit(limit).all()
    
    return [
        {
            "rank": i + 1,
            "user_id": r.Result.user_id,
            "full_name": r.User.full_name,
            "username": r.User.username,
            "obtained_marks": r.Result.obtained_marks,
            "total_marks": r.Result.total_marks,
            "percentage": r.Result.percentage,
            "is_passed": r.Result.is_passed
        }
        for i, r in enumerate(results)
    ]


@router.get("/manual-queue")
async def manual_eval_queue(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    """Answers pending manual evaluation."""
    answers = db.query(models.Answer).filter(
        models.Answer.is_correct.is_(None),
        models.Answer.text_answer.isnot(None) | models.Answer.file_url.isnot(None)
    ).limit(50).all()
    
    return [
        {
            "answer_id": a.id,
            "attempt_id": a.attempt_id,
            "question_id": a.question_id,
            "question_text": a.question.text if a.question else "",
            "question_type": a.question.question_type if a.question else "",
            "text_answer": a.text_answer,
            "file_url": a.file_url,
            "marks_available": a.question.marks if a.question else 0
        }
        for a in answers
    ]
