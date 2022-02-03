from datetime import timedelta

from starlette.config import Config
from starlette.datastructures import Secret

config = Config(".env")

PROJECT_NAME = "creativitycrop"
VERSION = "1.0.0"
API_PREFIX = "/api"

CDN_FILES_PATH = "/var/www/cdn/"
CDN_URL = "https://cdn.creativitycrop.tech/"

CDN_IMAGE_TYPES = [
    "image/svg+xml",
    "image/jpeg",
    "image/png"
]

CDN_MEDIA_TYPES = [
    "audio/mpeg",
    "video/mp4",
    "video/mpeg"
]

CDN_DOCS_TYPES = [
    "text/plain",
    "text/csv",
    "application/pdf",
    "application/json",
    "application/xml",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.rar",
    "application/zip"
]

CDN_ALLOWED_CONTENT_TYPES = CDN_IMAGE_TYPES + CDN_MEDIA_TYPES + CDN_DOCS_TYPES

STRIPE_API_KEY = config("STRIPE_API_KEY", cast=Secret, default='sk_test_51Jx4d2Ldhfi7be41P1vPbJ4zd47yIWOii662BD'
                                                               '9HIqUK14y3N8p57jbIt6sCKHNra0U1NzkAnZeaBUjHyZjRO'
                                                               'Yg300EhrWWoMB')
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", cast=Secret, default='whsec_B6yQ4rfFnE5SkgTf00D0DRFpzUmiTJXB')

MAILGUN_API_KEY = config("MAILGUN_API_KEY", cast=Secret, default='1ee6e3467a7a34b28f3c83ddd25276a9-ef80054a-64608b0b')

SUPER_USERS = config("SUPER_USERS", cast=set, default={"georgi", "zorry"})

# Database properties
DB_HOST = 'creativitycrop.tech'
DB_USER = 'creativity_crop'
DB_PASS = 'qO4n3BPtA4MgStJW'
DB_NAME = 'creativity_crop'

DB_CLEANUP_INTERVAL = config("DB_CLEANUP_INTERVAL", default=timedelta(minutes=5))

IDEA_EXPIRES_AFTER = config("IDEA_EXPIRES_AFTER", default=timedelta(days=31))

# JWT creation properties
JWT_SECRET_KEY = config("JWT_SECRET_KEY", cast=Secret,
                        default="7414c6300dee0ca7e6dfac035501b5a20153292b0d70052d9383d360acdaf11d")

JWT_PASSWORD_RESET_SECRET_KEY = config("JWT_PASSWORD_RESET_SECRET_KEY", cast=Secret,
                                       default="0ddf5597e02d981f8803c4cc11f015a4e52679d706edb29b595d9e466def5bcf")

JWT_ACCESS_TOKEN_EXPIRE_MINUTES = config(
    "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    cast=int,
    default=60  # one hour
)

JWT_PASSWORD_RESET_EXPIRE_MINUTES = config(
    "JWT_PASSWORD_RESET_EXPIRE_MINUTES",
    cast=int,
    default=5  # one hour
)

JWT_ALGORITHM = config("JWT_ALGORITHM", cast=str, default="HS256")
JWT_AUDIENCE = config("JWT_AUDIENCE", cast=str, default="creativitycrop")
JWT_TOKEN_PREFIX = config("JWT_TOKEN_PREFIX", cast=str, default="Bearer")
