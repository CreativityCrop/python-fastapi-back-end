import hashlib

from app.models.errors import IdeaIDInvalidError


def calculate_idea_id(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def verify_idea_id(idea_id: str):
    if len(idea_id) != len(hashlib.sha256().hexdigest()):
        raise IdeaIDInvalidError
