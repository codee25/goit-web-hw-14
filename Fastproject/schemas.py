from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- СХЕМИ ДЛЯ КОРИСТУВАЧІВ ---
class UserModel(BaseModel):
    username: str = Field(min_length=5, max_length=16)
    email: EmailStr
    password: str = Field(min_length=6, max_length=10)

class UserDb(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime
    avatar: Optional[str]

    model_config = ConfigDict(from_attributes=True)

class UserResponse(BaseModel):
    user: UserDb
    detail: str = "User successfully created"

# Модель для чистого логіну (тільки два поля)
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenModel(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

# --- СХЕМИ ДЛЯ КОНТАКТІВ ---
class ContactBase(BaseModel):
    first_name: str = Field(max_length=50)
    last_name: str = Field(max_length=50)
    email: EmailStr
    phone: str = Field(max_length=20)
    birthday: date
    additional_data: Optional[str] = None

class ContactCreate(ContactBase):
    pass

class ContactResponse(ContactBase):
    id: int

    class Config:
        from_attributes = True