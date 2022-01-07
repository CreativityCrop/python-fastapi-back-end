import bcrypt
from fastapi import HTTPException
from passlib.context import CryptContext
from starlette import status

from app.models.user import UserPasswordUpdate
from datetime import datetime, timedelta

from jose import JWTError, jwt

from app.config import *
from app.models.token import AccessToken

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def create_salt_and_hashed_password(self, *, plaintext_password: str) -> UserPasswordUpdate:
        salt = self.generate_salt()
        hashed_password = self.hash_password(password=plaintext_password, salt=salt)
        return UserPasswordUpdate(salt=salt, password=hashed_password)

    @staticmethod
    def generate_salt() -> str:
        return bcrypt.gensalt().decode()

    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        return pwd_context.hash(password + salt)

    @staticmethod
    def verify_password(password: str, salt: str, hashed_pw: str) -> bool:
        return pwd_context.verify(password + salt, hashed_pw)

    @staticmethod
    def create_access_token(data: dict):
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"issuer": JWT_AUDIENCE})
        to_encode.update({"issued": datetime.utcnow().__str__()})
        to_encode.update({"expires": str(datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES))})
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, str(JWT_SECRET_KEY), algorithm=JWT_ALGORITHM)

    @staticmethod
    def verify_token(token: str) -> AccessToken:
        try:
            payload = jwt.decode(token, str(JWT_SECRET_KEY), algorithms=[JWT_ALGORITHM])
            # print(payload)
            token_data = AccessToken(
                user=payload.get("user"),
                issuer=payload.get("issuer"),
                issued=payload.get("issued"),
                expires=payload.get("expires"),
                exp=payload.get("exp")
            )
        except JWTError as ex:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"failed": ex.__str__()})

        return token_data
