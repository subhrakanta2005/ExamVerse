from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models, schemas
from utils.auth import get_current_admin, get_current_user

router = APIRouter()


@router.get("/", response_model=List[schemas.UserOut])
async def list_users(
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    return db.query(models.User).offset(skip).limit(limit).all()


@router.get("/{user_id}", response_model=schemas.UserOut)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.id != user_id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=schemas.UserOut)
async def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.id != user_id and current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = payload.dict(exclude_unset=True)
    # Only admin can change role
    if "role" in update_data and current_user.role != models.UserRole.ADMIN:
        del update_data["role"]
    
    for key, value in update_data.items():
        setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}
