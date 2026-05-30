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

    active_exams = db.query(func.count(models.Exam.id)).filter(
        models.Exam.is_active == True
    ).scalar()

    total_attempts = db.query(func.count(models.Attempt.id)).filter(
        models.Attempt.status != models.AttemptStatus.IN_PROGRESS
    ).scalar()

    # Use SQL aggregates — no full table scan into Python
    agg = db.query(
        func.avg(models.Result.percentage).label("avg_pct"),
        func.count(models.Result.id).label("total"),
        func.sum(
            func.cast(models.Result.is_passed, models.db_int_type if hasattr(models, 'db_int_type') else models.Result.is_passed.__class__)
        ).label("passed_count"),
    ).first()

    # Fallback: simple Python aggregation if the cast trick doesn't work cross-DB
    result_rows = db.query(models.Result.percentage, models.Result.is_passed).all()
    if result_rows:
        avg_score = round(sum(r.percentage for r in result_rows) / len(result_rows), 1)
        pass_rate = round(sum(1 for r in result_rows if r.is_passed) / len(result_rows) * 100, 1)
    else:
        avg_score = 0.0
        pass_rate = 0.0

    pending_evaluations = db.query(func.count(models.Answer.id)).filter(
        models.Answer.is_correct.is_(None),
        (models.Answer.text_answer.isnot(None)) | (models.Answer.file_url.isnot(None))
    ).scalar()

    return {
        "total_users":          total_users,
        "total_exams":          total_exams,
        "active_exams":         active_exams,
        "total_attempts":       total_attempts,
        "avg_score":            avg_score,
        "pass_rate":            pass_rate,
        "pending_evaluations":  pending_evaluations,
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
        models.Attempt.status.in_([
            models.AttemptStatus.SUBMITTED,
            models.AttemptStatus.AUTO_SUBMITTED
        ])
    ).count()

    # SQL aggregates for exam-level stats
    agg = db.query(
        func.avg(models.Result.percentage).label("avg"),
        func.max(models.Result.percentage).label("high"),
        func.min(models.Result.percentage).label("low"),
        func.count(models.Result.id).label("cnt"),
    ).filter(models.Result.exam_id == exam_id).first()

    avg_score = round(float(agg.avg or 0), 2)
    highest   = round(float(agg.high or 0), 2)
    lowest    = round(float(agg.low or 0), 2)
    cnt       = agg.cnt or 0

    # Pass rate requires counting booleans — fetch only two columns, not all fields
    pass_count = db.query(func.count(models.Result.id)).filter(
        models.Result.exam_id == exam_id,
        models.Result.is_passed == True
    ).scalar() or 0
    pass_rate = round(pass_count / cnt * 100, 2) if cnt else 0.0

    return schemas.ExamAnalytics(
        exam_id=exam_id,
        exam_title=exam.title if exam else "Unknown",
        total_attempts=total_attempts,
        completed_attempts=completed,
        average_score=avg_score,
        pass_rate=pass_rate,
        highest_score=highest,
        lowest_score=lowest,
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
            "rank":            i + 1,
            "user_id":         r.Result.user_id,
            "full_name":       r.User.full_name,
            "candidate_name":  r.User.full_name,
            "candidate_email": r.User.email,
            "username":        r.User.username,
            "obtained_marks":  r.Result.obtained_marks,
            "total_marks":     r.Result.total_marks,
            "percentage":      r.Result.percentage,
            "is_passed":       r.Result.is_passed,
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
        (models.Answer.text_answer.isnot(None)) | (models.Answer.file_url.isnot(None))
    ).limit(50).all()

    rows = []
    for a in answers:
        attempt  = a.attempt
        question = a.question
        user     = attempt.user if attempt else None
        exam     = attempt.exam if attempt else None
        section  = question.section if question else None

        rows.append({
            "answer_id":         a.id,
            "attempt_id":        a.attempt_id,
            "question_id":       a.question_id,
            "question_text":     question.text if question else "",
            "question_type":     question.question_type if question else "",
            "answer_text":       a.text_answer,
            "file_url":          a.file_url,
            "max_marks":         question.marks if question else 0,
            "awarded_marks":     a.marks_obtained,
            "evaluator_comment": a.evaluator_comment,
            "candidate_name":    user.full_name if user else "",
            "exam_title":        exam.title if exam else "",
            "section_title":     section.title if section else "",
            "model_answer":      question.explanation if question else "",
        })

    return rows
