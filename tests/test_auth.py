from fastapi.testclient import TestClient
from fastapi import HTTPException
import mysql
import hashlib
import pytest

from app.routers import auth
from app.responses.auth import TokenResponse
from app.models.token import AccessToken
from app.errors.auth import PasswordIncorrectError, UserNotFoundError, TokenNullError, TokenInvalidError, AccessTokenExpiredError
from app.config import DB_HOST, DB_USER, DB_PASS, DB_NAME

client = TestClient(auth.router)

auth.db = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASS,
    database=DB_NAME
)

token = str()


def test_login():
    data = {
        "username": "test",
        "pass_hash": hashlib.sha3_256("798XeLoup4".encode('utf-8')).hexdigest()
    }
    response = client.post("/auth/login", json=data)
    global token
    token = response.json()["accessToken"]

    assert response.status_code == 200
    # Check if data is in the right format
    assert TokenResponse.parse_obj(response.json())


def test_wrong_username():
    data = {
        "username": "test2",
        "pass_hash": hashlib.sha3_256("testtesttest".encode('utf-8')).hexdigest()
    }
    # Exception is expected
    with pytest.raises(HTTPException) as err:
        client.post("/auth/login", json=data)
    # Check if the right error is received
    assert err.typename is UserNotFoundError.__name__


def test_wrong_password():
    data = {
        "username": "test",
        "pass_hash": hashlib.sha3_256("wrong".encode('utf-8')).hexdigest()
    }
    # Exception is expected
    with pytest.raises(HTTPException) as err:
        client.post("/auth/login", json=data)
    # Check if the right error is received
    assert err.typename is PasswordIncorrectError.__name__


def test_token():
    response = client.get("/auth/verify", headers={
        "Token": token
    })
    assert response.status_code == 200
    # Check if data is in the right format
    assert AccessToken.parse_obj(response.json())


def test_empty_token():
    # Exception is expected
    with pytest.raises(HTTPException) as err:
        client.get("/auth/verify", headers={
            "Token": ""
        })
    # Check if the right error is received
    assert err.typename is TokenNullError.__name__


def test_invalid_token():
    # Exception is expected
    with pytest.raises(HTTPException) as err:
        client.get("/auth/verify", headers={
            "Token": "invalid"
        })
    # Check if the right error is received
    assert err.typename is TokenInvalidError.__name__


def test_expired_token():
    # Exception is expected
    with pytest.raises(HTTPException) as err:
        client.get("/auth/verify", headers={
            "Token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZ2VvcmdpIiwidXNlcl9pZCI6MiwiaXNzdWVyIjoiY3JlYXRp"
                     "dml0eWNyb3AudGVjaCIsImlzc3VlZCI6IjIwMjItMDItMjggMjE6MTE6MzUuNTkyMTM0IiwiZXhwaXJlcyI6IjIwMjItMDItM"
                     "jggMjI6MTE6MzUuNTkyMTUzIiwiZXhwIjoxNjQ2MDg2Mjk1fQ.JdF8uxZtwC2tlol_ty767HMjoK09jMOt1FeTl3kGB-o"
        })
    # Check if the right error is received
    assert err.typename is AccessTokenExpiredError.__name__
