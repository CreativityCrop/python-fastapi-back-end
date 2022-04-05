from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from io import StringIO
import csv
import json
import requests
from datetime import datetime

from app.config import MAILGUN_API_KEY
from app.database import database
from app import authentication as auth
from app.internal.models.users import PasswordUpdate
from app.internal.responses.users import User, UsersList

router = APIRouter(
    prefix="/users",
)


@router.get("", response_model=UsersList)
async def get_users():
    users = await database.fetch_all(
        query="SELECT users.id, verified, first_name, last_name, email, username, iban, date_register, date_login, "
              "files.public_path AS avatar_url "
              "FROM users "
              "LEFT JOIN files ON users.avatar_id=files.id "
    )

    return UsersList(
        users=list(map(lambda user: User(
            id=user["id"],
            verified=user["verified"],
            firstName=user["first_name"],
            lastName=user["last_name"],
            email=user["email"],
            username=user["username"],
            iban=user["iban"],
            dateRegister=user["date_register"],
            dateLogin=user["date_login"],
            avatarURL=user["avatar_url"]
        ), users))
    )


@router.delete("/{user_id}")
async def delete_user(user_id: int):
    user = await database.fetch_one(
        query="SELECT email, first_name FROM users WHERE id=:user_id",
        values={"user_id": user_id},
    )
    requests.post(
        "https://api.eu.mailgun.net/v3/app.creativitycrop.tech/messages",
        auth=("api", str(MAILGUN_API_KEY)),
        data={
            "from": "Friendly Bot from CreativityCrop <no-reply@app.creativitycrop.tech>",
            "to": user["email"],
            "subject": "CreativityCrop - Account Deleted",
            "template": "delete-user",
            'h:X-Mailgun-Variables': json.dumps({
                "user_name": user["first_name"],
                "current_year": datetime.now().year
            })
        }
    )
    await database.execute(
        query="DELETE FROM users WHERE id=:user_id",
        values={"user_id": user_id}
    )


# Route to update user password
@router.put("/{user_id}/password")
async def update_user_password(user_id: int, update_data: PasswordUpdate):
    salt = auth.generate_salt()
    await database.execute(
        query="UPDATE users SET salt=:salt, pass_hash=:pass_hash WHERE id=:user_id",
        values={
            "salt": salt,
            "pass_hash": auth.hash_password(update_data.pass_hash, salt),
            "user_id": user_id
        }
    )
    return {"status": "success"}


@router.put("/{user_id}/activate")
async def activate_user(user_id: int):
    await database.execute(
        query="UPDATE users SET verified=1 WHERE id=:user_id",
        values={"user_id": user_id}
    )
    return {"status": "success"}


@router.put("/{user_id}/deactivate")
async def deactivate_user(user_id: int):
    await database.execute(
        query="UPDATE users SET verified=0 WHERE id=:user_id",
        values={"user_id": user_id}
    )
    return {"status": "success"}


# Route to export users to csv file
@router.get("/export", dependencies=None)
async def export_users():
    users = await database.fetch_all(
        query="SELECT users.id, verified, first_name, last_name, email, username, iban, date_register, date_login, "
              "files.public_path AS avatar_url "
              "FROM users "
              "LEFT JOIN files ON users.avatar_id=files.id "
    )
    f = StringIO()
    f.write("SEP=,\n")

    keys = users[0].keys()
    dict_writer = csv.DictWriter(f, keys)
    dict_writer.writeheader()
    dict_writer.writerows(map(lambda user: dict(user), users))
    data = f.getvalue()
    f.close()

    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"}
    )
