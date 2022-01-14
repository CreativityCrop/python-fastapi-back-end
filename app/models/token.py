from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AccessToken(BaseModel):
    user: str
    user_id: Optional[int]
    issuer: str = "creativitycrop"
    issued: datetime
    expires: datetime
    exp: int
