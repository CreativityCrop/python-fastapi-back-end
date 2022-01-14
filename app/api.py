import json
from datetime import datetime
import mysql.connector
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette import status
from stripe.api_resources.payment_intent import PaymentIntent

from app.models.user import UserRegister, UserLogin
from app.models.idea import IdeaPost
from app.models.token import AccessToken
from app.authentication import AuthService
from app.config import *
import hashlib
import stripe

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
    user_id = result["id"]

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
            "msg": "Username is wrong or nonexistent", "errno": 101
        })
    if not auth.verify_password(user.pass_hash, result["salt"], result["pass_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "msg": "Password is wrong", "errno": 102
        })

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
    query = "SELECT * FROM ideas WHERE id = %s"
    cursor.execute(query, (idea_id,))
    result = cursor.fetchone()
    # print(result)
    cursor.close()
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

    return result


@app.get("/api/ideas/get")
async def get_ideas(start: int = 0, end: int = 10):
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    query = "SELECT *, (SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id) AS likes FROM ideas " \
            "WHERE buyer_id IS NULL ORDER BY date_publish DESC LIMIT %s, %s"
    cursor.execute(query, (start, end))
    results = cursor.fetchall()
    return results


@app.post("/api/ideas/post")
async def post_idea(idea: IdeaPost, token: str = Header(None, convert_underscores=False)):
    token_data: AccessToken = auth.verify_token(token)
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        return ex.__dict__
    idea_id = hashlib.md5(idea.long_desc.encode()).hexdigest()
    cursor = db.cursor()
    query = "INSERT INTO ideas(id, seller_id, title, short_desc, long_desc, categories," \
            " date_publish, date_expiry, price) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    data = (idea_id, token_data.user_id, idea.title, idea.short_desc, idea.long_desc,
            json.dumps(idea.categories), datetime.now().isoformat(), (datetime.now() + IDEA_EXPIRES_AFTER).isoformat(),
            idea.price)
    try:
        cursor.execute(query, data)
    except mysql.connector.errors.IntegrityError as ex:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ex.__dict__)
    cursor.close()
    db.commit()
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


@app.get("/api/account/ideas/bought")
async def get_ideas_bought_by_user(token: str = Header(None, convert_underscores=False)):
    token_data: AccessToken = auth.verify_token(token)
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    query = "SELECT *, ( SELECT COUNT(*) FROM ideas_likes WHERE idea_id=ideas.id ) AS likes FROM ideas " \
            "WHERE buyer_id=%s ORDER BY date_publish DESC"
    cursor.execute(query, (token_data.user_id,))
    results = cursor.fetchall()
    return results


@app.get("/api/account/ideas/sold")
async def get_ideas_bought_by_user(token: str = Header(None, convert_underscores=False)):
    token_data: AccessToken = auth.verify_token(token)
    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    query = "SELECT id, seller_id, title, price, date_publish, likes FROM ideas " \
            "WHERE seller_id=%s ORDER BY date_publish ASC"
    cursor.execute(query, (token_data.user_id,))
    results = cursor.fetchall()
    return results


@app.get("/api/payment/create")
async def create_payment(idea_id: str, token: str = Header(None, convert_underscores=False)):
    token_data: AccessToken = auth.verify_token(token)

    try:
        db.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.errors.InterfaceError as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=ex.__dict__)
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT ideas.price, user.id, user.email FROM ideas, users WHERE ideas.id=%s AND users.id=%s",
                   (idea_id, token_data.user_id))
    result = cursor.fetchone()
    intent = stripe.PaymentIntent.create(
        amount=result["price"],
        customer=result["id"],
        receipt_email=result["email"],
        currency='usd',
    )
    return {
        'clientSecret': intent['client_secret']
    }


@app.post("/api/payment/cancel")
async def delete_payment(payment_id: PaymentIntent):
    stripe.PaymentIntent.cancel(
        payment_id,
    )


@app.get("/", response_class=HTMLResponse)
async def read_root():
    return '<script>window.location.replace("http://creativitycrop.tech");</script>'


@app.on_event("shutdown")
async def shutdown_event():
    db.close()
