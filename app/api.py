from fastapi import FastAPI, HTTPException, Header, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from starlette import status
from typing import Optional
from datetime import datetime

from app.models.user import UserRegister, UserLogin
from app.models.idea import IdeaPost
from app.models.token import AccessToken
from app.authentication import AuthService
from app.config import *

import stripe
from stripe.api_resources.payment_intent import PaymentIntent

import mysql.connector
import aiofiles as aiofiles
import hashlib

app = FastAPI()
auth = AuthService()
stripe.api_key = str(STRIPE_API_KEY)

origins = [
    "http://localhost:3000",
    "localhost:3000",
    "http://78.128.16.152:3000",
    "78.128.16.152:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # ["*"],  # ,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

db = mysql.connector.connect()


@app.on_event("startup")
async def startup_event():
    global db
    db = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )
    db.autocommit = True


@app.post("/api/auth/register")
async def register_user(user: UserRegister):
    salt = auth.generate_salt()
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor()
    query = "INSERT INTO users(first_name, last_name, email, username, salt, pass_hash, date_register) " \
            "VALUES(%s, %s, %s, %s, %s, %s, %s)"
    data = (user.first_name, user.last_name, user.email, user.username,
            salt, auth.hash_password(user.pass_hash, salt), datetime.now().isoformat(), user.username)
    try:
        cursor.execute(query, data)
    except mysql.connector.errors.IntegrityError as ex:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ex.__dict__)
    user_id = cursor.lastrowid
    cursor.close()
    access_token = auth.create_access_token(
        data={
            "user": user.username,
            "user_id": user_id
        }
    )
    return {
        "accessToken": access_token,
        "expiresIn": JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        "authUserState": {
            "firstName": user.first_name,
            "lastName": user.last_name,
            "username": user.username,
            "email": user.email
        }
    }


@app.post("/api/auth/login")
async def login_user(user: UserLogin):
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    query = 'SELECT * FROM users WHERE username = %s'
    cursor.execute(query, (user.username,))
    result = cursor.fetchone()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "msg": "Username is wrong or nonexistent", "errno": 101
        })
    if not auth.verify_password(user.pass_hash, result["salt"], result["pass_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "msg": "Password is wrong", "errno": 102
        })
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
    db.commit()
    return {
        "accessToken": access_token,
        "expiresIn": JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        "authUserState": {
            "username": user.username
        }
    }


@app.get("/api/auth/verify")
def verify_token(token: str = Header(None, convert_underscores=False)):
    return auth.verify_token(token)


@app.get("/api/ideas/get/{idea_id}")
async def get_idea_by_id(idea_id: str, token: str = Header(None, convert_underscores=False)):
    access_token = auth.verify_token(token)
    if len(idea_id) != len(hashlib.md5().hexdigest()):
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "msg": "ID validation failed, should be MD5 hash in hex format",
            "errno": 201
        })
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    query = "SELECT ideas.*, " \
            "(SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes, " \
            "files.public_path AS image_url " \
            "FROM ideas LEFT JOIN files ON ideas.id=files.id " \
            "WHERE ideas.id = %s"
    cursor.execute(query, (idea_id,))
    result = cursor.fetchone()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "msg": "The idea was not found",
            "errno": 202
        })
    if result["buyer_id"] is not None and result["buyer_id"] is not access_token.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={
            "msg": "The idea is not owned by the authenticated user",
            "errno": 203
        })
    cursor.execute("SELECT category FROM ideas_categories WHERE idea_id=%s", (result["id"],))
    result["categories"] = list(map(lambda x: x["category"], cursor.fetchall()))
    if result["buyer_id"] != access_token.user_id:
        del result["long_desc"]
    else:
        cursor.execute("SELECT * FROM files WHERE idea_id=%s AND idea_id!=id", (result["id"],))
        result["files"] = list(cursor.fetchall())
    # print(result)
    cursor.close()

    return result


@app.get("/api/ideas/get")
async def get_ideas(start: int = 0, end: int = 10, cat: Optional[str] = None):
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    query = "SELECT " \
            "ideas.id, seller_id, title, short_desc, date_publish, date_expiry, price, files.public_path AS image_url,"\
            "(SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes " \
            "FROM ideas LEFT JOIN files ON ideas.id=files.id " \
            "WHERE buyer_id IS NULL ORDER BY date_publish DESC LIMIT %s, %s "
    cursor.execute(query, (start, end))
    results = cursor.fetchall()
    for result in results:
        cursor.execute("SELECT category FROM ideas_categories WHERE idea_id=%s", (result["id"],))
        result["categories"] = list(map(lambda x: x["category"], cursor.fetchall()))
    cursor.close()
    if cat is not None:
        new_results = list()
        for result in results:
            if cat in result["categories"]:
                new_results.append(result)
        return new_results
    return results


