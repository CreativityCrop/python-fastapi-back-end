import decimal
from typing import Optional
from pydantic import BaseModel


class IdeaPost(BaseModel):
    title: str
    short_desc: str
    long_desc: str
    categories: Optional[list] = None
    price: decimal.Decimal
