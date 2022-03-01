from fastapi.testclient import TestClient
from fastapi import HTTPException
import mysql
import hashlib
import pytest

from app.routers import files, auth
from app.config import DB_HOST, DB_USER, DB_PASS, DB_NAME
from app.errors.files import FileAccessDeniedError

client = TestClient(files.router)
login = TestClient(auth.router)

files.db = auth.db = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASS,
    database=DB_NAME
)


def test_file_access_denied():
    login_data = {
        "username": "test",
        "pass_hash": hashlib.sha3_256("testtesttest".encode('utf-8')).hexdigest()
    }
    token_request = login.post("/auth/login", json=login_data)
    data = {
        "file_id": "2381249de63c9a261fd08a161290ed1f4ba0f3ec4f1e64e1cff61f5d11b8927b",
        "token": token_request.json()["accessToken"]
    }
    # Exception is expected
    with pytest.raises(HTTPException) as err:
        client.get("/files/download", params=data)
    # Check if the right error is received
    assert err.typename is FileAccessDeniedError.__name__
