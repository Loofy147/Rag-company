from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User

password_hash = PasswordHash.recommended()
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Passwords must be at least 12 characters long.")
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return password_hash.verify(password, encoded)
    except Exception:
        return False


def issue_access_token(user: User) -> str:
    now = datetime.now(UTC)
    claims = {"sub": str(user.id), "iss": settings.jwt_issuer, "iat": now, "exp": now + timedelta(minutes=settings.jwt_ttl_minutes), "jti": secrets.token_urlsafe(16)}
    return jwt.encode(claims, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def resolve_token(token: str, db: Session) -> User | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM], issuer=settings.jwt_issuer, options={"require": ["exp", "iat", "sub", "iss"]})
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        return None
    user = db.get(User, user_id)
    return user if user and user.is_active else None


def bootstrap_admin(db: Session) -> None:
    username, password = settings.bootstrap_admin_username.strip().lower(), settings.bootstrap_admin_password
    if not username or not password:
        return
    if len(password) < 12:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must be at least 12 characters.")
    if db.query(User).filter(func.lower(User.username) == username.lower()).first():
        return
    db.add(User(username=username, password_hash=hash_password(password), role="admin", groups=["administrators"], is_active=True))
    db.commit()
