from fastapi import HTTPException
from starlette import status


# Auth errors
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
        super().__init__(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "title": "Token Null",
            "msg": "Token cannot be null",
            "errno": 104
        })


class TokenExpiredError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
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


# Ideas errors
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


# Files errors
class UploadForbiddenError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Upload Forbidden",
            "msg": "Only idea publisher can upload files for it",
            "errno": 501
        })


class UploadTooLate(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Upload Forbidden",
            "msg": "You cannot upload files after idea is submitted",
            "errno": 502
        })


class FiletypeNotAllowed(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Filetype Is Not Allowed",
            "msg": "You cannot upload this kind of files",
            "errno": 503
        })


# Payment errors
class IdeaBusyError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Idea Busy",
            "msg": "This idea is already sold or in the process of payment",
            "errno": 401
        })


class UnresolvedPaymentExistsError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Unresolved Payment Already Exists",
            "msg": "Finish the previous payment and then start a new one",
            "errno": 402
        })


class IdeaAlreadySoldError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Idea Already Sold",
            "msg": "The idea has been already sold",
            "errno": 403
        })


class PaymentNotFound(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Payment Not Found",
            "msg": "There is no payment with that ID",
            "errno": 404
        })
