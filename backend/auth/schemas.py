from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type:   str
    expires_in:   int


class TokenData(BaseModel):
    username: str | None = None


class RegisterRequest(BaseModel):
    username:     str
    password:     str
    invite_token: str | None = None
