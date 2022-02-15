from pydantic import BaseModel


class TokenResponse(BaseModel):
    accessToken: str


class PasswordResetResponse(BaseModel):
    status: str
