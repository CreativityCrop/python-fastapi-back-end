import decimal
from typing import Optional
from pydantic import BaseModel


class IdeaPost(BaseModel):
    title: str
    short_desc: str
    long_desc: str
    categories: Optional[dict] = None
    price: decimal.Decimal
