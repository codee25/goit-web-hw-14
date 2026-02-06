from datetime import date, timedelta
from typing import List

import cloudinary
import cloudinary.uploader
import redis.asyncio as redis
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware

try:
    from fastapi_limiter import FastLimiter
    from fastapi_limiter.depends import RateLimiter
except ImportError:
    RateLimiter = lambda *args, **kwargs: None 
    FastLimiter = None

from fastapi_limiter.depends import RateLimiter
from sqlalchemy import extract, or_
from sqlalchemy.orm import Session

import models
import schemas
from auth import auth_service, get_current_user
from config import settings  # Виправлено під твою структуру (без src)
from database import engine, get_db

# Створюємо таблиці в базі при запуску

app = FastAPI(title="Contacts API PRO (HW 13)")

# --- 1. Налаштування CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. Налаштування Cloudinary ---
cloudinary.config(
    cloud_name=settings.cloudinary_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
    secure=True
)

# --- 3. Налаштування Redis для Rate Limiting ---
@app.on_event("startup")
async def startup():
    models.Base.metadata.create_all(bind=engine)
    r = await redis.from_url(
        f"redis://{settings.redis_host}:{settings.redis_port}", 
        encoding="utf-8", 
        decode_responses=True
    )
    if FastLimiter:
        await FastLimiter.init(r)
# --- МАРШРУТИ АУТЕНТИФІКАЦІЇ ---

@app.post("/signup", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: schemas.UserModel, background_tasks: BackgroundTasks, request: Request, db: Session = Depends(get_db)):
    exist_user = db.query(models.User).filter(models.User.email == body.email).first()
    if exist_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists")
    
    hashed_password = auth_service.get_password_hash(body.password)
    new_user = models.User(username=body.username, email=body.email, password=hashed_password, confirmed=False)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Якщо сервіс відправки пошти підключений, розкоментуй:
    # from src.services.email import send_email 
    # background_tasks.add_task(send_email, new_user.email, new_user.username, str(request.base_url))
    
    return {"user": new_user, "detail": "User created. Please confirm email if service is active."}

@app.get("/confirmed_email/{token}")
async def confirmed_email(token: str, db: Session = Depends(get_db)):
    email = await auth_service.get_email_from_token(token)
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification error")
    if user.confirmed:
        return {"message": "Your email is already confirmed"}
    
    user.confirmed = True
    db.commit()
    return {"message": "Email confirmed successfully"}

@app.post("/login", response_model=schemas.TokenModel)
async def login(body: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    
    if user is None or not auth_service.verify_password(body.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    
    if not user.confirmed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email not confirmed")
    
    access_token = await auth_service.create_access_token(data={"sub": user.email})
    refresh_token = await auth_service.create_refresh_token(data={"sub": user.email})
    
    user.refresh_token = refresh_token
    db.commit()
    
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

# --- МАРШРУТИ КОРИСТУВАЧА ---

@app.patch("/users/avatar", response_model=schemas.UserDb)
async def update_avatar(
    file: UploadFile = File(...), 
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    public_id = f'ContactsApp/{current_user.email}'
    r = cloudinary.uploader.upload(file.file, public_id=public_id, overwrite=True)
    src_url = cloudinary.CloudinaryImage(public_id).build_url(width=250, height=250, crop='fill', version=r.get('version'))
    
    current_user.avatar = src_url
    db.commit()
    return current_user

# --- МАРШРУТИ КОНТАКТІВ ---

@app.post("/contacts/", 
        response_model=schemas.ContactResponse, 
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(RateLimiter(2, 5))])

def create_contact(contact: schemas.ContactCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db_contact = models.Contact(**contact.model_dump(), user_id=current_user.id)
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

@app.get("/contacts/", response_model=List[schemas.ContactResponse])
def read_contacts(query: str = Query(None), db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    contacts = db.query(models.Contact).filter(models.Contact.user_id == current_user.id)
    if query:
        contacts = contacts.filter(
            or_(
                models.Contact.first_name.ilike(f"%{query}%"),
                models.Contact.last_name.ilike(f"%{query}%"),
                models.Contact.email.ilike(f"%{query}%")
            )
        )
    return contacts.all()

@app.get("/contacts/birthdays/", response_model=List[schemas.ContactResponse])
def get_upcoming_birthdays(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    today = date.today()
    upcoming = []
    for i in range(7):
        target = today + timedelta(days=i)
        contacts = db.query(models.Contact).filter(
            models.Contact.user_id == current_user.id,
            extract('month', models.Contact.birthday) == target.month,
            extract('day', models.Contact.birthday) == target.day
        ).all()
        upcoming.extend(contacts)
    return upcoming

@app.get("/contacts/{contact_id}", response_model=schemas.ContactResponse)
def read_contact(contact_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id, models.Contact.user_id == current_user.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@app.put("/contacts/{contact_id}", response_model=schemas.ContactResponse)
def update_contact(contact_id: int, contact_update: schemas.ContactCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db_contact = db.query(models.Contact).filter(models.Contact.id == contact_id, models.Contact.user_id == current_user.id).first()
    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    for key, value in contact_update.model_dump().items():
        setattr(db_contact, key, value)
    db.commit()
    db.refresh(db_contact)
    return db_contact

@app.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db_contact = db.query(models.Contact).filter(models.Contact.id == contact_id, models.Contact.user_id == current_user.id).first()
    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(db_contact)
    db.commit()
    return None