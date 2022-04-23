from fastapi import APIRouter, WebSocket, Query, Depends
from websockets.exceptions import ConnectionClosedOK
import asyncio

from app.config import SUPER_USERS
from app.internal.dependencies import verify_admin_user
from app.authentication import verify_access_token
from app.models.token import AccessToken
from app.errors.auth import TokenInvalidError, TokenNullError, AccessTokenExpiredError

from app.internal.routers import ideas, users, payouts


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin_user)],
    include_in_schema=False
)

router.include_router(ideas.router)
router.include_router(users.router)
router.include_router(payouts.router)


# TODO: add authentication and maybe query for customizing the refresh period :)
@router.websocket("/log")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    async def check_token():
        try:
            token_data = verify_access_token(token)
        except AccessTokenExpiredError:
            await websocket.send_json({"Error": "Your token has expired!"})
            await websocket.close()
            return
        except TokenInvalidError:
            await websocket.send_json({"Error": "Your token is invalid!"})
            await websocket.close()
            return
        except TokenNullError:
            await websocket.send_json({"Error": "Your token is null!!"})
            await websocket.close()
            return
        if token_data.user not in SUPER_USERS:
            await websocket.send_json({"Error": "You aren't allowed to view this content!"})
            await websocket.close()
            return

    async def send_data(temp):
        while str(websocket.client_state) == 'WebSocketState.CONNECTED':
            try:
                file = open(file="./app.log", mode="r", encoding="ascii")
                lines = file.readlines()
                if len(lines) > temp:
                    for i in range(temp, len(lines)):
                        await websocket.send_text(lines[i].rstrip())
                temp = len(lines)
                file.close()
                await asyncio.sleep(1)
            except FileNotFoundError:
                print("Log file not found")
                await websocket.send_json({"Error": "Log file was not found :(!"})
                await websocket.close()
                return

    async def watch_status():
        while str(websocket.client_state) == 'WebSocketState.CONNECTED':
            await websocket.receive()

    await websocket.accept()
    await check_token()
    last_line = 0
    print("Connection accepted from " + websocket.client.host)

    await asyncio.gather(watch_status(), send_data(last_line))

