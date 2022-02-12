from fastapi import APIRouter, Depends
from ..dependencies import get_token_header

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_token_header)]
)


@router.post("/")
async def update_admin(idk_param: str):
    return {"message": "Admin getting schwifty"}