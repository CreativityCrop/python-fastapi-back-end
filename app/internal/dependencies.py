from fastapi import Header

from app.config import SUPER_USERS
from app.models.token import AccessToken
from app.dependencies import get_token_data
from app.internal.errors.admin import UserNotAdminError


def verify_admin_user(token: str = Header(None, convert_underscores=False)) -> AccessToken:
    token_data = get_token_data(token)
    if token_data.user not in SUPER_USERS:
        raise UserNotAdminError
    return token_data
