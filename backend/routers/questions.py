from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models, schemas
from utils.auth import get_current_user, get_current_admin

router = APIRouter()


def _check_section_access(section_id: int, current_user: models.User, db: Session) -> models.Section:
    """Allow admin or the exam's creator to read/write questions in a section."""
    section = db.query(models.Section).filter(models.Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    is_admin = current_user.role == models.UserRole.ADMIN
    exam = db.query(models.Exam).filter(models.Exam.id == section.exam_id).first()
    if not is_admin and (not exam or exam.created_by != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorised")
    return section


@router.post("/", response_model=schemas.QuestionOut, status_code=201)
async def create_question(
    payload: schemas.QuestionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    _check_section_access(payload.section_id, current_user, db)

    q_data = payload.dict(exclude={"options"})
    # FIX: QuestionCreate uses 'metadata' but the model column is 'metadata_'
    if "metadata" in q_data:
        q_data["metadata_"] = q_data.pop("metadata")

    question = models.Question(**q_data)
    db.add(question)
    db.flush()

    for opt in (payload.options or []):
        db.add(models.Option(question_id=question.id, **opt.dict()))

    db.commit()
    db.refresh(question)
    return question


@router.put("/{question_id}", response_model=schemas.QuestionOut)
async def update_question(
    question_id: int,
    payload: schemas.QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    question = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    _check_section_access(question.section_id, current_user, db)

    update_data = payload.dict(exclude_unset=True, exclude={"options"})
    # FIX: same metadata → metadata_ remapping
    if "metadata" in update_data:
        update_data["metadata_"] = update_data.pop("metadata")

    for key, value in update_data.items():
        setattr(question, key, value)

    if payload.options is not None:
        db.query(models.Option).filter(models.Option.question_id == question_id).delete()
        for opt in payload.options:
            db.add(models.Option(question_id=question_id, **opt.dict()))

    db.commit()
    db.refresh(question)
    return question


@router.delete("/{question_id}")
async def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    question = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    _check_section_access(question.section_id, current_user, db)
    db.delete(question)
    db.commit()
    return {"message": "Question deleted"}


@router.get("/section/{section_id}", response_model=List[schemas.QuestionOut])
async def get_questions_by_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    _check_section_access(section_id, current_user, db)
    return db.query(models.Question).filter(
        models.Question.section_id == section_id
    ).order_by(models.Question.order).all()
