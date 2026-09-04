import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Falls back to a local SQLite file if DATABASE_URL isn't set, so you can run
# and test the API immediately without standing up Postgres first. Set
# DATABASE_URL (e.g. postgresql://user:pass@host:5432/lima) for real use.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lima.db")

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif "pg8000" in DATABASE_URL:
    # pg8000 (pure-Python driver, used as a local fallback on Windows when
    # psycopg2's compiled DLL won't load) wants SSL specified in code, not
    # as a `sslmode=` query param the way psycopg2 expects.
    connect_args = {"ssl_context": True}
else:
    connect_args = {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()