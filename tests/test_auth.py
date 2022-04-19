import pytest
import hashlib
from httpx import AsyncClient
from fastapi import HTTPException

from app.routers.auth import router
from app.database import database
from app.responses.auth import TokenResponse
from app.models.token import AccessToken
from app.errors.auth import PasswordIncorrectError, UserNotFoundError, TokenNullError, TokenInvalidError, AccessTokenExpiredError

token = str()


@pytest.mark.asyncio
async def test_create_user():
    await database.connect()
    async with AsyncClient(app=router, base_url="http://test") as ac:
        response = await ac.post(
            "/auth/login",
            json={"username": "test", "pass_hash": hashlib.sha3_256("798XeLoup4".encode('utf-8')).hexdigest()}
        )
        assert response.status_code == 200
        # Check if data is in the right format
        assert TokenResponse.parse_obj(response.json())
        global token
        token = response.json()["accessToken"]
    await database.disconnect()


@pytest.mark.asyncio
async def test_wrong_username():
    await database.connect()
    async with AsyncClient(app=router, base_url="http://test") as ac:
        # Exception is expected
        with pytest.raises(HTTPException) as err:
            await ac.post(
                "/auth/login",
                json={"username": "test2", "pass_hash": hashlib.sha3_256("798XeLoup4".encode('utf-8')).hexdigest()}
            )
        # Check if the right error is received
        assert err.typename is UserNotFoundError.__name__
    await database.disconnect()


@pytest.mark.asyncio
async def test_wrong_password():
    await database.connect()
    async with AsyncClient(app=router, base_url="http://test") as ac:
        # Exception is expected
        with pytest.raises(HTTPException) as err:
            await ac.post(
                "/auth/login",
                json={"username": "test", "pass_hash": hashlib.sha3_256("wrong password".encode('utf-8')).hexdigest()}
            )
        # Check if the right error is received
        assert err.typename is PasswordIncorrectError.__name__
    await database.disconnect()


@pytest.mark.asyncio
async def test_token():
    await database.connect()
    async with AsyncClient(app=router, base_url="http://test") as ac:
        response = await ac.get(
            "/auth/verify",
            headers={"Token": token}
        )
        assert response.status_code == 200
        # Check if data is in the right format
        assert AccessToken.parse_obj(response.json())
    await database.disconnect()


@pytest.mark.asyncio
async def test_empty_token():
    await database.connect()
    async with AsyncClient(app=router, base_url="http://test") as ac:
        # Exception is expected
        with pytest.raises(HTTPException) as err:
            await ac.get(
                "/auth/verify",
                headers={"Token": ""}
            )
        # Check if the right error is received
        assert err.typename is TokenNullError.__name__
    await database.disconnect()


@pytest.mark.asyncio
async def test_invalid_token():
    await database.connect()
    async with AsyncClient(app=router, base_url="http://test") as ac:
        # Exception is expected
        with pytest.raises(HTTPException) as err:
            await ac.get(
                "/auth/verify",
                headers={"Token": "invalid"}
            )
        # Check if the right error is received
        assert err.typename is TokenInvalidError.__name__
    await database.disconnect()


@pytest.mark.asyncio
async def test_expired_token():
    await database.connect()
    async with AsyncClient(app=router, base_url="http://test") as ac:
        # Exception is expected
        with pytest.raises(HTTPException) as err:
            await ac.get(
                "/auth/verify",
                headers={
                    "Token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZ2VvcmdpIiwidXNlcl9pZCI6MiwiaXNzdWV"
                             "yIjoiY3JlYXRpdml0eWNyb3AudGVjaCIsImlzc3VlZCI6IjIwMjItMDItMjggMjE6MTE6MzUuNTkyMTM0Iiw"
                             "iZXhwaXJlcyI6IjIwMjItMDItMjggMjI6MTE6MzUuNTkyMTUzIiwiZXhwIjoxNjQ2MDg2Mjk1fQ.JdF8uxZt"
                             "wC2tlol_ty767HMjoK09jMOt1FeTl3kGB-o"
                }
            )
        # Check if the right error is received
        assert err.typename is AccessTokenExpiredError.__name__
    await database.disconnect()
