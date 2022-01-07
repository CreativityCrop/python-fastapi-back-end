from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    id: Optional[int] = None
    first_name: str
    last_name: str
    email: EmailStr
    username: str
    salt: Optional[str] = None
    pass_hash: str
    date_register: Optional[datetime] = None
    date_login: Optional[datetime] = None


class UserLogin(BaseModel):
    username: str
    pass_hash: str


class UserPasswordUpdate(BaseModel):
    name: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None