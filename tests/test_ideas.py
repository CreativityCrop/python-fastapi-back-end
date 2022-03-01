from fastapi.testclient import TestClient
import mysql
from app.routers import ideas
from app.responses.ideas import IdeasHottest, IdeasList
from app.config import DB_HOST, DB_USER, DB_PASS, DB_NAME

client = TestClient(ideas.router)

ideas.db = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASS,
    database=DB_NAME
)


def test_get_ideas():
    response = client.get("/ideas/get")
    assert response.status_code == 200
    # Check if data is in the right format
    assert IdeasList.parse_obj(response.json())


def test_hottest_ideas():
    response = client.get("/ideas/get-hottest")
    assert response.status_code == 200
    # Check if data is in the right format
    assert IdeasHottest.parse_obj(response.json())
