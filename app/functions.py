from fastapi import UploadFile
from starlette import status
from typing import Optional
import aiofiles as aiofiles
import hashlib
import urllib
import os

from app.config import *
from app.database import database
from app.errors.ideas import IdeaIDInvalidError
from app.errors.files import FiletypeNotAllowedError


def calculate_idea_id(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def verify_idea_id(idea_id: str):
    if len(idea_id) != len(hashlib.sha256().hexdigest()):
        raise IdeaIDInvalidError


def get_folder_for_file(filetype):
    if filetype in CDN_DOCS_TYPES:
        return "docs/"
    elif filetype in CDN_MEDIA_TYPES:
        return "media/"
    elif filetype in CDN_IMAGE_TYPES:
        return "img/"
    else:
        raise FiletypeNotAllowedError


async def save_file(file: UploadFile, kind: str, uid: Optional[str] = None):
    # Open file for reading
    temp = await file.read()

    # There are three file types:
    #  - avatar -> uid is user id
    #  - title images -> uid is idea id
    #  - idea files -> uid is idea id
    #  - others -> uid is None or appended if provided
    if kind == 'avatar':
        file_id = hashlib.sha256(
            str(hashlib.sha256(temp).hexdigest() + "#USER" + uid).encode('utf-8')
        ).hexdigest()
        idea_id = None
        filepath = f'avatars/user#{uid}-{file.filename}'
    elif kind == 'idea-title':
        file_id = uid
        idea_id = uid
        filepath = f'ideas-titles/{uid}-{file.filename}'
    elif kind == 'idea-file':
        file_id = hashlib.sha256(
            str(hashlib.sha256(temp).hexdigest() + "#IDEA" + uid).encode('utf-8')
        ).hexdigest()
        idea_id = uid
        filepath = f'ideas-files/{uid}/{get_folder_for_file(file.content_type)}/{file.filename}'
    else:
        file_id = hashlib.sha256(temp).hexdigest()
        idea_id = None
        filepath = f'others/{uid}_{file.filename}'

    # Create needed dirs if they don't exist
    os.makedirs(os.path.dirname(CDN_FILES_PATH + filepath), exist_ok=True)

    async with aiofiles.open(CDN_FILES_PATH + filepath, "wb") as directory:
        await directory.write(temp)

    # Save info about file to database
    # TODO: if duplication error on id then file probably exists, contact security lol
    await database.execute(
        query="INSERT INTO files(id, idea_id, name, size, absolute_path, public_path, content_type) "
              "VALUES(:id, :idea_id, :name, :size, :absolute_path, :public_path, :content_type)",
        values={
            "id": file_id,
            "idea_id": idea_id,
            "name": file.filename,
            "size": file.spool_max_size,
            "absolute_path": CDN_FILES_PATH + filepath,
            "public_path": CDN_URL + filepath,
            "content_type": file.content_type
        }
    )
