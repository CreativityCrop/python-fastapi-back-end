from fastapi import APIRouter, File
from io import StringIO
import csv

from app.database import database
from app.internal.responses.users import User, UsersList

router = APIRouter(
    prefix="/users",
)


@router.get("/", response_model=UsersList)
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
    await database.execute(
        query="DELETE FROM users WHERE id=:user_id",
        values={"user_id": user_id}
    )


# Route to update user password
@router.put("/{user_id}/password")
async def update_user_password(user_id: int, pass_hash: str):
    salt = auth.generate_salt()
    await database.execute(
        query="UPDATE users SET salt=:salt, pass_hash=:pass_hash WHERE id=:user_id",
        values={
            "salt": salt,
            "pass_hash": auth.hash_password(pass_hash, salt),
            "user_id": user_id
        }
    )


# Route to export users to csv file
# @router.get("/export", dependencies=None)
# async def export_users():
#     users = await database.fetch_all(
#         query="SELECT users.id, verified, first_name, last_name, email, username, iban, date_register, date_login, "
#               "files.public_path AS avatar_url "
#               "FROM users "
#               "LEFT JOIN files ON users.avatar_id=files.id "
#     )
#     f = StringIO()
#
#     keys = users[0].keys()
#     dict_writer = csv.DictWriter(f, keys)
#     dict_writer.writeheader()
#     dict_writer.writerows(map(lambda user: dict(user), users))
#     f.close()
#     return File(f)
