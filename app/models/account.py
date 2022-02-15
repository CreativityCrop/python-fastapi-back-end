from fastapi import UploadFile, File, Form
from pydantic import BaseModel, EmailStr
from typing import Optional


class Account(BaseModel):
    id: int
    idk: str
