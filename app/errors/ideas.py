from fastapi import HTTPException
from starlette import status


class IdeaIDInvalidError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "title": "Invalid Idea ID",
            "msg": "ID validation failed, should be SHA256 hash in hex format",
            "errno": 201
        })


class IdeaNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail={
            "title": "Idea Not Found",
            "msg": "The idea was not found, check the ID",
            "errno": 202
        })


class IdeaAccessDeniedError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Access To Idea Denied",
            "msg": "The idea is not owned by the authenticated user",
            "errno": 203
        })


class IdeaDuplicationError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Idea Duplication",
            "msg": "Please contact us",
            "errno": 204
        })
