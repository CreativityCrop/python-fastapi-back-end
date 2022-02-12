from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Idea(BaseModel):
    id: str
    sellerID: int
    buyerID: int
    title: str
    shortDesc: str
    imageURL: str
    likes: int
    categories: List[str]
    datePublish: datetime
    dateExpiry: datetime
    dateBought: datetime
    price: float


class IdeaFile(BaseModel):
    id: str
    ideaID: str
    name: str
    size: int
    absolutePath: str
    publicPath: str
    contentType: str
    uploadDate: datetime


class PostIdea(BaseModel):
    title: str
    short_desc: str
    long_desc: str
    categories: Optional[list] = None
    price: float


class BoughtIdea(Idea):
    longDesc: str
    files: List[IdeaFile]


class SoldIdea(BaseModel):
    id: str
    sellerID: int
    title: str
    imageURL: str
    likes: int
    datePublish: datetime
    dateBought: datetime
    price: float
    payoutStatus: Optional[str]
