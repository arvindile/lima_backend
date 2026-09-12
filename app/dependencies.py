from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
import jwt

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

    return player
