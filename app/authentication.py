from jose import JWTError, jwt, ExpiredSignatureError
import bcrypt
from passlib.context import CryptContext
from datetime import datetime

from app.config import *
from app.errors.auth import TokenInvalidError, TokenNullError, AccessTokenExpiredError
from app.models.token import *

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_salt() -> str:
    return bcrypt.gensalt().decode()


def hash_password(password: str, salt: str) -> str:
    return pwd_context.hash(password + salt)


def verify_password(password: str, salt: str, hashed_pw: str) -> bool:
    return pwd_context.verify(password + salt, hashed_pw)


def create_access_token(data: AccessToken):
    data.issued = (datetime.utcnow()).__str__()
    data.expires = (datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)).__str__()
    data.exp = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(data.dict(), str(JWT_AUTH_SECRET_KEY), algorithm=JWT_ALGORITHM)


def verify_access_token(token: str) -> AccessToken:
    if token is None or token == "":
        raise TokenNullError
    try:
        payload = jwt.decode(token, str(JWT_AUTH_SECRET_KEY), algorithms=[JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise AccessTokenExpiredError
    except JWTError:
        raise TokenInvalidError
    except AttributeError:
        raise TokenInvalidError
    return AccessToken.parse_obj(payload)


def create_email_verify_token(data: EmailVerifyToken) -> str:
    expire = datetime.utcnow() + timedelta(minutes=JWT_EMAIL_VERIFY_EXPIRE_MINUTES)
    data.exp = expire
    return jwt.encode(data.dict(), str(JWT_EMAIL_VERIFY_SECRET_KEY), algorithm=JWT_ALGORITHM)


def verify_email_verify_token(token: str) -> EmailVerifyToken:
    if token is None or token == "":
        raise TokenNullError
    try:
        payload = jwt.decode(token, str(JWT_EMAIL_VERIFY_SECRET_KEY), algorithms=[JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise EmailVerifyToken
    except JWTError:
        raise TokenInvalidError
    except AttributeError:
        raise TokenInvalidError
    return EmailVerifyToken.parse_obj(payload)


def create_password_reset_token(data: PasswordResetToken) -> str:
    expire = datetime.utcnow() + timedelta(minutes=JWT_PASSWORD_RESET_EXPIRE_MINUTES)
    data.exp = expire
    return jwt.encode(data.dict(), str(JWT_PASSWORD_RESET_SECRET_KEY), algorithm=JWT_ALGORITHM)


def verify_password_reset_token(token: str) -> PasswordResetToken:
    if token is None or token == "":
        raise TokenNullError
    try:
        payload = jwt.decode(token, str(JWT_PASSWORD_RESET_SECRET_KEY), algorithms=[JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise PasswordResetToken
    except JWTError:
        raise TokenInvalidError
    except AttributeError:
        raise TokenInvalidError
    return PasswordResetToken.parse_obj(payload)
