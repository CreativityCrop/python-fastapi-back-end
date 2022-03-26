from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from fastapi.responses import FileResponse
from typing import Optional, List
from datetime import datetime
import mysql.connector
import aiofiles as aiofiles
import hashlib

from starlette import status

from app.config import *
from app.database import database
import app.authentication as auth
from app.dependencies import get_token_data
from app.functions import verify_idea_id
from app.models.token import AccessToken
from app.errors.files import UploadForbiddenError, UploadTooLateError, FiletypeNotAllowedError, FileAccessDeniedError

router = APIRouter(
    prefix="/files",
    tags=["files"]
)


def get_folder_for_file(filetype):
    if filetype in CDN_DOCS_TYPES:
        return "docs/"
    elif filetype in CDN_MEDIA_TYPES:
        return "media/"
    elif filetype in CDN_IMAGE_TYPES:
        return "img/"
    else:
        raise FiletypeNotAllowedError


@router.post("/upload")
async def upload_files(
        files: List[UploadFile],
        idea_id: Optional[str] = None,
        token_data: AccessToken = Depends(get_token_data)
):
    verify_idea_id(idea_id)
    result = await database.fetch_one(
        query="SELECT date_publish, seller_id FROM ideas WHERE id=:idea_id",
        values={"idea_id": idea_id}
    )

    # Only idea seller can upload files
    if token_data.user_id != result["seller_id"]:
        raise UploadForbiddenError
    # File upload is allowed for 5 minutes after idea is posted, to allow slow connections to complete successfully
    if datetime.now() > result["date_publish"] + timedelta(minutes=5):
        raise UploadTooLateError

    for file in files:
        if file.content_type not in CDN_ALLOWED_CONTENT_TYPES:
            raise FiletypeNotAllowedError

        # Open file for reading
        temp = await file.read()
        async with aiofiles.open(f'{CDN_FILES_PATH + get_folder_for_file(file.content_type) + idea_id + "_" + file.filename}', "wb") as directory:
            await directory.write(temp)
        # If filename starts with title, it is title image for idea, so file_id needs to be the same as idea_id
        if file.filename.startswith("title-"):
            file_id = idea_id
        else:
            file_id = hashlib.sha256(
                str(hashlib.sha256(temp).hexdigest() + "#IDEA" + idea_id).encode('utf-8')
            ).hexdigest()
        # Save info about file to database
        await database.execute(
            query="INSERT INTO files(id, idea_id, name, size, absolute_path, public_path, content_type) "
                  "VALUES(:id, :idea_id, :name, :size, :absolute_path, :public_path, :content_type)",
            values={
                "id": file_id,
                "idea_id": idea_id,
                "name": file.filename,
                "size": file.spool_max_size,
                "absolute_path": f'{CDN_FILES_PATH + get_folder_for_file(file.content_type) + idea_id + "_" + file.filename}',
                "public_path": f'{CDN_URL + get_folder_for_file(file.content_type) + idea_id + "_" + file.filename}',
                "content_type": file.content_type
            }
        )

    return {"status": "success"}


@router.get("/download", response_class=FileResponse)
async def download_file(file_id: str, token: str):
    # Here token has to be a query parameter
    token_data = auth.verify_access_token(token)
    # Get info about file from database
    file = await database.fetch_one(
        query="SELECT *, ideas.buyer_id AS buyer_id "
              "FROM files LEFT JOIN ideas ON files.idea_id = ideas.id "
              "WHERE files.id=:file_id",
        values={"file_id": file_id}
    )
    # Check if user has access to download the file
    if file["buyer_id"] != token_data.user_id:
        raise FileAccessDeniedError

    # Because of security measures in browser, downloads can only be initiated by same domain,
    # so we need to get a file and return it as response
    return FileResponse(path=file["absolute_path"], filename=file["name"], media_type=file["content_type"])
