from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Category(BaseModel):
    category: str


class Idea(BaseModel):
    id: str
    seller_id: int
    buyer_id: Optional[int] = None
    title: str
    short_desc: str
    date_publish: datetime
    date_expiry: datetime
    date_bought: Optional[datetime] = None
    price: float
    likes: int
    title_url: Optional[str] = None
    categories: Optional[List[Category]] = None
