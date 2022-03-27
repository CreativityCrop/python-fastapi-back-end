from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class User(BaseModel):
    id: int
    verified: bool
    first_name: str
    last_name: str
    email: EmailStr
    username: str
    iban: str
    date_register: datetime
    date_login: Optional[datetime] = None
    avatar_url: Optional[str] = None
