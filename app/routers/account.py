from fastapi import APIRouter, Header, File, UploadFile, Form
from fastapi.responses import RedirectResponse
import mysql.connector
import stripe
import aiofiles as aiofiles
import requests
import hashlib
import json

from app.config import *
import app.authentication as auth
from app.models.user import *
from app.models.token import AccessToken, PasswordResetToken
from app.models.errors import *


router = APIRouter(
    prefix="/account",
    tags=["account"]
)

stripe.api_key = str(STRIPE_API_KEY)

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


@router.get("")
async def get_account(token: str = Header(None, convert_underscores=False)):
    token_data: AccessToken = auth.verify_access_token(token)

    is_db_up()
    cursor = db.cursor(dictionary=True)
    query = "SELECT " \
            "users.id, users.first_name, users.last_name, email, username, date_register, date_login, " \
            "files.public_path AS avatar_url, " \
            "payments.id AS unfinished_intent, payments.idea_id AS unfinished_payment_idea, " \
            "ideas.title, ideas.short_desc, ideas.price, " \
            "(SELECT files.public_path FROM files WHERE files.id=payments.idea_id ) AS idea_img " \
            "FROM users " \
            "LEFT JOIN files ON users.avatar_id=files.id " \
            "LEFT JOIN payments ON users.id=payments.user_id AND payments.status != 'succeeded' " \
            "AND payments.date > DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 MINUTE)" \
            "LEFT JOIN ideas ON ideas.id=payments.idea_Id " \
            "WHERE users.id=%s"
    cursor.execute(query, (token_data.user_id,))
    result = cursor.fetchone()
    if result["unfinished_intent"] is not None:
        intent = stripe.PaymentIntent.retrieve(result["unfinished_intent"], )
        result["unfinished_intent_secret"] = intent["client_secret"]
    cursor.close()

    return result


@router.put("")
async def update_account(avatar: Optional[UploadFile] = File(None), username: str = Form(None), email: str = Form(None),
                         pass_hash: str = Form(None), token: str = Header(None, convert_underscores=False)):
    token_data = auth.verify_access_token(token)

    is_db_up()
    cursor = db.cursor(dictionary=True)
    result = {"status": "none changed"}
    if avatar is not None:
        if avatar.content_type not in CDN_ALLOWED_CONTENT_TYPES:
            raise HTTPException(status_code=406, detail="File type is not allowed for upload!")
        temp = await avatar.read()
        async with aiofiles.open(f'{CDN_FILES_PATH + "accounts/" + avatar.filename}',
                                 "wb") as directory:
            await directory.write(temp)
        file_id = hashlib.md5(temp).hexdigest()
        cursor.execute("INSERT INTO files(id, name, size, absolute_path, public_path, content_type)"
                       "VALUES(%s, %s, %s, %s, %s, %s)",
                       (file_id, avatar.filename, avatar.spool_max_size,
                        f'{CDN_FILES_PATH + "accounts/" + avatar.filename}',
                        f'{CDN_URL + "accounts/" + avatar.filename}', avatar.content_type))
        cursor.execute("UPDATE users SET avatar_id=%s WHERE id=%s", (file_id, token_data.user_id))
        result = {"status": "success"}
    if username is not None:
        cursor.execute("UPDATE users SET username=%s WHERE id=%s", (username, token_data.user_id))
        result = {"status": "success"}
        token_data.user = username
    if email is not None:
        cursor.execute("UPDATE users SET email=%s WHERE id=%s", (email, token_data.user_id))
        result = {"status": "success"}
    if pass_hash is not None:
        salt = auth.generate_salt()
        cursor.execute(
            "UPDATE users SET salt=%s, pass_hash=%s WHERE id=%s",
            (salt, auth.hash_password(pass_hash, salt), token_data.user_id)
        )
        result = {
            "token": auth.create_access_token(
                data={
                    "user": token_data.user,
                    "user_id": token_data.user_id
                }
            )
        }
    cursor.close()
    return result


@router.get("/verify-email", response_class=RedirectResponse)
async def verify_email_account(email: str):
    is_db_up()
    cursor = db.cursor(dictionary=True)
    cursor.execute("UPDATE users SET verified=TRUE WHERE email=%s", (email,))
    if cursor.rowcount == 0:
        raise UserNotFoundError
    cursor.close()
    return "http://localhost:3000/login"


