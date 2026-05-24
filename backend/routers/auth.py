from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import os

from database import get_db
import models
import schemas
from utils.auth import (
    verify_password, get_password_hash, create_access_token, get_current_user
)

router = APIRouter()

RESET_TOKEN_EXPIRE_HOURS = 2
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://exam-verse-np738pawm-subhrakantbehera8699-3748s-projects.vercel.app")


def send_reset_email_bg(email: str, token: str, frontend_url: str):
    """Background task for sending reset email (stub - integrate with SendGrid/SES)"""
    reset_url = f"{frontend_url}/reset-password?token={token}"
    print(f"[EMAIL] Password reset link for {email}: {reset_url}")
    # TODO: Integrate with SendGrid, SES, or Resend


@router.post("/signup", response_model=schemas.Token, status_code=201)
async def signup(payload: schemas.UserSignup, db: Session = Depends(get_db)):
    try:
        if db.query(models.User).filter(models.User.email == payload.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        if db.query(models.User).filter(models.User.username == payload.username).first():
            raise HTTPException(status_code=400, detail="Username already taken")

        user = models.User(
            email=payload.email,
            username=payload.username,
            full_name=payload.full_name,
            hashed_password=get_password_hash(payload.password),
            role=models.UserRole.CANDIDATE,
            is_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token({"sub": str(user.id), "role": user.role.value})
        return schemas.Token(
            access_token=token,
            user=schemas.UserOut.from_orm(user)
        )
    except Exception as e:
        print("SIGNUP ERROR:", repr(e))
        raise

@router.post("/login", response_model=schemas.Token)
async def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return schemas.Token(
        access_token=token,
        user=schemas.UserOut.from_orm(user)
    )


@router.get("/me", response_model=schemas.UserOut)
async def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password")
async def forgot_password(
    payload: schemas.ForgotPassword,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    # Always return success to prevent email enumeration
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expiry = datetime.utcnow() + timedelta(hours=RESET_TOKEN_EXPIRE_HOURS)
        db.commit()
        background_tasks.add_task(send_reset_email_bg, user.email, token, FRONTEND_URL)
    
    return {"message": "If that email is registered, you'll receive a password reset link shortly."}


@router.post("/reset-password")
async def reset_password(payload: schemas.ResetPassword, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.reset_token == payload.token,
        models.User.reset_token_expiry > datetime.utcnow()
    ).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.hashed_password = get_password_hash(payload.new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()

    return {"message": "Password reset successful. Please log in with your new password."}
