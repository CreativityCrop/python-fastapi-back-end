from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class User(BaseModel):
    id: Optional[int] = None
    first_name: str
    last_name: str
    email: EmailStr
    username: str
    salt: Optional[str] = None
    pass_hash: str
    date_register: Optional[datetime] = None
    date_login: Optional[datetime] = None


class UserRegister(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    username: str
    iban: str
    pass_hash: str


class UserLogin(BaseModel):
    username: str
    pass_hash: str


class UserPasswordReset(BaseModel):
    email: EmailStr


class UserPasswordUpdate(BaseModel):
    pass_hash: str
