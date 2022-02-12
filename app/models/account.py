from pydantic import BaseModel


class Account(BaseModel):
    id: int
    idk: str
