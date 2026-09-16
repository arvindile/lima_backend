from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
import jwt
import os

from app.auth import decode_access_token
from app.database import get_db
from app.models import Player


def get_current_player(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> Player:
    """
    Reads "Authorization: Bearer <token>", verifies it, and returns the
    Player it belongs to. Use this (instead of trusting a player_id from
    the URL/body) on any endpoint that acts ON BEHALF OF a player — e.g.
    changing their username, accepting a match, sending a message.

    Endpoints that only READ public data (profiles, leaderboards, match
    results) don't need this — anyone can already see that data in the
    app regardless of who's asking.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization[len("Bearer "):]

    try:
        player_id = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=401, detail="Player no longer exists")
    if player.is_deleted:
        # The account was deleted after this token was issued (tokens are
        # valid for 30 days and aren't individually revocable) — reject it
        # explicitly rather than letting a deleted account keep working
        # until the token naturally expires.
        raise HTTPException(status_code=401, detail="This account has been deleted")
    if player.is_banned:
        raise HTTPException(status_code=403, detail="Your account has been suspended")

    return player


ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")


def require_admin(x_admin_key: str = Header(None)):
    """
    Gates the review/ban endpoints in app/routers/admin.py. This is a
    deliberately minimal stopgap — a single shared secret, not a real
    admin role system — until there's an actual admin panel. Set
    ADMIN_API_KEY as a Render env var and send it as the X-Admin-Key
    header (e.g. from Postman) to use these endpoints. Treat this key
    with the same care as JWT_SECRET_KEY — anyone with it can ban any
    account.
    """
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="Admin access isn't configured on this server")
    if not x_admin_key or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")
