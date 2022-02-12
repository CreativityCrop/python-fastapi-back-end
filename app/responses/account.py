
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

from app.models.idea import BoughtIdea, SoldIdea


class AccountData(BaseModel):
    id: int
    firstName: str
    lastName: str
    email: EmailStr
    username:  str
    dateRegister: datetime
    dateLogin: datetime
    avatarURL: str
    unfinishedPaymentIntent: Optional[str]
    unfinishedPaymentIdeaID: Optional[str]
    unfinishedPaymentIdeaTitle: Optional[str]
    unfinishedPaymentIdeaShortDesc: Optional[str]
    unfinishedPaymentIdeaPrice: Optional[float]
    unfinishedPaymentIdeaPictureURL: Optional[str]
    unfinishedPaymentIntentSecret: Optional[str]


class BoughtIdeas(BaseModel):
    countLeft: int
    ideas: List[BoughtIdea]


class SoldIdeas(BaseModel):
    countLeft: int
    ideas: List[SoldIdea]
