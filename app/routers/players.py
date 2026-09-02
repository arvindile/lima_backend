import os
import uuid
from typing import List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import get_db
from app.models import Player
from app.schemas import PlayerCreate, PlayerOut, UsernameUpdate

router = APIRouter(prefix="/players", tags=["players"])

UPLOAD_DIR = "uploads"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB


@router.post("", response_model=PlayerOut)
def register_player(payload: PlayerCreate, db: Session = Depends(get_db)):
    existing = db.query(Player).filter(Player.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    player = Player(
        username=payload.username,
        password_hash=hash_password(payload.password),
        avatar_url=payload.avatar_url,
        barangay_id=payload.barangay_id,
        city_id=payload.city_id,
        province_id=payload.province_id,
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


@router.get("/search", response_model=List[PlayerOut])
def search_players(q: str, db: Session = Depends(get_db)):
    return (
        db.query(Player)
        .filter(or_(Player.username.ilike(f"%{q}%"), Player.id == q))
        .limit(20)
        .all()
    )


@router.get("/{player_id}", response_model=PlayerOut)
def get_player(player_id: str, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@router.patch("/{player_id}/username", response_model=PlayerOut)
def update_username(player_id: str, payload: UsernameUpdate, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    if player.username_last_changed_at and player.username_last_changed_at > datetime.utcnow() - timedelta(days=30):
        raise HTTPException(status_code=429, detail="Username can only be changed once per month")

    taken = db.query(Player).filter(Player.username == payload.new_username).first()
    if taken:
        raise HTTPException(status_code=409, detail="Username already taken")

    player.username = payload.new_username
    player.username_last_changed_at = datetime.utcnow()
    db.commit()
    db.refresh(player)
    return player


@router.post("/{player_id}/avatar", response_model=PlayerOut)
def upload_avatar(player_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WEBP images are allowed")

    contents = file.file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Image must be under 5MB")

    extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[file.content_type]
    filename = f"{uuid.uuid4()}{extension}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    player.avatar_url = f"/uploads/{filename}"
    db.commit()
    db.refresh(player)
    return player
