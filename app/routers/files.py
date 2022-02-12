from fastapi import APIRouter, Header, File, UploadFile
from fastapi.responses import FileResponse
import mysql.connector
import aiofiles as aiofiles
import hashlib

from app.config import *
import app.authentication as auth
from app.models.user import *
from app.models.errors import *


router = APIRouter(
    prefix="/account",
    tags=["account"]
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
        raise TypeError


@router.post("/api/files/upload")
async def upload_files(idea_id: Optional[str] = None, files: list[UploadFile] = File(...),
                       token: str = Header(None, convert_underscores=False)):
    token_data = auth.verify_access_token(token)
    if len(idea_id) != len(hashlib.md5().hexdigest()):
        raise IdeaIDInvalidError
    # TODO: File upload part

    is_db_up()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT date_publish, seller_id FROM ideas WHERE id=%s", (idea_id,))
    result = cursor.fetchone()
    if token_data.user_id != result["seller_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"msg": "You cannot upload files for ideas that aren't yours"}
                            )
    if datetime.now() > result["date_publish"] + timedelta(minutes=5):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"msg": "You cannot upload files after idea submission"}
                            )
    for file in files:
        if file.content_type not in CDN_ALLOWED_CONTENT_TYPES:
            raise HTTPException(status_code=406, detail="File type is not allowed for upload!")
        temp = await file.read()
        async with aiofiles.open(f'{CDN_FILES_PATH + get_folder_for_file(file.content_type) + file.filename}',
                                 "wb") as directory:
            await directory.write(temp)
        if file.filename.startswith("title-"):
            file_id = idea_id
        else:
            file_id = hashlib.md5(temp).hexdigest()
        cursor.execute("INSERT INTO files(id, idea_id, name, size, absolute_path, public_path, content_type)"
                       "VALUES(%s, %s, %s, %s, %s, %s, %s)",
                       (file_id, idea_id, file.filename, file.spool_max_size,
                        f'{CDN_FILES_PATH + get_folder_for_file(file.content_type) + file.filename}',
                        f'{CDN_URL + get_folder_for_file(file.content_type) + file.filename}', file.content_type))
    cursor.close()

    return


@router.get("/api/files/download")
async def download_file(file_id: str, token: str):
    auth.verify_access_token(token)

    is_db_up()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM files WHERE id=%s", (file_id,))
    file = cursor.fetchone()
    cursor.close()

    return FileResponse(path=file["absolute_path"], filename=file["name"], media_type=file["content_type"])


@router.on_event("shutdown")
async def shutdown_event():
    db.close()
