from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List


class User(BaseModel):
    id: int
    verified: bool
    firstName: str
    lastName: str
    email: EmailStr
    username: str
    iban: str
    dateRegister: datetime
    dateLogin: Optional[datetime] = None
    avatarURL: Optional[str] = None


class UsersList(BaseModel):
    users: List[User]
