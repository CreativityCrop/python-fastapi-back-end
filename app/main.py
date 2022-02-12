from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

from app.routers import auth, account, ideas, files, payment
from app.internal import admin

app = FastAPI(
    title="CreativityCrop API",
    description="""
    This is the long overview of our project!
    """,
    terms_of_service="https://creativitycrop.tech/terms-conditions",
    contact={
        "name": "Zorry or Georgi",
        "url": "https://creativitycrop.tech/about-us",
        "email": "contact@creativitycrop.tech",
    },
    license_info={
        "name": "GNU GPL v3",
        "url": "https://www.gnu.org/licenses/gpl-3.0.html"
    },
    dependencies=[],
    root_path="/api",
    servers=[{"url": "/api"}],
)

app.include_router(auth.router)
app.include_router(account.router)
app.include_router(ideas.router)
app.include_router(files.router)
app.include_router(payment.router)
app.include_router(admin.router)

# Origins for CORS
origins = [
    "http://localhost:3000",
    "localhost:3000",
    "http://78.128.16.152:3000",
    "78.128.16.152:3000",
    "http://creativitycrop.tech",
    "https://creativitycrop.tech",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # ["*"],  # ,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]

)


@app.get("/", response_class=RedirectResponse)
async def read_root():
    return "https://creativitycrop.tech"
