from fastapi import APIRouter, Header
from fastapi.responses import RedirectResponse
import mysql.connector
import requests
import json
from datetime import datetime

from app.config import DB_USER, DB_PASS, DB_NAME, DB_HOST, MAILGUN_API_KEY
from app import authentication as auth
from app.models.user import UserRegister, UserLogin, UserPasswordReset, UserPasswordUpdate
from app.models.token import AccessToken, EmailVerifyToken, PasswordResetToken
from app.errors.auth import *
from app.responses.auth import TokenResponse, PasswordResetResponse

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
    is_db_up()
    cursor = db.cursor()
    query = "INSERT INTO users(first_name, last_name, email, iban, username, salt, pass_hash, date_register) " \
            "VALUES(%s, %s, %s, %s, %s, %s, %s, %s)"
    salt = auth.generate_salt()
    data = (user.first_name, user.last_name, user.email, user.iban, user.username,
            salt, auth.hash_password(user.pass_hash, salt), datetime.now().isoformat())
    try:
        cursor.execute(query, data)
    except mysql.connector.errors.IntegrityError as ex:
        field = ex.msg.split()[5]
        if field == "'email'":
            raise EmailDuplicateError
        if field == "'username'":
            raise UsernameDuplicateError
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ex.__dict__)
    user_id = cursor.lastrowid
    cursor.close()

    email_token = auth.create_email_verify_token(
        EmailVerifyToken(user_id=user_id, user=user.username, email=user.email)
    )

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
                "email_token": email_token,
                "current_year": datetime.now().year
            })
        }
    )

    return {"status": "success"}


@router.post("/login", response_model=TokenResponse)
async def login_user(user: UserLogin):
    is_db_up()

    cursor = db.cursor(dictionary=True)
    query = 'SELECT * FROM users WHERE username = %s'
    cursor.execute(query, (user.username,))
    result = cursor.fetchone()

    if result is None:
        raise UserNotFoundError
    # User need to verify the account to login
    if result["verified"] == 0:
        raise UserNotVerifiedError
    if not auth.verify_password(user.pass_hash, result["salt"], result["pass_hash"]):
        raise PasswordIncorrectError

    query = "UPDATE users SET date_login = %s WHERE users.username = %s;"
    cursor.execute(query, (datetime.now().isoformat(), user.username))
    access_token = auth.create_access_token(
        AccessToken(user_id=result["id"], user=user.username)
    )
    cursor.close()
    return TokenResponse(accessToken=access_token)


@router.get("/verify", response_model=AccessToken)
def verify_token(token: str = Header(None, convert_underscores=False)):
    return auth.verify_access_token(token)


@router.get("/verify-email", response_class=RedirectResponse)
async def verify_email_account(token: str):
    is_db_up()
    # Here token must be a query parameter
    token_data = auth.verify_email_verify_token(token)

    cursor = db.cursor(dictionary=True)
    cursor.execute("UPDATE users SET verified=TRUE WHERE email=%s", (token_data.email,))
    cursor.close()
    # auth_token = auth.create_access_token(AccessToken(user_id=token_data.user_id, user=token_data.user))
    return RedirectResponse("https://creativitycrop.tech/login?email_verified=true")


@router.post("/request-password-reset", response_model=PasswordResetResponse)
async def request_password_reset(email: UserPasswordReset):
    is_db_up()

    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, first_name, CONCAT(first_name, ' ', last_name) AS name, username, email FROM users WHERE email=%s",
        (email.email,)
    )
    user = cursor.fetchone()
    if user is None:
        raise EmailNotFoundError
    password_reset_token = auth.create_password_reset_token(
        PasswordResetToken(user_id=user["id"], user=user["name"], email=user["email"])
    )
    requests.post(
        "https://api.eu.mailgun.net/v3/app.creativitycrop.tech/messages",
        auth=("api", str(MAILGUN_API_KEY)),
        data={
            "from": "Friendly Bot from CreativityCrop <no-reply@app.creativitycrop.tech>",
            "to": user["email"],
            "subject": "CreativityCrop - Account Password Recovery  ",
            "template": "password-recovery",
            'h:X-Mailgun-Variables': json.dumps({
                "user_name": user["first_name"],
                "password_token": password_reset_token,
                "current_year": datetime.now().year
            })
        }
    )
    cursor.close()

    return PasswordResetResponse(status="success")


@router.put("/password-reset", response_model=TokenResponse)
async def password_reset(new_data: UserPasswordUpdate, token: str = Header(None, convert_underscores=False)):
    is_db_up()
    token_data = auth.verify_password_reset_token(token)
    salt = auth.generate_salt()

    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "UPDATE users SET salt=%s, pass_hash=%s WHERE id=%s",
        (salt, auth.hash_password(new_data.pass_hash, salt), token_data.user_id,)
    )
    access_token = auth.create_access_token(AccessToken(user_id=token_data.user_id, user=token_data.user))
    cursor.close()

    return TokenResponse(accessToken=access_token)


@router.on_event("shutdown")
async def shutdown_event():
    db.close()
