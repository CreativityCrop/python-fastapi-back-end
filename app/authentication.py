from datetime import datetime

from fastapi import HTTPException
from passlib.context import CryptContext
from starlette import status

import bcrypt
from jose import JWTError, jwt

from app.config import *
from app.models.errors import TokenInvalidError
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
    try:
        payload = jwt.decode(token, str(JWT_AUTH_SECRET_KEY), algorithms=[JWT_ALGORITHM])
    except JWTError as ex:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"msg": ex.__str__(), "errno": 103})
    except AttributeError:
        raise TokenInvalidError
    return AccessToken.parse_obj(payload)


def create_email_verify_token(data: EmailVerifyToken) -> str:
    expire = datetime.utcnow() + timedelta(minutes=JWT_EMAIL_VERIFY_EXPIRE_MINUTES)
    data.exp = expire
    return jwt.encode(data.dict(), str(JWT_EMAIL_VERIFY_SECRET_KEY), algorithm=JWT_ALGORITHM)


def verify_email_verify_token(token: str) -> EmailVerifyToken:
    try:
        payload = jwt.decode(token, str(JWT_EMAIL_VERIFY_SECRET_KEY), algorithms=[JWT_ALGORITHM])
    except JWTError as ex:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"msg": ex.__str__(), "errno": 103})
    except AttributeError:
        raise TokenInvalidError
    return EmailVerifyToken.parse_obj(payload)


def create_password_reset_token(data: PasswordResetToken) -> str:
    expire = datetime.utcnow() + timedelta(minutes=JWT_PASSWORD_RESET_EXPIRE_MINUTES)
    data.exp = expire
    return jwt.encode(data.dict(), str(JWT_PASSWORD_RESET_SECRET_KEY), algorithm=JWT_ALGORITHM)


def verify_password_reset_token(token: str) -> PasswordResetToken:
    try:
        payload = jwt.decode(token, str(JWT_PASSWORD_RESET_SECRET_KEY), algorithms=[JWT_ALGORITHM])
    except JWTError as ex:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"msg": ex.__str__(), "errno": 103})
    except AttributeError:
        raise TokenInvalidError
    return PasswordResetToken.parse_obj(payload)