@router.get("/ideas/bought")
async def get_ideas_bought_by_user(page: Optional[int] = 0, token: str = Header(None, convert_underscores=False)):
    load_count = 5
    token_data: AccessToken = auth.verify_access_token(token)

    is_db_up()
    cursor = db.cursor(dictionary=True)
    query = "SELECT ideas.*, " \
            "files.public_path AS image_url, " \
            "( SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id ) AS likes " \
            "FROM ideas " \
            "LEFT JOIN files ON ideas.id=files.id " \
            "WHERE buyer_id=%s ORDER BY date_bought DESC LIMIT %s, %s"
    cursor.execute(query, (token_data.user_id, page * load_count, (page + 1) * load_count))
    results = cursor.fetchall()
    for result in results:
        cursor.execute("SELECT category FROM ideas_categories WHERE idea_id=%s", (result["id"],))
        result["categories"] = list(map(lambda x: x["category"], cursor.fetchall()))
        cursor.execute("SELECT * FROM files WHERE idea_id=%s AND idea_id!=id", (result["id"],))
        result["files"] = list(cursor.fetchall())

    # Find the number of ideas matching the criteria
    query = "SELECT COUNT(*) AS ideas_count " \
            "FROM ideas " \
            "WHERE buyer_id=%s"
    cursor.execute(query, (token_data.user_id,))
    ideas_count = cursor.fetchone()["ideas_count"]

    # Calculate remaining ideas for endless scrolling feature
    if page == 0:
        ideas_left = ideas_count - len(results)
    else:
        ideas_left = ideas_count - (page * load_count + len(results))

    cursor.close()

    return {
        "countLeft": ideas_left,
        "ideas": results
    }


@router.get("/ideas/sold")
async def get_ideas_bought_by_user(page: Optional[int] = 0, token: str = Header(None, convert_underscores=False)):
    load_count = 5
    token_data: AccessToken = auth.verify_access_token(token)

    is_db_up()
    cursor = db.cursor(dictionary=True)
    query = "SELECT ideas.id, seller_id, title, price, date_publish, " \
            "files.public_path AS image_url, " \
            "( SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id ) AS likes, " \
            "( SELECT status FROM payouts WHERE idea_id=ideas.id ) AS payout_status " \
            "FROM ideas " \
            "LEFT JOIN files ON ideas.id=files.id " \
            "WHERE seller_id=%s AND buyer_id IS NOT NULL AND buyer_id != -1 " \
            "ORDER BY date_publish ASC LIMIT %s, %s"
    cursor.execute(query, (token_data.user_id, page * load_count, (page + 1) * load_count))
    results = cursor.fetchall()

    # Find the number of ideas matching the criteria
    query = "SELECT COUNT(*) AS ideas_count " \
            "FROM ideas " \
            "WHERE seller_id=%s AND buyer_id IS NOT NULL AND buyer_id != -1"
    cursor.execute(query, (token_data.user_id,))
    ideas_count = cursor.fetchone()["ideas_count"]

    # Calculate remaining ideas for endless scrolling feature
    if len(results) == 0:
        ideas_left = 0
    elif page == 0:
        ideas_left = ideas_count - len(results)
    else:
        ideas_left = ideas_count - (page * load_count + len(results))

    cursor.close()

    return {
        "countLeft": ideas_left,
        "ideas": results
    }


@router.put("/request-payout")
async def request_payout(idea_id: str, token: str = Header(None, convert_underscores=False)):
    auth.verify_access_token(token)
    if len(idea_id) != len(hashlib.md5().hexdigest()):
        raise IdeaIDInvalidError

    cursor = db.cursor(dictionary=True)
    cursor.execute("UPDATE payouts SET status='processing', date=CURRENT_TIMESTAMP() WHERE idea_id=%s", (idea_id,))
    cursor.close()

    return {"payoutStatus": "processing"}


@router.post("/request-password-reset")
async def request_password_reset(email: UserPasswordReset):
    is_db_up()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, first_name, CONCAT(first_name, ' ', last_name) AS name, username, email FROM users WHERE email=%s",
        (email.email,)
    )
    user = cursor.fetchone()
    if user is None:
        return ':('
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

    return ':)'


@router.put("/password-reset")
async def password_reset(new_data: UserPasswordUpdate, token: str = Header(None, convert_underscores=False)):
    token_data = auth.verify_password_reset_token(token)
    salt = auth.generate_salt()

    is_db_up()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "UPDATE users SET salt=%s, pass_hash=%s WHERE id=%s",
            (salt, auth.hash_password(new_data.pass_hash, salt), token_data.user_id,)
        )
    except mysql.connector.errors.Error as ex:
        cursor.close()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"msg": ex.__dict__})
    access_token = auth.create_access_token(
        data={
            "user": token_data.user,
            "user_id": token_data.user_id
        }
    )
    cursor.close()

    return {
        "accessToken": access_token,
        "expiresIn": JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        "authUserState": {
            "username": token_data.user
        }
    }


@router.on_event("shutdown")
async def shutdown_event():
    db.close()
