from fastapi.testclient import TestClient
import mysql
import hashlib

from app.routers import account, auth
from app.config import DB_HOST, DB_USER, DB_PASS, DB_NAME
from app.responses.account import AccountData, BoughtIdeas, SoldIdeas

client = TestClient(account.router)
login = TestClient(auth.router)


account.db = auth.db = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASS,
    database=DB_NAME
)

token = str()


def test_get_account():
    data = {
        "username": "test",
        "pass_hash": hashlib.sha3_256("testtesttest".encode('utf-8')).hexdigest()
    }
    token_request = login.post("/auth/login", json=data)
    global token
    token = token_request.json()["accessToken"]
    response = client.get("/account", headers={
        "Token": token
    })
    assert response.status_code == 200
    # Check if data is in the right format
    assert AccountData.parse_obj(response.json())


def test_bought_ideas():
    response = client.get("/account/ideas/bought", headers={
        "Token": token
    })
    assert response.status_code == 200
    # Check if data is in the right format
    assert BoughtIdeas.parse_obj(response.json())


def test_sold_ideas():
    response = client.get("/account/ideas/sold", headers={
        "Token": token
    })
    assert response.status_code == 200
    # Check if data is in the right format
    assert SoldIdeas.parse_obj(response.json())
