from pydantic import BaseModel
from typing import List

from app.models.idea import IdeaPartial, IdeaSmall


class IdeasList(BaseModel):
    countLeft: int
    ideas: List[IdeaPartial]


class IdeasHottest(BaseModel):
    ideas: List[IdeaSmall]


class Like(BaseModel):
    isLiked: bool
    count: int
