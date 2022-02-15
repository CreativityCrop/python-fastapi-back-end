from fastapi import APIRouter, Depends

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.post("/")
async def update_admin(idk_param: str):
    return {"message": "Admin getting schwifty"}