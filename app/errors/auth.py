from fastapi import HTTPException
from starlette import status


class UserNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail={
            "title": "User Not Found",
            "msg": "Username is wrong or nonexistent",
            "errno": 101
        })


class PasswordIncorrectError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "title": "Password Wrong",
            "msg": "Password is wrong, check if you have Caps Lock active",
            "errno": 102
        })


class UserNotVerifiedError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "title": "Unverified User",
            "msg": "User is not verified, please check email, if needed, contact us",
            "errno": 103
        })


class TokenNullError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "title": "Token Null",
            "msg": "Token cannot be null",
            "errno": 104
        })


class AccessTokenExpiredError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "title": "Token Expired",
            "msg": "Token has expired, please login again",
            "errno": 105
        })


class TokenInvalidError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "title": "Token Invalid",
            "msg": "Token is either invalid or in unsuitable format",
            "errno": 106
        })


class UsernameDuplicateError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail={
            "title": "Username Duplication",
            "msg": "Username is already taken by another user",
            "errno": 107
        })


class EmailDuplicateError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail={
            "title": "Email Duplication",
            "msg": "Email is already used by another user",
            "errno": 108
        })


class PasswordResetTokenExpiredError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "title": "Password Reset Link Expired",
            "msg": "Please request a new password reset link",
            "errno": 109
        })


class EmailVerificationTokenExpiredError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "title": "Account Verification Expired",
            "msg": "You did not verify your account on time, register again",
            "errno": 110
        })


class EmailNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail={
            "title": "Email Not Found",
            "msg": "Email is wrong or there is no account associated with it",
            "errno": 111
        })
