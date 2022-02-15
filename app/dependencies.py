import hashlib

from fastapi import Header

from .authentication import verify_access_token
from .errors.ideas import IdeaIDInvalidError


def get_token_data(token: str = Header(None, convert_underscores=False)):
    return verify_access_token(token)


def verify_idea_id(idea_id: str):
    if len(idea_id) != len(hashlib.sha256().hexdigest()):
        raise IdeaIDInvalidError
    return idea_id
