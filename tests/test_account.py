import pytest
import hashlib
from httpx import AsyncClient
from fastapi import HTTPException

from app.routers.account import router
from app.routers.auth import router as auth_router
from app.database import database
from app.responses.account import AccountData, BoughtIdeas, SoldIdeas, Invoice

token = str()


@pytest.mark.asyncio
async def test_account():
    await database.connect()
    async with AsyncClient(app=auth_router, base_url="http://test") as ac:
        response = await ac.post(
            "/auth/login",
            json={"username": "test", "pass_hash": hashlib.sha3_256("798XeLoup4".encode('utf-8')).hexdigest()}
        )
        global token
        token = response.json()["accessToken"]
    async with AsyncClient(app=router, base_url="http://test") as ac:
        response = await ac.get(
            "/account",
            headers={"Token": token}
        )
        assert response.status_code == 200
        # Check if data is in the right format
        assert AccountData.parse_obj(response.json())
    await database.disconnect()


@pytest.mark.asyncio
async def test_bought_ideas():
    await database.connect()
    async with AsyncClient(app=router, base_url="http://test") as ac:
        response = await ac.get(
            "/account/ideas/bought",
            headers={"Token": token}
        )
        assert response.status_code == 200
        # Check if data is in the right format
        assert BoughtIdeas.parse_obj(response.json())
    await database.disconnect()


@pytest.mark.asyncio
async def test_sold_ideas():
    await database.connect()
    async with AsyncClient(app=router, base_url="http://test") as ac:
        response = await ac.get(
            "/account/ideas/sold",
            headers={"Token": token}
        )
        assert response.status_code == 200
        # Check if data is in the right format
        assert SoldIdeas.parse_obj(response.json())
    await database.disconnect()


@pytest.mark.asyncio
async def test_invoice():
    await database.connect()
    async with AsyncClient(app=router, base_url="http://test") as ac:
        response = await ac.get(
            "/account/invoice/a1b16fef6370d3467406d695158192f0bd5023e4ce95a360761f172c771aa6dd",
            headers={"Token": token}
        )
        assert response.status_code == 200
        # Check if data is in the right format
        assert Invoice.parse_obj(response.json())
    await database.disconnect()
