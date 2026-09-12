import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import auth, friends, leaderboard, matches, messages, players, regions

# For local dev this creates tables automatically from the SQLAlchemy models.
# For production, prefer Alembic migrations instead of relying on this.
Base.metadata.create_all(bind=engine)

os.makedirs("uploads", exist_ok=True)

app = FastAPI(title="LIMA API", version="0.1.0")

# Local-disk fallback only — avatars are served from Cloudinary in
# production (see app/storage.py) whenever CLOUDINARY_* env vars are set,
# since Render's disk doesn't survive a redeploy. This mount just keeps
# local dev working when no Cloudinary account is configured.
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(players.router)
app.include_router(matches.router)
app.include_router(leaderboard.router)
app.include_router(friends.router)
app.include_router(messages.router)
app.include_router(auth.router)
app.include_router(regions.router)


@app.get("/health")
def health():
    return {"status": "ok"}
