from datetime import timedelta

from starlette.config import Config
from starlette.datastructures import Secret

config = Config(".env")

PROJECT_NAME = "creativitycrop"
VERSION = "1.0.0"
API_PREFIX = "/api"

CDN_FILES_PATH = "/var/www/cdn"
CDN_URL = "https://cdn.creativitycrop.tech/"
CDN_ALLOWED_CONTENT_TYPES = [
    "text/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/json",
    "audio/mpeg",
    "video/mp4",
    "video/mpeg",
    "image/png",
    "application/pdf",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.rar",
    "image/svg+xml",
    "text/plain",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/xml"
]

STRIPE_API_KEY = config("STRIPE_API_KEY", cast=Secret, default='sk_test_51Jx4d2Ldhfi7be41P1vPbJ4zd47yIWOii662BD'
                                                               '9HIqUK14y3N8p57jbIt6sCKHNra0U1NzkAnZeaBUjHyZjRO'
                                                               'Yg300EhrWWoMB')

SUPER_USERS = config("SUPER_USERS", cast=set, default={"georgi", "zorry"})

# Database properties
DB_HOST = 'creativitycrop.tech'
DB_USER = 'creativity_crop'
DB_PASS = 'qO4n3BPtA4MgStJW'
DB_NAME = 'creativity_crop'

IDEA_EXPIRES_AFTER = config("IDEA_EXPIRES_AFTER", default=timedelta(days=31))

# JWT creationg properties
JWT_SECRET_KEY = config("JWT_SECRET_KEY", cast=Secret,
                        default="7414c6300dee0ca7e6dfac035501b5a20153292b0d70052d9383d360acdaf11d")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = config(
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    cast=int,
    default=60  # one hour
)
JWT_ALGORITHM = config("JWT_ALGORITHM", cast=str, default="HS256")
JWT_AUDIENCE = config("JWT_AUDIENCE", cast=str, default="creativitycrop")
JWT_TOKEN_PREFIX = config("JWT_TOKEN_PREFIX", cast=str, default="Bearer")
