import json

from fastapi import FastAPI, HTTPException, Header, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from starlette import status
from typing import Optional
from datetime import datetime
import threading
import requests

from app.models.user import UserRegister, UserLogin
from app.models.idea import IdeaPost
from app.models.token import AccessToken
from app.authentication import AuthService
from app.config import *

import stripe

import mysql.connector
import aiofiles as aiofiles
import hashlib

app = FastAPI()
auth = AuthService()
stripe.api_key = str(STRIPE_API_KEY)

# Origins for CORS
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


def is_db_up():
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    return True


# Event that set-ups the application for startup
@app.on_event("startup")
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


@app.post("/api/auth/register")
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
    is_db_up()
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
    # This checks if idea id is in the right format, i.e. MD5 hash
    if len(idea_id) != len(hashlib.md5().hexdigest()):
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "msg": "ID validation failed, should be MD5 hash in hex format",
            "errno": 201
        })
    is_db_up()
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
    # Fetch categories separately cos they are in different table
    cursor.execute("SELECT category FROM ideas_categories WHERE idea_id=%s", (result["id"],))
    result["categories"] = list(map(lambda x: x["category"], cursor.fetchall()))
    # Check if the user is the owner of the idea, then fetch the files
    if result["buyer_id"] != access_token.user_id:
        del result["long_desc"]
    else:
        cursor.execute("SELECT * FROM files WHERE idea_id=%s AND idea_id!=id", (result["id"],))
        result["files"] = list(cursor.fetchall())
    # print(result)
    cursor.close()

    return result


# This is a worker method that is run in a separate thread to check for expired payments every N minutes
worker_next_run = datetime(1970, 1, 1)


def cleanup_database():
    # Set variable to keep next run time
    global worker_next_run
    worker_next_run = datetime.now() + DB_CLEANUP_INTERVAL
    print("Starting DB cleanup process")

    second_db = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )
    second_db.autocommit = True
    cursor = second_db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM payments "
                   "WHERE status!='succeeded' AND date < DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 MINUTE)")
    payments = cursor.fetchall()
    for payment in payments:
        cursor.execute("UPDATE ideas SET buyer_id = NULL WHERE id=%s", (payment["idea_id"],))
        stripe.PaymentIntent.cancel(
            stripe.PaymentIntent(payment["id"])
        )
        cursor.execute("DELETE FROM payments WHERE id = %s", (payment["id"],))
    cursor.close()
    second_db.close()
    print("DB cleaning process is completed!")


worker = threading.Thread(target=cleanup_database, args=())


@app.get("/api/ideas/get")
async def get_ideas(page: Optional[int] = 0, cat: Optional[str] = "%"):
    is_db_up()

    # Worker to clean up database
    global worker
    global worker_next_run
    if worker_next_run == datetime(1970, 1, 1):
        # First run for worker
        worker.start()
    elif worker.is_alive() is False and datetime.now() > worker_next_run:
        # Worker has died and it is time to start again
        worker = threading.Thread(target=cleanup_database, args=())
        worker.start()

    cursor = db.cursor(dictionary=True)

    query = "SELECT " \
            "ideas.id, seller_id, title, short_desc, date_publish, date_expiry, price, files.public_path AS image_url,"\
            "(SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes " \
            "FROM ideas LEFT JOIN files ON ideas.id=files.id " \
            "WHERE buyer_id IS NULL AND " \
            "ideas.id IN (SELECT idea_id FROM ideas_categories WHERE category LIKE %s) " \
            "ORDER BY date_publish DESC LIMIT %s, %s "
    cursor.execute(
        query, (cat, page * 10, (page + 1) * 10)
    )
    results = cursor.fetchall()

    # Check if there are results, don't waste time to continue if not
    if len(results) == 0:
        return {"countLeft": 0, "ideas": []}

    # Get categories in ia neat array
    for result in results:
        cursor.execute("SELECT category FROM ideas_categories WHERE idea_id=%s", (result["id"],))
        result["categories"] = list(map(lambda x: x["category"], cursor.fetchall()))

    # Find the number of ideas matching the criteria
    query = "SELECT COUNT(*) AS ideas_count " \
            "FROM ideas " \
            "WHERE ideas.buyer_id IS NULL AND " \
            "ideas.id IN (SELECT idea_id FROM ideas_categories WHERE category LIKE %s)"
    cursor.execute(query, (cat,))
    ideas_count = cursor.fetchone()["ideas_count"]

    # Calculate remaining ideas for endless scrolling feature
    if page == 0:
        ideas_left = ideas_count - len(results)
    else:
        ideas_left = ideas_count - (page * 10 + len(results))

    cursor.close()

    return {
        "countLeft": ideas_left,
        "ideas": results
    }


