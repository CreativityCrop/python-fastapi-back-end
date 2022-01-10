import json
from datetime import datetime

import mysql.connector
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette import status

from app.models.user import UserRegister, UserLogin
from app.models.idea import IdeaPost
from app.models.token import AccessToken
from app.authentication import AuthService
from app.config import *
import hashlib


app = FastAPI()
auth = AuthService()

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
            salt, auth.hash_password(user.pass_hash, salt), datetime.now().isoformat())
    try:
        cursor.execute(query, data)
    except mysql.connector.errors.IntegrityError as ex:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ex.__dict__)
    cursor.close()
    db.commit()
    access_token = auth.create_access_token(
        data={
            "name": user.first_name + " " + user.last_name,
            "user": user.username
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
    query = 'SELECT * FROM users WHERE username LIKE %s'
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

    query = "UPDATE users SET date_login = %s WHERE users.username LIKE %s;"
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
    # print(token)
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
    query = "SELECT * FROM ideas WHERE id LIKE %s"
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
    query = "SELECT * FROM ideas ORDER BY date_publish DESC LIMIT %s, %s"
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
    id = hashlib.md5(idea.long_desc.encode()).hexdigest()
    cursor = db.cursor()
    query = "INSERT INTO ideas(id, seller_id, title, short_desc, long_desc, categories," \
            " date_publish, date_expiry, price) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    data = (id, token_data.user_id, idea.title, idea.short_desc, idea.long_desc,
            json.dumps(idea.categories), datetime.now().isoformat(), (datetime.now() + IDEA_EXPIRES_AFTER).isoformat(),
            idea.price)
    try:
        cursor.execute(query, data)
    except mysql.connector.errors.IntegrityError as ex:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ex.__dict__)
    cursor.close()
    db.commit()
    return id


@app.get("/", response_class=HTMLResponse)
async def read_root():
    return '<script>window.location.replace("http://creativitycrop.tech");</script>'


@app.on_event("shutdown")
async def shutdown_event():
    db.close()
