from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class IdeaFile(BaseModel):
    id: str
    ideaID: str
    name: str
    size: int
    absolutePath: str
    publicPath: str
    contentType: str
    uploadDate: datetime


class IdeaSmall(BaseModel):
    id: str
    title: str
    imageURL: Optional[str]
    likes: int


class IdeaPartial(IdeaSmall):
    sellerID: int
    shortDesc: str
    categories: Optional[List[str]]
    datePublish: datetime
    dateExpiry: datetime
    price: float


class IdeaFull(IdeaPartial):
    buyerID: Optional[int]
    longDesc: Optional[str]
    files: Optional[List[IdeaFile]]
    dateBought: Optional[datetime]


class IdeaPost(BaseModel):
    title: str
    short_desc: str
    long_desc: str
    categories: Optional[list] = None
    price: float


class BoughtIdea(IdeaFull):
    pass


class SoldIdea(BaseModel):
    id: str
    sellerID: int
    title: str
    imageURL: Optional[str]
    likes: int
    datePublish: datetime
    dateBought: datetime
    price: float
    payoutStatus: Optional[str]
