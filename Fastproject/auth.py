import pickle
from datetime import datetime, timedelta
from typing import Optional

import redis.asyncio as redis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

import models
from database import get_db


class Auth:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", truncate_error=False)
    SECRET_KEY = "your_super_secret_key_here" # В ідеалі тягнути з settings
    ALGORITHM = "HS256"
    oauth2_scheme = HTTPBearer()
    r = redis.Redis(host='localhost', port=6379, db=0)

    def verify_password(self, plain_password, hashed_password):
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str):
        return self.pwd_context.hash(password)

    async def create_access_token(self, data: dict, expires_delta: Optional[float] = None):
        to_encode = data.copy()
        expire = datetime.utcnow() + (timedelta(seconds=expires_delta) if expires_delta else timedelta(minutes=15))
        to_encode.update({"iat": datetime.utcnow(), "exp": expire, "scope": "access_token"})
        return jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)

    async def create_email_token(self, data: dict):
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=1)
        to_encode.update({"iat": datetime.utcnow(), "exp": expire, "scope": "email_token"})
        return jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)

auth_service = Auth()

async def get_current_user(token: HTTPAuthorizationCredentials = Depends(auth_service.oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token.credentials, auth_service.SECRET_KEY, algorithms=[auth_service.ALGORITHM])
        email = payload.get("sub")
        if email is None: raise credentials_exception
    except JWTError: raise credentials_exception

    # Кешування (Додаткове завдання)
    user_cache = await auth_service.r.get(f"user:{email}")
    if user_cache:
        user = pickle.loads(user_cache)
    else:
        user = db.query(models.User).filter(models.User.email == email).first()
        if user is None: raise credentials_exception
        await auth_service.r.set(f"user:{email}", pickle.dumps(user))
        await auth_service.r.expire(f"user:{email}", 900)
    return user