@app.get("/api/ideas/get-hottest")
def get_hottest_ideas():
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    query = "SELECT ideas.id, ideas.title, files.public_path AS image_url, " \
            "(SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes " \
            "FROM ideas LEFT JOIN files ON ideas.id=files.id " \
            "WHERE buyer_id IS NULL ORDER BY likes DESC LIMIT 5"
    cursor.execute(query)
    return cursor.fetchall()


@app.post("/api/ideas/post")
async def post_idea(idea: IdeaPost, token: str = Header(None, convert_underscores=False)):
    token_data: AccessToken = auth.verify_token(token)
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        return ex.__dict__
    idea_id = hashlib.md5(idea.long_desc.encode()).hexdigest()
    cursor = db.cursor()
    query = "INSERT INTO ideas(id, seller_id, title, short_desc, long_desc, " \
            "date_publish, date_expiry, price) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)"
    data = (idea_id, token_data.user_id, idea.title, idea.short_desc, idea.long_desc, datetime.now().isoformat(),
            (datetime.now() + IDEA_EXPIRES_AFTER).isoformat(), idea.price)
    try:
        cursor.execute(query, data)
        for category in idea.categories:
            cursor.execute("INSERT INTO ideas_categories(idea_id, category) VALUES(%s, %s)", (idea_id, category))
    except mysql.connector.errors.IntegrityError as ex:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ex.__dict__)
    return idea_id


@app.put("/api/ideas/like")
async def like_idea(idea_id: str, token: str = Header(None, convert_underscores=False)):
    token_data = auth.verify_token(token)

    if len(idea_id) != len(hashlib.md5().hexdigest()):
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "msg": "ID validation failed, should be MD5 hash in hex format",
            "errno": 201
        })

    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("INSERT INTO ideas_likes(idea_id, user_id) VALUES(%s, %s)", (idea_id, token_data.user_id))
    except mysql.connector.IntegrityError:
        cursor.execute("DELETE FROM ideas_likes WHERE idea_id = %s AND user_id = %s", (idea_id, token_data.user_id))
    query = "SELECT COUNT(*) AS likes FROM ideas_likes WHERE idea_id = %s"
    cursor.execute(query, (idea_id,))
    likes = cursor.fetchone()
    cursor.close()
    if likes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "msg": "The idea was not found",
            "errno": 202
        })

    return likes


@app.get("/api/account")
async def get_account_details(token: str = Header(None, convert_underscores=False)):
    token_data: AccessToken = auth.verify_token(token)
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    query = "SELECT " \
            "users.*, files.public_path AS avatar_url " \
            "FROM users " \
            "LEFT JOIN files ON users.avatar_id=files.id " \
            "WHERE users.id=%s"
    cursor.execute(query, (token_data.user_id,))
    result = cursor.fetchone()
    cursor.close()
    return result


@app.get("/api/account/ideas/bought")
async def get_ideas_bought_by_user(start: int = 0, end: int = 5, token: str = Header(None, convert_underscores=False)):
    token_data: AccessToken = auth.verify_token(token)
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    query = "SELECT *, " \
            "files.public_path AS image_url, " \
            "( SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id ) AS likes FROM ideas " \
            "LEFT JOIN files ON ideas.id=files.id " \
            "WHERE buyer_id=%s ORDER BY date_publish DESC LIMIT %s, %s"
    cursor.execute(query, (token_data.user_id, start, end))
    results = cursor.fetchall()
    for result in results:
        cursor.execute("SELECT category FROM ideas_categories WHERE idea_id=%s", (result["id"],))
        result["categories"] = list(map(lambda x: x["category"], cursor.fetchall()))
        cursor.execute("SELECT * FROM files WHERE idea_id=%s AND idea_id!=id", (result["id"],))
        result["files"] = list(cursor.fetchall())
    cursor.close()
    return results


@app.get("/api/account/ideas/sold")
async def get_ideas_bought_by_user(start: int = 0, end: int = 5, token: str = Header(None, convert_underscores=False)):
    token_data: AccessToken = auth.verify_token(token)
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    query = "SELECT ideas.id, seller_id, title, price, date_publish, " \
            "files.public_path AS image_url, " \
            "( SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id ) AS likes FROM ideas " \
            "LEFT JOIN files ON ideas.id=files.id " \
            "WHERE seller_id=%s AND buyer_id IS NOT NULL ORDER BY date_publish ASC LIMIT %s, %s"
    cursor.execute(query, (token_data.user_id, start, end))
    results = cursor.fetchall()
    cursor.close()
    return results