@app.get("/api/ideas/get-hottest")
def get_hottest_ideas():
    is_db_up()

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
    is_db_up()

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

    # This checks if idea id is in the right format, i.e. MD5 hash
    if len(idea_id) != len(hashlib.md5().hexdigest()):
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "msg": "ID validation failed, should be MD5 hash in hex format",
            "errno": 201
        })

    is_db_up()

    cursor = db.cursor(dictionary=True)
    # Try to insert a like row in the table, if a duplication error is thrown, delete the like
    try:
        cursor.execute("INSERT INTO ideas_likes(idea_id, user_id) VALUES(%s, %s)", (idea_id, token_data.user_id))
    except mysql.connector.IntegrityError:
        cursor.execute("DELETE FROM ideas_likes WHERE idea_id = %s AND user_id = %s", (idea_id, token_data.user_id))
    # Get the number of likes
    query = "SELECT " \
            "COUNT(*) AS likes, " \
            "((SELECT COUNT(*) FROM ideas_likes WHERE idea_id=%s AND user_id=%s) = 1) AS is_liked " \
            "FROM ideas_likes WHERE idea_id = %s"
    cursor.execute(query, (idea_id, token_data.user_id, idea_id))
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
    is_db_up()

    cursor = db.cursor(dictionary=True)
    query = "SELECT " \
            "users.*, files.public_path AS avatar_url, " \
            "payments.id AS unfinished_intent, payments.idea_id AS unfinished_payment_idea, " \
            "ideas.title, ideas.short_desc, ideas.price, " \
            "(SELECT files.public_path FROM files WHERE files.id=payments.idea_id ) AS idea_img " \
            "FROM users " \
            "LEFT JOIN files ON users.avatar_id=files.id " \
            "LEFT JOIN payments ON users.id=payments.user_id AND payments.status != 'succeeded' " \
            "LEFT JOIN ideas ON ideas.id=payments.idea_Id " \
            "WHERE users.id=%s"
    cursor.execute(query, (token_data.user_id,))
    result = cursor.fetchone()
    if result["unfinished_intent"] is not None:
        intent = stripe.PaymentIntent.retrieve(result["unfinished_intent"], )
        result["unfinished_intent_secret"] = intent["client_secret"]
    cursor.close()

    return result


@app.get("/api/account/ideas/bought")
async def get_ideas_bought_by_user(start: int = 0, end: int = 5, token: str = Header(None, convert_underscores=False)):
    token_data: AccessToken = auth.verify_token(token)
    is_db_up()

    cursor = db.cursor(dictionary=True)
    query = "SELECT ideas.*, " \
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
    is_db_up()

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
    # Check if idea id is valid MD5 hash
    if len(idea_id) != len(hashlib.md5().hexdigest()):
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "msg": "ID validation failed, should be MD5 hash in hex format",
            "errno": 201
        })
    is_db_up()

    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT "
                   "(SELECT COUNT(*) FROM payments WHERE idea_id=%s) AS idea_count, "
                   "(SELECT COUNT(*) FROM payments WHERE user_id=%s AND status != 'succeeded') AS user_count",
                   (idea_id, token_data.user_id)
                   )
    check = cursor.fetchone()
    if check["idea_count"] != 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "msg": "This idea is already sold or in process of buying!",
            "errno": "new one pls"
        })
    if check["user_count"] != 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "msg": "Finish the previous payment and then start a new one!",
            "errno": "new one again"
        })

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
        amount=int(idea["price"] * 100),
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
async def delete_payment(intent_id: str):
    stripe.PaymentIntent.cancel(
        stripe.PaymentIntent(intent_id)
    )
    return stripe.PaymentIntent.list()


@app.get("/api/payment/get")
def get_payment(token: str = Header(None, convert_underscores=False)):
    token_data = auth.verify_token(token)
    is_db_up()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id FROM payments WHERE user_id=%s", (token_data.user_id,))
    result = cursor.fetchone()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "msg": "Payment not found",
            "errno": "Make up a new one pls"
        })
    intent = stripe.PaymentIntent.retrieve(result["id"], )

    cursor.close()

    return intent["client_secret"]


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

    is_db_up()
    cursor = db.cursor(dictionary=True)
    intent = {}
    if event['type'] == 'payment_intent.canceled':
        intent = event['data']['object']
    elif event['type'] == 'payment_intent.payment_failed':
        intent = event['data']['object']
    elif event['type'] == 'payment_intent.processing':
        intent = event['data']['object']
    elif event['type'] == 'payment_intent.requires_action':
        intent = event['data']['object']
    elif event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
    else:
        print('Unhandled event type {}'.format(event['type']))
    cursor.execute(
        "UPDATE payments SET amount=%s, currency=%s, status=%s WHERE id=%s",
        (intent["amount"], intent["currency"], intent["status"], intent["id"])
    )
    if intent["status"] == "succeeded":
        cursor.execute(
            "UPDATE ideas SET buyer_id=%s WHERE id=%s",
            (intent["metadata"]["user_id"], intent["metadata"]["idea_id"])
        )
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
    is_db_up()
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
                        f'{CDN_FILES_PATH + get_folder_for_file(file.content_type) + file.filename}',
                        f'{CDN_URL + get_folder_for_file(file.content_type) + file.filename}', file.content_type))
    cursor.close()
    db.commit()

    return


@app.get("/api/files/download")
async def download_file(file_id: str, token: str):
    auth.verify_token(token)

    is_db_up()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM files WHERE id=%s", (file_id,))
    file = cursor.fetchone()
    cursor.close()

    return FileResponse(path=file["absolute_path"], filename=file["name"], media_type=file["content_type"])


@app.get("/api/account/forgotten-password")
async def reset_password(token: str = Header(None, convert_underscores=False)):
    token_data = auth.verify_token(token)

    is_db_up()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT first_name, last_name, username, email FROM users WHERE id=%s", (token_data.user_id,))
    user = cursor.fetchone()

    password_reset_token = ""
    requests.post(
        "https://api.eu.mailgun.net/v3/app.creativitycrop.tech/messages",
        auth=("api", str(MAILGUN_API_KEY)),
        data={
            "from": "Friendly Bot from CreativityCrop <no-reply@app.creativitycrop.tech>",
            "to": [user["email"], "test-4i51cm213@srv1.mail-tester.com"],
            "subject": "CreativityCrop - Account Password Recovery  ",
            "template": "password-recovery",
            'h:X-Mailgun-Variables': json.dumps({
                "user_name": user["first_name"],
                "password_token": password_reset_token,
                "current_year": datetime.now().year
            })
        }
    )
    return ':)'


@app.get("/", response_class=RedirectResponse)
async def read_root():
    return "https://creativitycrop.tech"


@app.on_event("shutdown")
async def shutdown_event():
    db.close()
