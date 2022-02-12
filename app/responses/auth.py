from pydantic import BaseModel


class TokenResponse(BaseModel):
    accessToken: str


class RegisterError(BaseModel):
    msg: str
    errno: int


class LoginError(BaseModel):
    msg: str
    errno: int
