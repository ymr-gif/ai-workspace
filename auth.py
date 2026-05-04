"""
auth.py
───────
JWT authentication module

Responsibilities:
- Password hashing / verification
- JWT creation + decoding
- FastAPI dependency: get_current_user
- Role enforcement
- /auth/* router (token + me)

User lookups now go through PostgreSQL via AsyncSession.
USERS_DB has been removed.
"""

from datetime import datetime, timedelta, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY
from db import get_db
from models import User

# ── Logging ───────────────────────────────────────────────────────────────────
logger = logging.getLogger("auth")

# ── Password hashing ──────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── OAuth2 token URL ──────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# ── Schemas ───────────────────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class TokenData(BaseModel):
    username: str | None = None


# ── Core helpers ──────────────────────────────────────────────────────────────
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


async def get_user(username: str, db: AsyncSession) -> dict | None:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    return user.to_dict() if user else None


async def authenticate_user(
    username: str, password: str, db: AsyncSession
) -> dict | None:
    user_dict = await get_user(username, db)

    if not user_dict:
        logger.warning(f"[auth] user not found username={username}")
        return None

    if not verify_password(password, user_dict["hashed_password"]):
        logger.warning(f"[auth] invalid password username={username}")
        return None

    return user_dict


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES)
    )

    to_encode["exp"] = expire

    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# ── Dependency ────────────────────────────────────────────────────────────────
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        username: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if username is None:
            logger.warning("[auth] token missing username")
            raise credentials_exception

        if token_type != "access":
            logger.warning("[auth] invalid token type")
            raise credentials_exception

    except JWTError:
        logger.warning("[auth] JWT decode failed")
        raise credentials_exception

    user = await get_user(username, db)

    if user is None:
        logger.warning(f"[auth] user not found from token username={username}")
        raise credentials_exception

    return user


# ── Role enforcement ──────────────────────────────────────────────────────────
def require_role(required_role: str):
    def role_checker(
        user: dict = Depends(get_current_user),
    ):
        if user["role"] != required_role:
            logger.warning(
                f"[auth] forbidden role={user['role']} required={required_role}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return user

    return role_checker


# ── Router ────────────────────────────────────────────────────────────────────
auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(form_data.username, form_data.password, db)

    if not user:
        logger.warning(f"[auth] login failed username={form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_delta = timedelta(minutes=JWT_EXPIRE_MINUTES)

    token = create_access_token(
        data={
            "sub": user["username"],
            "role": user["role"],
            "type": "access",
        },
        expires_delta=expires_delta,
    )

    logger.info(f"[auth] login success username={user['username']}")

    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=int(expires_delta.total_seconds()),
    )


@auth_router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {
        "username": current_user["username"],
        "role": current_user["role"],
    }