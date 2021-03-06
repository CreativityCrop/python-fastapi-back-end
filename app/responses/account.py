from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

from app.models.idea import BoughtIdea, SoldIdea, IdeaPartial
from app.responses.auth import TokenResponse


class AccountData(BaseModel):
    id: int
    firstName: str
    lastName: str
    email: EmailStr
    iban: Optional[str]
    username:  str
    dateRegister: datetime
    dateLogin: datetime
    avatarURL: Optional[str]
    unfinishedPaymentIntent: Optional[str]
    unfinishedPaymentIntentSecret: Optional[str]
    unfinishedPaymentIdea: Optional[IdeaPartial]


class AccountUpdate(BaseModel):
    status: str
    token: Optional[TokenResponse]


class BoughtIdeas(BaseModel):
    countLeft: int
    ideas: List[BoughtIdea]


class SoldIdeas(BaseModel):
    countLeft: int
    ideas: List[SoldIdea]


class PayoutRequest(BaseModel):
    status: str


class Invoice(BaseModel):
    id: str
    date: datetime
    userName: str
    userType: str
    ideaID: str
    ideaTitle: str
    ideaShortDesc: Optional[str]
    ideaPrice: str
