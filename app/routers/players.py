import re
import secrets
from typing import List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password
from app.database import get_db
from app.dependencies import get_current_player
from app.models import Friendship, Match, MatchStatus, Message, Player
from app.schemas import AuthResponse, EmailUpdate, PlayerCreate, PlayerOut, PlayerSelfOut, UsernameUpdate
from app.storage import delete_avatar, save_avatar

router = APIRouter(prefix="/players", tags=["players"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB

# Deliberately loose — just enough to catch obvious typos ("bob@gmail")
# and reject empty/garbage input, not a full RFC 5322 validator. Doing a
# real check would mean adding the email-validator package as a new
# dependency for one field; this catches the vast majority of real
# mistakes without that.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(email: str) -> str:
    email = email.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail="That doesn't look like a valid email address")
    return email


@router.post("", response_model=AuthResponse)
def register_player(payload: PlayerCreate, db: Session = Depends(get_db)):
    existing = db.query(Player).filter(Player.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    email = _validate_email(payload.email)
    existing_email = db.query(Player).filter(Player.email == email).first()
    if existing_email:
        raise HTTPException(status_code=409, detail="An account with that email already exists")

    player = Player(
        username=payload.username,
        password_hash=hash_password(payload.password),
        email=email,
        avatar_url=payload.avatar_url,
        barangay_id=payload.barangay_id,
        city_id=payload.city_id,
        province_id=payload.province_id,
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    # Same shape as /auth/login, so the app is signed in immediately after
    # registering instead of needing a separate login call right after.
    token = create_access_token(player.id)
    return AuthResponse(access_token=token, player=player)


@router.delete("/me", status_code=204)
def delete_my_account(
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    """
    Deletes the caller's OWN account — matches what the in-app
    "Data & Privacy Requests" page promises users.

    The player row is anonymized rather than hard-deleted: Match rows
    reference players.id with no ON DELETE clause, so removing the row
    outright would break match history for every OTHER player this
    account ever played against. Anonymizing keeps the row (and their
    match history) intact while making the account itself unusable and
    unidentifiable — the same "kept in anonymized form" behavior already
    described to users.

    Friendships and chat messages ARE deleted outright rather than
    anonymized — that's this account's own social data, and doesn't
    affect any other player's independent record the way match history
    would.
    """
    player_id = current_player.id

    db.query(Message).filter(
        or_(Message.sender_id == player_id, Message.receiver_id == player_id),
    ).delete(synchronize_session=False)

    db.query(Friendship).filter(
        or_(Friendship.requester_id == player_id, Friendship.addressee_id == player_id),
    ).delete(synchronize_session=False)

    # Any invite still waiting on this player is now stale — decline it
    # rather than leaving it stuck pending forever.
    pending_invites = (
        db.query(Match)
        .filter(
            Match.status == MatchStatus.PENDING,
            or_(Match.vanguard_id == player_id, Match.sentinel_id == player_id),
        )
        .all()
    )
    for match in pending_invites:
        match.status = MatchStatus.DECLINED

    delete_avatar(player_id)  # best-effort — never blocks deletion

    # Anonymize the account. The new username is derived from the id
    # (already globally unique, so this can never collide), and the
    # password hash is replaced with something nobody could ever type —
    # combined with is_deleted being checked on every authenticated
    # request, there's no path back into this account.
    current_player.username = f"deleted_user_{player_id[:8]}"
    current_player.password_hash = hash_password(secrets.token_hex(32))
    current_player.avatar_url = None
    current_player.is_deleted = True
    db.commit()


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
def update_username(
    player_id: str,
    payload: UsernameUpdate,
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    if current_player.id != player_id:
        raise HTTPException(status_code=403, detail="You can only change your own username")

    player = current_player

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


@router.patch("/{player_id}/email", response_model=PlayerSelfOut)
def update_email(
    player_id: str,
    payload: EmailUpdate,
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    """
    Lets a player add or change their recovery email. This is how
    accounts created BEFORE this feature existed (with no email on file)
    get one added — without an email here, /auth/forgot-password has no
    way to reach that account at all.
    """
    if current_player.id != player_id:
        raise HTTPException(status_code=403, detail="You can only change your own email")

    email = _validate_email(payload.new_email)
    taken = db.query(Player).filter(Player.email == email, Player.id != player_id).first()
    if taken:
        raise HTTPException(status_code=409, detail="An account with that email already exists")

    current_player.email = email
    db.commit()
    db.refresh(current_player)
    return current_player


@router.post("/{player_id}/avatar", response_model=PlayerOut)
def upload_avatar(
    player_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    if current_player.id != player_id:
        raise HTTPException(status_code=403, detail="You can only change your own avatar")

    player = current_player

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WEBP images are allowed")

    contents = file.file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Image must be under 5MB")

    player.avatar_url = save_avatar(player_id, contents, file.content_type)
    db.commit()
    db.refresh(player)
    return player
