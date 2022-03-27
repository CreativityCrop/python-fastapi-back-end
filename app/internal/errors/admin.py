from fastapi import HTTPException
from starlette import status


class UserNotAdminError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "title": "You are not an admin",
            "msg": "You cannot access this resource",
            "errno": 601
        })
