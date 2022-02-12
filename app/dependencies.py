from fastapi import Header
import mysql
from fastapi import HTTPException
from starlette import status

from .authentication import verify_access_token


async def get_token_header(token: str = Header(...)):
    return verify_access_token(token)

#
# def is_db_up():
#     try:
#        db.ping(reconnect=True, attempts=3, delay=5)
#     except mysql.connector.errors.InterfaceError as ex:
#         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
#     return True
