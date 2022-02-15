from fastapi import Header

from .authentication import verify_access_token


async def get_token_data(token: str = Header(None, convert_underscores=False)):
    return verify_access_token(token)
