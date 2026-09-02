from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Friendship, FriendshipStatus, Player
from app.schemas import (
    FriendRequestCreate,
    FriendshipOut,
    PendingRequestOut,
    PlayerOut,
)

router = APIRouter(prefix="/friends", tags=["friends"])


@router.post("/request", response_model=FriendshipOut)
def send_friend_request(payload: FriendRequestCreate, db: Session = Depends(get_db)):
    if payload.requester_id == payload.addressee_id:
        raise HTTPException(status_code=400, detail="Can't friend yourself")

    for player_id in (payload.requester_id, payload.addressee_id):
        if not db.query(Player).filter(Player.id == player_id).first():
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    existing = (
        db.query(Friendship)
        .filter(
            or_(
                and_(Friendship.requester_id == payload.requester_id, Friendship.addressee_id == payload.addressee_id),
                and_(Friendship.requester_id == payload.addressee_id, Friendship.addressee_id == payload.requester_id),
            ),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Friendship already {existing.status.value.lower()}")

    friendship = Friendship(
        requester_id=payload.requester_id,
        addressee_id=payload.addressee_id,
        status=FriendshipStatus.PENDING,
    )
    db.add(friendship)
    db.commit()
    db.refresh(friendship)
    return friendship


@router.post("/{friendship_id}/accept", response_model=FriendshipOut)
def accept_friend_request(friendship_id: str, db: Session = Depends(get_db)):
    friendship = db.query(Friendship).filter(Friendship.id == friendship_id).first()
    if not friendship:
        raise HTTPException(status_code=404, detail="Friend request not found")

    friendship.status = FriendshipStatus.ACCEPTED
    db.commit()
    db.refresh(friendship)
    return friendship


@router.post("/{friendship_id}/decline")
def decline_friend_request(friendship_id: str, db: Session = Depends(get_db)):
    friendship = db.query(Friendship).filter(Friendship.id == friendship_id).first()
    if not friendship:
        raise HTTPException(status_code=404, detail="Friend request not found")

    db.delete(friendship)
    db.commit()
    return {"detail": "Declined"}


@router.get("/{player_id}", response_model=List[PlayerOut])
def list_friends(player_id: str, db: Session = Depends(get_db)):
    friendships = (
        db.query(Friendship)
        .filter(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(Friendship.requester_id == player_id, Friendship.addressee_id == player_id),
        )
        .all()
    )
    friend_ids = [
        f.addressee_id if f.requester_id == player_id else f.requester_id
        for f in friendships
    ]
    if not friend_ids:
        return []
    return db.query(Player).filter(Player.id.in_(friend_ids)).all()


@router.get("/{player_id}/pending", response_model=List[PendingRequestOut])
def list_pending_requests(player_id: str, db: Session = Depends(get_db)):
    """Incoming requests awaiting this player's response."""
    pending = (
        db.query(Friendship)
        .filter(Friendship.addressee_id == player_id, Friendship.status == FriendshipStatus.PENDING)
        .all()
    )
    result = []
    for friendship in pending:
        requester = db.query(Player).filter(Player.id == friendship.requester_id).first()
        if requester:
            result.append(PendingRequestOut(friendship_id=friendship.id, requester=requester))
    return result
