from pydantic import BaseModel
from typing import List

from app.internal.models.ideas import Idea


class IdeasList(BaseModel):
    ideas: List[Idea]
