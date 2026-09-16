import random
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password, verify_password
from app.database import get_db
from app.dependencies import get_current_player
from app.email_utils import RESET_CODE_EXPIRY_MINUTES, send_password_reset_email
from app.models import Player
from app.schemas import AuthResponse, ForgotPasswordRequest, LoginRequest, PlayerSelfOut, ResetPasswordRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.username == payload.username).first()
    if not player or not verify_password(payload.password, player.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if player.is_banned:
        # Deliberately distinct from the generic 401 above — a banned
        # player DID enter the right password, so telling them that
        # explicitly isn't a security leak the way it would be for a
        # wrong-password guess, and it's much clearer for them to see.
        raise HTTPException(status_code=403, detail="Your account has been suspended")
    token = create_access_token(player.id)
    return AuthResponse(access_token=token, player=player)


@router.get("/me", response_model=PlayerSelfOut)
def get_me(current_player: Player = Depends(get_current_player)):
    """
    Lets the app restore a session on startup: send the saved token, get
    back fresh player data if it's still valid. A 401 here means the saved
    token is expired/invalid, telling the app to fall back to the login
    screen instead of trusting stale local data.
    """
    return current_player


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Starts a password reset: if the email belongs to an account, emails a
    6-digit code. Always returns the SAME response either way — this
    stops the endpoint from being usable to check which emails have a
    LIMA account (a common enumeration attack on forgot-password flows).
    """
    email = payload.email.strip().lower()
    player = db.query(Player).filter(Player.email == email, Player.is_deleted == False).first()  # noqa: E712

    if player:
        code = f"{random.randint(0, 999999):06d}"
        player.password_reset_code = code
        player.password_reset_expires_at = datetime.utcnow() + timedelta(minutes=RESET_CODE_EXPIRY_MINUTES)
        db.commit()
        send_password_reset_email(email, code)

    return {"message": "If that email is registered, a reset code has been sent to it."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    player = db.query(Player).filter(Player.email == email, Player.is_deleted == False).first()  # noqa: E712

    code_matches = player and player.password_reset_code == payload.code
    not_expired = player and player.password_reset_expires_at and player.password_reset_expires_at > datetime.utcnow()

    if not (player and code_matches and not_expired):
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")

    player.password_hash = hash_password(payload.new_password)
    player.password_reset_code = None
    player.password_reset_expires_at = None
    db.commit()

    return {"message": "Password reset successfully. You can now log in."}
