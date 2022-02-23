from fastapi.testclient import TestClient

from app.routers.ideas import router
client = TestClient(router)


def test_read_item():
    response = client.get("/ideas/get-hottest")
    assert response.status_code == 200
