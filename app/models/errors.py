from fastapi import HTTPException
from starlette import status


# Auth errors
class UserNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail={
            "msg": "Username is wrong or invalid",
            "errno": 101
        })


class PasswordIncorrectError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "msg": "Password is wrong", "errno": 102
        })


class TokenInvalidError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "msg": "Token cannot be null",
            "errno": 103
        })


class UserNotVerified(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "msg": "User is not verified, please check email",
            "errno": 104
        })


# Ideas errors
class IdeaIDInvalidError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "msg": "ID validation failed, should be MD5 hash in hex format",
            "errno": 201
        })


class IdeaNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail={
            "msg": "The idea was not found",
            "errno": 202
        })


class IdeaAccessDeniedError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "msg": "The idea is not owned by the authenticated user",
            "errno": 203
        })
