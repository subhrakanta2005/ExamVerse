from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, text
from typing import List, Optional
from datetime import datetime

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


def _check_exam_ownership(exam_id: int, current_user: models.User, db: Session) -> models.Exam:
    """Allow admin OR the exam's creator to modify the exam."""
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    is_admin = current_user.role == models.UserRole.ADMIN
    if not is_admin and exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorised to modify this exam")
    return exam


# ── Create exam (any authenticated user) ─────────────────────────────────────

@router.post("/", response_model=schemas.ExamOut, status_code=201)
async def create_exam(
    payload: schemas.ExamCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
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
    current_user: models.User = Depends(get_current_user)
):
    exam = _check_exam_ownership(exam_id, current_user, db)
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(exam, key, value)
    db.commit()
    return get_exam_or_404(exam_id, db)


# ── Delete exam (cascade-safe via raw SQL) ───────────────────────────────────

@router.delete("/{exam_id}")
async def delete_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    exists = db.execute(text("SELECT id, created_by FROM exams WHERE id = :eid"), {"eid": exam_id}).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Exam not found")

    is_admin = current_user.role == models.UserRole.ADMIN
    is_creator = exists.created_by == current_user.id
    if not is_admin and not is_creator:
        raise HTTPException(status_code=403, detail="Not authorised to delete this exam")

    try:
        db.execute(
            text("DELETE FROM answers WHERE attempt_id IN (SELECT id FROM attempts WHERE exam_id = :eid)"),
            {"eid": exam_id}
        )
        db.execute(text("DELETE FROM results WHERE exam_id = :eid"), {"eid": exam_id})
        db.execute(text("DELETE FROM attempts WHERE exam_id = :eid"), {"eid": exam_id})
        db.execute(text("DELETE FROM exam_assignments WHERE exam_id = :eid"), {"eid": exam_id})
        db.execute(
            text("DELETE FROM options WHERE question_id IN "
                 "(SELECT id FROM questions WHERE section_id IN "
                 "(SELECT id FROM sections WHERE exam_id = :eid))"),
            {"eid": exam_id}
        )
        db.execute(
            text("DELETE FROM questions WHERE section_id IN "
                 "(SELECT id FROM sections WHERE exam_id = :eid)"),
            {"eid": exam_id}
        )
        db.execute(text("DELETE FROM sections WHERE exam_id = :eid"), {"eid": exam_id})
        db.execute(text("DELETE FROM exams WHERE id = :eid"), {"eid": exam_id})
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Exam deleted"}


# ── Sections ─────────────────────────────────────────────────────────────────

@router.post("/{exam_id}/sections", response_model=schemas.SectionOut, status_code=201)
async def add_section(
    exam_id: int,
    payload: schemas.SectionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    _check_exam_ownership(exam_id, current_user, db)
    section = models.Section(exam_id=exam_id, **payload.dict())
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.delete("/{exam_id}/sections/{section_id}")
async def delete_section(
    exam_id: int,
    section_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    _check_exam_ownership(exam_id, current_user, db)
    section = db.query(models.Section).filter(
        models.Section.id == section_id,
        models.Section.exam_id == exam_id
    ).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    db.delete(section)
    db.commit()
    return {"message": "Section deleted"}


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


# ── Get exam detail (admin/owner — includes answers) ─────────────────────────

@router.get("/{exam_id}", response_model=schemas.ExamOut)
async def get_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    exam = get_exam_or_404(exam_id, db)
    # Allow admin or the exam creator to see full detail
    is_admin = current_user.role == models.UserRole.ADMIN
    if not is_admin and exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorised")
    return exam
