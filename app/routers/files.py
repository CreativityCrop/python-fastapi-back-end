from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from fastapi.responses import FileResponse
from typing import Optional, List
from datetime import datetime
import mysql.connector
import aiofiles as aiofiles
import hashlib

from starlette import status

from app.config import *
import app.authentication as auth
from app.dependencies import get_token_data
from app.functions import verify_idea_id
from app.models.token import AccessToken
from app.errors.files import UploadForbiddenError, UploadTooLateError, FiletypeNotAllowedError

router = APIRouter(
    prefix="/files",
    tags=["files"]
)

db = mysql.connector.connect()


def is_db_up():
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    return True


# Event that set-ups the application for startup
@router.on_event("startup")
async def startup_event():
    global db
    db = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )
    # This makes it work without having to commit after every query
    db.autocommit = True


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
async def upload_files(files: List[UploadFile], idea_id: Optional[str] = None,
                       token_data: AccessToken = Depends(get_token_data)):
    verify_idea_id(idea_id)
    is_db_up()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT date_publish, seller_id FROM ideas WHERE id=%s", (idea_id,))
    result = cursor.fetchone()

    # Only idea seller can upload files
    if token_data.user_id != result["seller_id"]:
        raise UploadForbiddenError
    # File upload is allowed for 5 minutes after idea is posted, to allow slow connections to complete successfully
    if datetime.now() > result["date_publish"] + timedelta(minutes=5):
        raise UploadTooLateError

    for file in files:
        if file.content_type not in CDN_ALLOWED_CONTENT_TYPES:
            raise FiletypeNotAllowedError
        temp = await file.read()
        async with aiofiles.open(f'{CDN_FILES_PATH + get_folder_for_file(file.content_type) + file.filename}',
                                 "wb") as directory:
            await directory.write(temp)
        if file.filename.startswith("title-"):
            file_id = idea_id
        else:
            file_id = hashlib.sha256(
                str(hashlib.sha256(temp).hexdigest() + "#IDEA" + idea_id).encode('utf-8')).hexdigest()
        cursor.execute("INSERT INTO files(id, idea_id, name, size, absolute_path, public_path, content_type)"
                       "VALUES(%s, %s, %s, %s, %s, %s, %s)",
                       (file_id, idea_id, file.filename, file.spool_max_size,
                        f'{CDN_FILES_PATH + get_folder_for_file(file.content_type) + file.filename}',
                        f'{CDN_URL + get_folder_for_file(file.content_type) + file.filename}', file.content_type))
    cursor.close()

    return


@router.get("/download", response_class=FileResponse)
async def download_file(file_id: str, token: str):
    # Here token must be a query parameter
    auth.verify_access_token(token)
    is_db_up()

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM files WHERE id=%s", (file_id,))
    file = cursor.fetchone()

    cursor.close()
    # Because of security measures in browser, downloads can only be initiated by same domain,
    # so we need to get a file and return it as response
    return FileResponse(path=file["absolute_path"], filename=file["name"], media_type=file["content_type"])


@router.on_event("shutdown")
async def shutdown_event():
    db.close()
