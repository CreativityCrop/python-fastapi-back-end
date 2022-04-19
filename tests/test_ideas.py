import pytest
import hashlib
from httpx import AsyncClient
from fastapi import HTTPException

from app.routers.ideas import router
from app.database import database
from app.responses.ideas import IdeasList, IdeasHottest


@pytest.mark.asyncio
async def test_get_ideas():
    await database.connect()
    async with AsyncClient(app=router, base_url="http://test") as ac:
        response = await ac.get("/ideas/get")
        assert response.status_code == 200
        # Check if data is in the right format
        assert IdeasList.parse_obj(response.json())
    await database.disconnect()


@pytest.mark.asyncio
async def test_hottest_ideas():
    await database.connect()
    async with AsyncClient(app=router, base_url="http://test") as ac:
        response = await ac.get("/ideas/get-hottest")
        assert response.status_code == 200
        # Check if data is in the right format
        assert IdeasHottest.parse_obj(response.json())
    await database.disconnect()
