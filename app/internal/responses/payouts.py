from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class Payout(BaseModel):
    userID: int
    userFirstName: str
    userLastName: str
    ideaID: str
    date: datetime
    datePaid: Optional[datetime] = None
    status: str
    amount: float
    iban: str


class PayoutsList(BaseModel):
    payouts: List[Payout]
