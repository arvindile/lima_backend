from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import create_access_token, verify_password
from app.database import get_db
from app.models import Player
from app.schemas import AuthResponse, LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.username == payload.username).first()
    if not player or not verify_password(payload.password, player.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(player.id)
    return AuthResponse(access_token=token, player=player)
