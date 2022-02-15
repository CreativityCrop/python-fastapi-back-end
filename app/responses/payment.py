from pydantic import BaseModel


class ClientSecret(BaseModel):
    clientSecret: str
