from pydantic import BaseModel
from typing import List


class FileUploadResult(BaseModel):
    status: str  # either failed, success, error


class FilesUploadResult(BaseModel):
    successCount: int
    failCount: int
    files: List[FileUploadResult]
