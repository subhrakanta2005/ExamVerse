from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
from sqlalchemy import text

from database import get_db
import models, schemas
from utils.auth import get_current_user, get_current_admin

router = APIRouter()


def get_exam_or_404(exam_id: int, db: Session) -> models.Exam:
    exam = db.query(models.Exam).options(
        joinedload(models.Exam.sections).joinedload(models.Section.questions).joinedload(models.Question.options)
    ).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


# ── Admin: Create exam ───────────────────────────────────────────────────────

@router.post("/", response_model=schemas.ExamOut, status_code=201)
async def create_exam(
    payload: schemas.ExamCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin)
):
    exam = models.Exam(**payload.dict(), created_by=current_user.id)
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return get_exam_or_404(exam.id, db)


@router.put("/{exam_id}", response_model=schemas.ExamOut)
async def update_exam(
    exam_id: int,
    payload: schemas.ExamUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(exam, key, value)
    db.commit()
    return get_exam_or_404(exam_id, db)


@router.delete("/{exam_id}")
async def delete_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    db.delete(exam)
    db.commit()
    return {"message": "Exam deleted"}


# ── Admin: Sections ──────────────────────────────────────────────────────────

@router.post("/{exam_id}/sections", response_model=schemas.SectionOut, status_code=201)
async def add_section(
    exam_id: int,
    payload: schemas.SectionCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    section = models.Section(exam_id=exam_id, **payload.dict())
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.delete("/{exam_id}")
async def delete_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    # Verify exam exists
    exists = db.execute(text("SELECT id FROM exams WHERE id = :eid"), {"eid": exam_id}).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    try:
        db.execute(text("DELETE FROM answers WHERE attempt_id IN (SELECT id FROM attempts WHERE exam_id = :eid)"), {"eid": exam_id})
        db.execute(text("DELETE FROM results WHERE exam_id = :eid"), {"eid": exam_id})
        db.execute(text("DELETE FROM attempts WHERE exam_id = :eid"), {"eid": exam_id})
        db.execute(text("DELETE FROM exam_assignments WHERE exam_id = :eid"), {"eid": exam_id})
        db.execute(text("DELETE FROM options WHERE question_id IN (SELECT id FROM questions WHERE section_id IN (SELECT id FROM sections WHERE exam_id = :eid))"), {"eid": exam_id})
        db.execute(text("DELETE FROM questions WHERE section_id IN (SELECT id FROM sections WHERE exam_id = :eid)"), {"eid": exam_id})
        db.execute(text("DELETE FROM sections WHERE exam_id = :eid"), {"eid": exam_id})
        db.execute(text("DELETE FROM exams WHERE id = :eid"), {"eid": exam_id})
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
    return {"message": "Exam deleted"}

# ── Assign exam to users ─────────────────────────────────────────────────────

@router.post("/{exam_id}/assign")
async def assign_exam(
    exam_id: int,
    user_ids: List[int],
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    assigned = 0
    for user_id in user_ids:
        exists = db.query(models.ExamAssignment).filter(
            models.ExamAssignment.exam_id == exam_id,
            models.ExamAssignment.user_id == user_id
        ).first()
        if not exists:
            db.add(models.ExamAssignment(exam_id=exam_id, user_id=user_id))
            assigned += 1
    db.commit()
    return {"message": f"Assigned to {assigned} users"}


# ── Admin: List all exams ────────────────────────────────────────────────────

@router.get("/admin/all", response_model=List[schemas.ExamListOut])
async def admin_list_exams(
    skip: int = 0, limit: int = 20,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    exams = db.query(models.Exam).offset(skip).limit(limit).all()
    result = []
    for exam in exams:
        q_count = db.query(func.count(models.Question.id)).join(models.Section).filter(
            models.Section.exam_id == exam.id
        ).scalar()
        exam_dict = {
            **{c.name: getattr(exam, c.name) for c in exam.__table__.columns},
            "question_count": q_count
        }
        result.append(schemas.ExamListOut(**exam_dict))
    return result


# ── Candidate: Available exams ───────────────────────────────────────────────

@router.get("/available", response_model=List[schemas.ExamListOut])
async def get_available_exams(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    now = datetime.utcnow()
    
    # Public exams
    public_q = db.query(models.Exam).filter(
        models.Exam.is_active == True,
        models.Exam.is_public == True
    )
    
    # Assigned exams
    assigned_ids = db.query(models.ExamAssignment.exam_id).filter(
        models.ExamAssignment.user_id == current_user.id
    ).subquery()
    assigned_q = db.query(models.Exam).filter(
        models.Exam.is_active == True,
        models.Exam.id.in_(assigned_ids)
    )
    
    exams = public_q.union(assigned_q).all()
    result = []
    for exam in exams:
        q_count = db.query(func.count(models.Question.id)).join(models.Section).filter(
            models.Section.exam_id == exam.id
        ).scalar()
        exam_dict = {
            **{c.name: getattr(exam, c.name) for c in exam.__table__.columns},
            "question_count": q_count
        }
        result.append(schemas.ExamListOut(**exam_dict))
    return result


# ── Get exam detail (candidate view, no answers) ─────────────────────────────

@router.get("/{exam_id}/candidate", response_model=schemas.ExamOut)
async def get_exam_for_candidate(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    exam = get_exam_or_404(exam_id, db)
    if not exam.is_active:
        raise HTTPException(status_code=403, detail="Exam is not active")
    return exam


# ── Admin: Get exam with answers ─────────────────────────────────────────────

@router.get("/{exam_id}", response_model=schemas.ExamOut)
async def get_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    return get_exam_or_404(exam_id, db)
