from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# ЗАМІНЕНО: localhost на db, щоб підключитися через внутрішню мережу Docker
SQLALCHEMY_DATABASE_URL = "postgresql+psycopg://postgres:17477321@db:5432/contacts_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()