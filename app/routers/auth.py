from fastapi import APIRouter, Header
import mysql.connector
import requests
import json

from app.config import *
from app import authentication as auth
from app.models.user import *
from app.models.errors import *


router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
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


@router.post("/register")
async def register_user(user: UserRegister):
    salt = auth.generate_salt()
    is_db_up()
    cursor = db.cursor()
    query = "INSERT INTO users(first_name, last_name, email, username, salt, pass_hash, date_register) " \
            "VALUES(%s, %s, %s, %s, %s, %s, %s)"
    data = (user.first_name, user.last_name, user.email, user.username,
            salt, auth.hash_password(user.pass_hash, salt), datetime.now().isoformat())
    try:
        cursor.execute(query, data)
    except mysql.connector.errors.IntegrityError as ex:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ex.__dict__)
    # user_id = cursor.lastrowid
    cursor.close()

    requests.post(
        "https://api.eu.mailgun.net/v3/app.creativitycrop.tech/messages",
        auth=("api", str(MAILGUN_API_KEY)),
        data={
            "from": "Friendly Bot from CreativityCrop <no-reply@app.creativitycrop.tech>",
            "to": user.email,
            "subject": "CreativityCrop - Account Password Recovery  ",
            "template": "confirm-email",
            'h:X-Mailgun-Variables': json.dumps({
                "user_name": user.first_name,
                "email": user.email,
                "current_year": datetime.now().year
            })
        }
    )
    # access_token = auth.create_access_token(
    #     data={
    #         "user": user.username,
    #         "user_id": user_id
    #     }
    # )
    # return {
    #     "accessToken": access_token,
    #     "expiresIn": JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    #     "authUserState": {
    #         "firstName": user.first_name,
    #         "lastName": user.last_name,
    #         "username": user.username,
    #         "email": user.email
    #     }
    # }
    return


@router.post("/login")
async def login_user(user: UserLogin):
    is_db_up()
    cursor = db.cursor(dictionary=True)
    query = 'SELECT * FROM users WHERE username = %s'
    cursor.execute(query, (user.username,))
    result = cursor.fetchone()
    if result is None:
        raise UserNotFoundError
    if result["verified"] == 0:
        raise UserNotVerified
    if not auth.verify_password(user.pass_hash, result["salt"], result["pass_hash"]):
        raise PasswordIncorrectError
    user_id = result["id"]
    query = "UPDATE users SET date_login = %s WHERE users.username = %s;"
    cursor.execute(query, (datetime.now().isoformat(), user.username))
    access_token = auth.create_access_token(
        data={
            "user": user.username,
            "user_id": user_id
        }
    )
    cursor.close()
    return {
        "accessToken": access_token,
        "expiresIn": JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        "authUserState": {
            "username": user.username
        }
    }


@router.get("/verify")
def verify_token(token: str = Header(None, convert_underscores=False)):
    return auth.verify_access_token(token)


@router.on_event("shutdown")
async def shutdown_event():
    db.close()
