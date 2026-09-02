import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Falls back to a local SQLite file if DATABASE_URL isn't set, so you can run
# and test the API immediately without standing up Postgres first. Set
# DATABASE_URL (e.g. postgresql://user:pass@host:5432/lima) for real use.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lima.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
