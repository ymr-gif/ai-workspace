import logging
from datetime import timedelta, timezone, datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY
from core.db import get_db
from models import User

logger      = logging.getLogger("auth")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


async def get_user(username: str, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def authenticate_user(username: str, password: str, db: AsyncSession) -> User | None:
    user = await get_user(username, db)
    if not user:
        logger.warning("[auth] user not found username=%s", username)
        return None
    if not verify_password(password, user.hashed_password):
        logger.warning("[auth] invalid password username=%s", username)
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire    = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db:    AsyncSession = Depends(get_db),
) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise exc

    # Try JWT first
    try:
        payload    = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM], options={"verify_aud": False})
        username   = payload.get("sub")
        token_type = payload.get("type")
        if username and token_type == "access":
            user = await get_user(username, db)
            if user and user.is_active:
                return user
            raise exc
    except JWTError:
        pass

    # Fall back to API key lookup
    result = await db.execute(select(User).where(User.api_key == token, User.api_key.isnot(None)))
    user = result.scalar_one_or_none()
    if user and user.is_active:
        return user

    logger.warning("[auth] invalid token/api-key")
    raise exc


def require_role(required_role: str):
    def checker(user: User = Depends(get_current_user)):
        if user.role != required_role:
            logger.warning("[auth] forbidden role=%s required=%s", user.role, required_role)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
        return user
    return checker
