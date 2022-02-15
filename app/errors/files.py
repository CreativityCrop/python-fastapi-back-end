from fastapi import HTTPException
from starlette import status


class UploadForbiddenError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Upload Forbidden",
            "msg": "Only idea publisher can upload files for it",
            "errno": 501
        })


class UploadTooLateError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Upload Forbidden",
            "msg": "You cannot upload files after idea is submitted",
            "errno": 502
        })


class FiletypeNotAllowedError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail={
            "title": "Filetype Is Not Allowed",
            "msg": "You cannot upload this kind of files",
            "errno": 503
        })
