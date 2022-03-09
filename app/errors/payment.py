from fastapi import HTTPException
from starlette import status


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


class PaymentNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Payment Not Found",
            "msg": "There is no payment with that ID",
            "errno": 404
        })


class PaymentCannotBeCanceledError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Payment Cannot Be Canceled",
            "msg": "This payment is successful and cannot be canceled",
            "errno": 405
        })
