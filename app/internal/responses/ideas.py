from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List


class Category(BaseModel):
    category: str


class Idea(BaseModel):
    id: str
    sellerID: int
    buyerID: Optional[int] = None
    title: str
    shortDesc: str
    datePublish: datetime
    dateExpiry: datetime
    dateBought: Optional[datetime] = None
    price: float
    likes: int
    imageURL: Optional[str] = None
    categories: Optional[List[Category]] = None


class IdeasList(BaseModel):
    ideas: List[Idea]
