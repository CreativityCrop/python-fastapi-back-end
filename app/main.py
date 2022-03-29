from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

from app.routers import auth, account, ideas, files, payment
from app.internal import admin
from app.database import database

app = FastAPI(
    title="CreativityCrop API",
    description='Platform for sharing and monetising ideas!',
    terms_of_service="https://creativitycrop.tech/terms-conditions",
    contact={
        "name": "Contact",
        "url": "https://creativitycrop.tech/about-us",
        "email": "contact@creativitycrop.tech",
    },
    license_info={
        "name": "GNU GPL v3",
        "url": "https://www.gnu.org/licenses/gpl-3.0.html"
    },
    root_path="/api",
    servers=[{"url": "/api"}],
)

# Adding routers to FastAPI instance
app.include_router(auth.router)
app.include_router(account.router)
app.include_router(ideas.router)
app.include_router(files.router)
app.include_router(payment.router)
app.include_router(admin.router)

# Origins for CORS
origins = [
    "http://localhost:3000",
    "http://creativitycrop.tech",
    "https://creativitycrop.tech"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]

)


@app.on_event("startup")
async def app_startup():
    await database.connect()


@app.on_event("shutdown")
async def app_shutdown():
    await database.disconnect()


# Root route redirects to main page
@app.get("/", response_class=RedirectResponse)
async def read_root():
    return "https://creativitycrop.tech"
