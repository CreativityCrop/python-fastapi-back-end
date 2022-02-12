from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class AccessToken(BaseModel):
    user: str
    user_id: Optional[int]
    issuer: Optional[str] = "creativitycrop.tech"
    issued: Optional[str]
    expires: Optional[str]
    exp: Optional[int]


class EmailVerifyToken(BaseModel):
    user: str
    user_id: int
    email: EmailStr
    issuer: Optional[str] = "creativitycrop.tech"
    exp: Optional[int]


class PasswordResetToken(BaseModel):
    user: str
    user_id: int
    email: EmailStr
    issuer: Optional[str] = "creativitycrop.tech"
    exp: Optional[int]
