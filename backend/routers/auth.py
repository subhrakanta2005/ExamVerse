"""
backend/routers/auth.py

Rate limiting is provided by slowapi (wraps limits library).
Add to requirements.txt:  slowapi==0.1.9

If slowapi is not installed, the app still starts — the limiter is applied
only when the dependency is present. To disable rate limiting entirely, set
DISABLE_RATE_LIMIT=true in your environment.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import os
import logging

from database import get_db
import models
import schemas
from utils.auth import (
    verify_password, get_password_hash, create_access_token, get_current_user
)

logger = logging.getLogger(__name__)
router = APIRouter()

RESET_TOKEN_EXPIRE_HOURS = 2
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
DISABLE_RATE_LIMIT = os.getenv("DISABLE_RATE_LIMIT", "false").lower() == "true"

# ── Optional slowapi rate limiter ──────────────────────────────────────────────
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    _limiter = Limiter(key_func=get_remote_address)
    _RATE_LIMIT = "10/minute"
    HAS_LIMITER = True
except ImportError:
    _limiter = None
    HAS_LIMITER = False
    logger.warning(
        "slowapi not installed — auth endpoints have NO rate limiting. "
        "Add slowapi==0.1.9 to requirements.txt and mount the limiter in main.py."
    )


def _rate_limit(request: Request):
    """Apply rate limiting when slowapi is available and not disabled."""
    if HAS_LIMITER and not DISABLE_RATE_LIMIT and _limiter:
        _limiter.limit(_RATE_LIMIT)(lambda r: None)(request)


# ── Email stub ─────────────────────────────────────────────────────────────────

def send_reset_email_bg(email: str, token: str, frontend_url: str):
    """
    STUB — password reset emails are NOT sent in production yet.

    To make this work, integrate an email provider:
      - SendGrid: pip install sendgrid, use sendgrid.SendGridAPIClient
      - AWS SES:  pip install boto3,  use ses_client.send_email(...)
      - Resend:   pip install resend,  use resend.Emails.send(...)

    Until then, the reset URL is logged to stdout (visible in Render logs).
    This means password reset is OPERATOR-ASSISTED only.
    """
    reset_url = f"{frontend_url}/reset-password?token={token}"
    logger.warning(
        "[EMAIL STUB] Password reset requested for %s. "
        "No email was sent. Reset URL (visible in logs only): %s",
        email, reset_url
    )
    # TODO: replace with real email send — remove the log line above when done


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=schemas.Token, status_code=201)
async def signup(request: Request, payload: schemas.UserSignup, db: Session = Depends(get_db)):
    _rate_limit(request)
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
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token({"sub": str(user.id), "role": user.role.value})
        return schemas.Token(
            access_token=token,
            user=schemas.UserOut.model_validate(user),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("SIGNUP ERROR: %r", e)
        raise


@router.post("/login", response_model=schemas.Token)
async def login(request: Request, payload: schemas.UserLogin, db: Session = Depends(get_db)):
    _rate_limit(request)
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return schemas.Token(
        access_token=token,
        user=schemas.UserOut.model_validate(user),
    )


@router.get("/me", response_model=schemas.UserOut)
async def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    payload: schemas.ForgotPassword,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    _rate_limit(request)
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expiry = datetime.utcnow() + timedelta(hours=RESET_TOKEN_EXPIRE_HOURS)
        db.commit()
        background_tasks.add_task(send_reset_email_bg, user.email, token, FRONTEND_URL)

    # Always return the same message to avoid user enumeration
    return {"message": "If that email is registered, you'll receive a password reset link shortly."}


@router.post("/reset-password")
async def reset_password(payload: schemas.ResetPassword, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.reset_token == payload.token,
        models.User.reset_token_expiry > datetime.utcnow(),
    ).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.hashed_password = get_password_hash(payload.new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()

    return {"message": "Password reset successful. Please log in with your new password."}
