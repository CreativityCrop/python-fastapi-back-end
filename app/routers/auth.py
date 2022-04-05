from fastapi import APIRouter, Header
from fastapi.responses import RedirectResponse
import requests
import json
from datetime import datetime

from app.config import DB_USER, DB_PASS, DB_NAME, DB_HOST, MAILGUN_API_KEY
from app.database import database
from app import authentication as auth
from app.models.user import UserRegister, UserLogin, UserPasswordReset, UserPasswordUpdate
from app.models.token import AccessToken, EmailVerifyToken, PasswordResetToken
from app.errors.auth import *
from asyncmy.errors import IntegrityError
from app.responses.auth import TokenResponse, PasswordResetResponse

router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)


@router.post("/register")
async def register_user(user: UserRegister):
    query = "INSERT INTO users(first_name, last_name, email, iban, username, salt, pass_hash, date_register) " \
            "VALUES(:first_name, :last_name, :email, :iban, :username, :salt, :pass_hash, :date_register)"
    salt = auth.generate_salt()
    data = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "iban": user.iban,
        "username": user.username,
        "salt": salt,
        "pass_hash": auth.hash_password(user.pass_hash, salt),
        "date_register": datetime.now().isoformat()
    }
    try:
        await database.execute(query=query, values=data)
    except IntegrityError as ex:
        field = ex.args[1].split()[5]
        if field == "'email'":
            raise EmailDuplicateError
        if field == "'username'":
            raise UsernameDuplicateError
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ex.__dict__)
    user_id = await database.fetch_val(
        query="SELECT id FROM users WHERE username=:username",
        values={"username": user.username},
        column=0
    )

    email_token = auth.create_email_verify_token(
        EmailVerifyToken(user_id=user_id, user=user.username, email=user.email)
    )

    requests.post(
        "https://api.eu.mailgun.net/v3/app.creativitycrop.tech/messages",
        auth=("api", str(MAILGUN_API_KEY)),
        data={
            "from": "Friendly Bot from CreativityCrop <no-reply@app.creativitycrop.tech>",
            "to": user.email,
            "subject": "CreativityCrop - Account Verification",
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
    result = await database.fetch_one(
        query='SELECT * FROM users WHERE username = :username',
        values={"username": user.username}
    )

    if result is None:
        raise UserNotFoundError
    # User need to verify the account to login
    if result["verified"] == 0:
        raise UserNotVerifiedError
    if not auth.verify_password(user.pass_hash, result["salt"], result["pass_hash"]):
        raise PasswordIncorrectError

    await database.execute(
        query="UPDATE users SET date_login = :date_login WHERE users.username = :username",
        values={"date_login": datetime.now().isoformat(), "username": user.username}
    )
    access_token = auth.create_access_token(
        AccessToken(user_id=result["id"], user=user.username)
    )
    return TokenResponse(accessToken=access_token)


@router.get("/verify", response_model=AccessToken)
def verify_token(token: str = Header(None, convert_underscores=False)):
    return auth.verify_access_token(token)


@router.get("/verify-email", response_class=RedirectResponse)
async def verify_email_account(token: str):
    # Here token must be a query parameter
    token_data = auth.verify_email_verify_token(token)

    await database.execute(
        query="UPDATE users SET verified=TRUE WHERE email = :email",
        values={"email": token_data.email}
    )

    # auth_token = auth.create_access_token(AccessToken(user_id=token_data.user_id, user=token_data.user))
    return RedirectResponse("https://creativitycrop.tech/login?email_verified=true")


@router.post("/request-password-reset", response_model=PasswordResetResponse)
async def request_password_reset(email: UserPasswordReset):
    user = await database.fetch_one(
        query="SELECT id, first_name, username, email FROM users WHERE email=:email",
        values={"email": email.email}
    )
    if user is None:
        raise EmailNotFoundError
    password_reset_token = auth.create_password_reset_token(
        PasswordResetToken(user_id=user["id"], user=user["username"], email=user["email"])
    )
    requests.post(
        "https://api.eu.mailgun.net/v3/app.creativitycrop.tech/messages",
        auth=("api", str(MAILGUN_API_KEY)),
        data={
            "from": "Friendly Bot from CreativityCrop <no-reply@app.creativitycrop.tech>",
            "to": user["email"],
            "subject": "CreativityCrop - Account Password Recovery",
            "template": "password-recovery",
            'h:X-Mailgun-Variables': json.dumps({
                "user_name": user["first_name"],
                "password_token": password_reset_token,
                "current_year": datetime.now().year
            })
        }
    )

    return PasswordResetResponse(status="success")


@router.put("/password-reset", response_model=TokenResponse)
async def password_reset(new_data: UserPasswordUpdate, token: str = Header(None, convert_underscores=False)):
    token_data = auth.verify_password_reset_token(token)
    salt = auth.generate_salt()

    await database.execute(
        query="UPDATE users SET salt=:salt, pass_hash=:pass_hash WHERE id=:id",
        values={
            "salt": salt,
            "pass_hash": auth.hash_password(new_data.pass_hash, salt),
            "id": token_data.user_id
        }
    )

    access_token = auth.create_access_token(AccessToken(user_id=token_data.user_id, user=token_data.user))
    return TokenResponse(accessToken=access_token)
