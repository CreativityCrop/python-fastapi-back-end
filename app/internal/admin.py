import asyncio
from websockets.exceptions import ConnectionClosedOK
from fastapi import APIRouter, WebSocket

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.post("/")
async def update_admin():
    return {"message": "Admin getting schwifty"}


# TODO: add authentication and maybe query for customizing the refresh period :)
@router.websocket("/admin/log")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Connection accepted")
    last_line = 0
    try:
        while True:
            file = open(file="./log.log", mode="r", encoding="utf-8")
            lines = file.readlines()
            if len(lines) > last_line:
                for i in range(last_line, len(lines)):
                    await websocket.send_text(lines[i].rstrip())
            last_line = len(lines)
            file.close()
            await asyncio.sleep(15)
    except ConnectionClosedOK:
        print("Connection closed by remote host")
        await websocket.close()
