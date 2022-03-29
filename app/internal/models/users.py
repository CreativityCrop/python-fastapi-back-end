from pydantic import BaseModel


class PasswordUpdate(BaseModel):
    pass_hash: str