@app.get("/api/payment/create")
async def create_payment(idea_id: str, token: str = Header(None, convert_underscores=False)):
    token_data: AccessToken = auth.verify_token(token)
    if len(idea_id) != len(hashlib.md5().hexdigest()):
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "msg": "ID validation failed, should be MD5 hash in hex format",
            "errno": 201
        })
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT ideas.price, ideas.title, ideas.buyer_id, users.id AS user_id, users.email "
                   "FROM ideas, users "
                   "WHERE ideas.id=%s AND users.id=%s",
                   (idea_id, token_data.user_id))
    idea = cursor.fetchone()
    if idea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "msg": "The idea was not found",
            "errno": 202
        })
    if idea["buyer_id"] is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={
            "msg": "The idea has been already sold",
            "errno": "MAKE A NEW ONE"
        })
    intent = stripe.PaymentIntent.create(
        amount=int(idea["price"]) * 100,
        # customer=result["id"],
        receipt_email=idea["email"],
        currency="usd",
        description="CreativityCrop - Selling the idea: " + idea["title"],
        metadata={
            "idea_id": idea_id,
            "user_id": token_data.user_id
        }

    )
    cursor.execute("INSERT INTO payments(id, amount, currency, idea_id, user_id, status) "
                   "VALUES(%s, %s, %s, %s, %s, %s)",
                   (intent["id"], intent["amount"], intent["currency"], idea_id, idea["user_id"], intent["status"]))
    # Make the buyer_id -1 to stop it from appearing in the list of ideas for sale
    cursor.execute("UPDATE ideas SET buyer_id=-1 WHERE id=%s", (idea_id,))
    cursor.close()
    return {
        "clientSecret": intent["client_secret"]
    }


@app.post("/api/payment/cancel")
async def delete_payment(payment_id: PaymentIntent):
    stripe.PaymentIntent.cancel(
        payment_id,
    )
    return stripe.PaymentIntent.list()


@app.post('/api/payment/webhook')
async def webhook_received(request: Request):
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = str(STRIPE_WEBHOOK_SECRET)
    try:
        event = stripe.Webhook.construct_event(await request.body(), sig_header, webhook_secret)
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ex.__dict__)
    except stripe.error.SignatureVerificationError:
        print("Signature invalid:")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"text": "Invalid signature"})

    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)

    if event['type'] == 'payment_intent.canceled':
        intent = event['data']['object']
    elif event['type'] == 'payment_intent.created':
        intent = event['data']['object']
    elif event['type'] == 'payment_intent.payment_failed':
        intent = event['data']['object']
    elif event['type'] == 'payment_intent.processing':
        intent = event['data']['object']
    elif event['type'] == 'payment_intent.requires_action':
        intent = event['data']['object']
    elif event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        cursor.execute(
            "UPDATE payments SET amount=%s, currency=%s, status=%s WHERE id=%s",
            (intent["amount"], intent["currency"], intent["status"], intent["id"])
        )
        cursor.execute(
            "UPDATE ideas SET buyer_id=%s WHERE id=%s",
            (intent["metadata"]["user_id"], intent["metadata"]["idea_id"])
        )
    else:
        print('Unhandled event type {}'.format(event['type']))

    cursor.close()
    return {'status': 'success'}


def get_folder_for_file(filetype):
    if filetype in CDN_DOCS_TYPES:
        return "docs/"
    elif filetype in CDN_MEDIA_TYPES:
        return "media/"
    elif filetype in CDN_IMAGE_TYPES:
        return "img/"
    else:
        raise TypeError


@app.post("/api/files/upload")
async def upload_file(idea_id: Optional[str] = None, files: list[UploadFile] = File(...),
                      token: str = Header(None, convert_underscores=False)):
    auth.verify_token(token)
    # TODO: File upload part
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    for file in files:
        if file.content_type not in CDN_ALLOWED_CONTENT_TYPES:
            raise HTTPException(status_code=406, detail="File type is not allowed for upload!")
        temp = await file.read()
        async with aiofiles.open(f'{CDN_FILES_PATH + get_folder_for_file(file.content_type) + file.filename}',
                                 "wb") as directory:
            await directory.write(temp)
        if file.filename == ("img-" + idea_id):
            file_id = idea_id
        else:
            file_id = hashlib.md5(temp).hexdigest()
        cursor.execute("INSERT INTO files(id, idea_id, name, size, absolute_path, public_path, content_type)"
                       "VALUES(%s, %s, %s, %s, %s, %s, %s)",
                       (file_id, idea_id, file.filename, file.spool_max_size,
                        f'{CDN_FILES_PATH + "/img/" + file.filename}',
                        f'{CDN_URL + "/img/" + file.filename}', file.content_type))
    cursor.close()
    db.commit()
    return


@app.get("/api/files/download")
async def download_file(file_id: str, token: str):
    auth.verify_token(token)
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM files WHERE id=%s", (file_id,))
    file = cursor.fetchone()
    cursor.close()
    return FileResponse(path=file["absolute_path"], filename=file["name"], media_type=file["content_type"])


@app.get("/", response_class=RedirectResponse)
async def read_root():
    return "https://creativitycrop.tech"


@app.on_event("shutdown")
async def shutdown_event():
    db.close()
