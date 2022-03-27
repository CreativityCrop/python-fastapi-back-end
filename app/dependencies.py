import hashlib

from fastapi import Header

from app.authentication import verify_access_token
from app.models.token import AccessToken
from app.errors.ideas import IdeaIDInvalidError


def get_token_data(token: str = Header(None, convert_underscores=False)) -> AccessToken:
    return verify_access_token(token)


def verify_idea_id(idea_id: str) -> str:
    if len(idea_id) != len(hashlib.sha256().hexdigest()):
        raise IdeaIDInvalidError
    return idea_id
