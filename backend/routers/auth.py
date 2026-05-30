"""
backend/routers/auth.py

Rate limiting: simple in-process sliding-window limiter (no extra dependencies).
For multi-worker / multi-instance deployments, replace _RateLimiter with a
Redis-backed implementation.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from collections import defaultdict, deque
import secrets
import os
import time
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


# ── Simple in-process rate limiter ────────────────────────────────────────────

class _RateLimiter:
    """
    Sliding-window rate limiter keyed by IP.
    Default: 10 requests per 60 seconds per IP.
    Thread-safe enough for single-worker uvicorn; for multi-worker use Redis.
    """
    def __init__(self, max_calls: int = 10, period_seconds: int = 60):
        self.max_calls = max_calls
        self.period = period_seconds
        self._calls: dict = defaultdict(deque)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        window_start = now - self.period
        q = self._calls[key]
        # evict timestamps outside the window
        while q and q[0] < window_start:
            q.popleft()
        if len(q) >= self.max_calls:
            return False
        q.append(now)
        return True


_limiter = _RateLimiter(max_calls=10, period_seconds=60)


def _check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if not _limiter.is_allowed(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a minute and try again.",
        )


# ── Email stub ─────────────────────────────────────────────────────────────────

def send_reset_email_bg(email: str, token: str, frontend_url: str):
    """
    STUB — password reset emails are NOT sent yet.

    To enable real emails, integrate one of:
      - Resend:   pip install resend  →  resend.Emails.send(...)
      - SendGrid: pip install sendgrid
      - AWS SES:  pip install boto3

    Until then the reset URL is written to the Render log (operator-assisted reset).
    """
    reset_url = f"{frontend_url}/reset-password?token={token}"
    logger.warning(
        "[EMAIL STUB] Password reset for %s — no email sent. "
        "Reset URL (Render logs only): %s",
        email, reset_url,
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=schemas.Token, status_code=201)
async def signup(request: Request, payload: schemas.UserSignup, db: Session = Depends(get_db)):
    _check_rate_limit(request)
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
    _check_rate_limit(request)
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
    _check_rate_limit(request)
    user = db.query(models.User).filter(models.User.email == payload.email).first()
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
        models.User.reset_token_expiry > datetime.utcnow(),
    ).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.hashed_password = get_password_hash(payload.new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()

    return {"message": "Password reset successful. Please log in with your new password."}
