from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models, schemas
from utils.auth import get_current_admin

router = APIRouter()


@router.post("/", response_model=schemas.QuestionOut, status_code=201)
async def create_question(
    payload: schemas.QuestionCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    section = db.query(models.Section).filter(models.Section.id == payload.section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    q_data = payload.dict(exclude={"options"})
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
    _: models.User = Depends(get_current_admin)
):
    question = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    update_data = payload.dict(exclude_unset=True, exclude={"options"})
    for key, value in update_data.items():
        setattr(question, key, value)
    
    if payload.options is not None:
        # Delete old options and recreate
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
    _: models.User = Depends(get_current_admin)
):
    question = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(question)
    db.commit()
    return {"message": "Question deleted"}


@router.get("/section/{section_id}", response_model=List[schemas.QuestionOut])
async def get_questions_by_section(
    section_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    return db.query(models.Question).filter(
        models.Question.section_id == section_id
    ).order_by(models.Question.order).all()
