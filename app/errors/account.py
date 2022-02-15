from fastapi import HTTPException
from starlette import status


class InvoiceUnavailableYetError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "title": "Invoice Unavailable Yet",
            "msg": "You cannot access the invoice yet",
            "errno": 301
        })


class InvoiceAccessUnauthorizedError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Invoice Access Denied",
            "msg": "You cannot access this invoice",
            "errno": 302
        })