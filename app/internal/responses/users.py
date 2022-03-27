from pydantic import BaseModel
from typing import List

from app.internal.models.users import User


class UsersList(BaseModel):
    users: List[User]
