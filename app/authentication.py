from fastapi import HTTPException
from passlib.context import CryptContext
from starlette import status

import bcrypt
from jose import JWTError, jwt

from app.config import *
from app.models.token import *

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_salt() -> str:
    return bcrypt.gensalt().decode()


def hash_password(password: str, salt: str) -> str:
    return pwd_context.hash(password + salt)


def verify_password(password: str, salt: str, hashed_pw: str) -> bool:
    return pwd_context.verify(password + salt, hashed_pw)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"issuer": JWT_AUDIENCE})
    to_encode.update({"issued": datetime.utcnow().__str__()})
    to_encode.update({"expires": str(datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES))})
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, str(JWT_SECRET_KEY), algorithm=JWT_ALGORITHM)


def verify_access_token(token: str) -> AccessToken:
    try:
        payload = jwt.decode(token, str(JWT_SECRET_KEY), algorithms=[JWT_ALGORITHM])
    except JWTError as ex:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"msg": ex.__str__(), "errno": 103})
    except AttributeError:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "msg": "Token cannot be null",
            "errno": 103
        })
    return AccessToken.parse_obj(payload)


def create_password_reset_token(data: PasswordResetToken) -> str:
    expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    data.exp = expire
    return jwt.encode(data.dict(), str(JWT_PASSWORD_RESET_SECRET_KEY), algorithm=JWT_ALGORITHM)


def verify_password_reset_token(token: str) -> PasswordResetToken:
    try:
        payload = jwt.decode(token, str(JWT_PASSWORD_RESET_SECRET_KEY), algorithms=[JWT_ALGORITHM])
    except JWTError as ex:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"msg": ex.__str__(), "errno": 103})
    except AttributeError:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail={
            "msg": "Token cannot be null",
            "errno": 103
        })
    return PasswordResetToken.parse_obj(payload)
