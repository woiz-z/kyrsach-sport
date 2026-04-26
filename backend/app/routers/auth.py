from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.models import User, PasswordResetToken
from app.schemas.schemas import (
    UserCreate, UserLogin, UserResponse, Token,
    PasswordResetRequest, PasswordResetConfirm,
)
from app.services.auth import hash_password, verify_password, create_access_token, get_current_user
from app.services.email import send_password_reset_email
from app.config import get_settings
from slowapi import Limiter
from slowapi.util import get_remote_address
import secrets
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/api/auth", tags=["Auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("10/minute")
async def register(request: Request, data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(User).where((User.username == data.username) | (User.email == data.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Користувач з таким ім'ям або email вже існує")

    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("20/minute")
async def login(request: Request, data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Невірне ім'я користувача або пароль")

    token = create_access_token({"sub": user.id})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password", status_code=200)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a password-reset link to the user's email.

    Always returns 200 to prevent user-enumeration.
    """
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user:
        token_value = secrets.token_urlsafe(48)
        expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token_value,
            expires_at=expires,
        )
        db.add(reset_token)
        await db.flush()

        settings = get_settings()
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token_value}"
        try:
            await send_password_reset_email(user.email, reset_link)
        except Exception:
            # Log already done inside send_password_reset_email; don't expose error to client
            pass

    return {"detail": "Якщо цей email зареєстрований, ви отримаєте лист зі скиданням пароля."}


@router.post("/reset-password", status_code=200)
@limiter.limit("10/minute")
async def reset_password(
    request: Request,
    data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Validate the reset token and set a new password."""
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == data.token)
    )
    reset_token = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if (
        reset_token is None
        or reset_token.used
        or reset_token.expires_at.replace(tzinfo=timezone.utc) < now
    ):
        raise HTTPException(status_code=400, detail="Токен недійсний або термін його дії закінчився")

    user_result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="Користувача не знайдено")

    user.password_hash = hash_password(data.new_password)
    reset_token.used = True

    return {"detail": "Пароль успішно змінено"}
