"""
auth.py
───────
Everything JWT:
  - Password hashing (bcrypt via passlib)
  - Token creation & verification (HS256 via python-jose)
  - In-memory user store  ← swap with a real DB in production
  - Pydantic schemas: Token, TokenData
  - FastAPI dependency: get_current_user
  - APIRouter with POST /auth/token and GET /auth/me

Usage in router.py:
    from auth import auth_router, get_current_user
    app.include_router(auth_router)
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY

# ── Password hashing ──────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── OAuth2 token URL ──────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# ── In-memory user store ──────────────────────────────────────────────────────
# Replace with a real database (SQLAlchemy, Tortoise, etc.) in production.
# Run cd tests and test.py to get hashed_passwords in correspondence.
USERS_DB: dict[str, dict] = {
    "admin": {
        "username": "admin",
        "hashed_password": "",  # ADMIN
        "role": "admin",
    },
    "user": {
        "username": "user",
        "hashed_password": "",  # USER
        "role": "user",
    },
}

# ── Pydantic schemas ──────────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int     # seconds until expiry

class TokenData(BaseModel):
    username: str | None = None

# ── Core auth helpers ─────────────────────────────────────────────────────────
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def get_user(username: str) -> dict | None:
    return USERS_DB.get(username)

def authenticate_user(username: str, password: str) -> dict | None:
    """Return user dict if credentials are valid, else None."""
    user = get_user(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES)
    )

    to_encode["exp"] = expire
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:    
    """
    Decode and validate the Bearer token.
    Raises HTTP 401 if the token is missing, invalid, or expired.
    Inject with:  current_user: dict = Depends(get_current_user)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload  = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user(username)
    if user is None:
        raise credentials_exception
    return user
# ── Role enforcement ────────────────────────────────────────────────────────────
def require_role(required_role: str):
    def role_checker(user: dict = Depends(get_current_user)):
        if user["role"] != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return user
    return role_checker

# ── Auth router ───────────────────────────────────────────────────────────────
auth_router = APIRouter(prefix="/auth", tags=["auth"])

@auth_router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Exchange username + password for a signed JWT.
    The token must be sent as:  Authorization: Bearer <token>
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    expires_delta = timedelta(minutes=JWT_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": user["username"], "role": user["role"], "type": "access"},  # Added comma
        expires_delta=expires_delta,  # Fixed param name & position
    )
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=int(expires_delta.total_seconds()),  # Fixed variable
    )


@auth_router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Returns the currently authenticated user's public info."""
    return {"username": current_user["username"], "role": current_user["role"]}