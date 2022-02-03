from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class AccessToken(BaseModel):
    user: str
    user_id: Optional[int]
    issuer: str
    issued: datetime
    expires: datetime
    exp: int


class PasswordResetToken(BaseModel):
    user: str
    user_id: int
    email: EmailStr
    exp: Optional[int]
