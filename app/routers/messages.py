from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Friendship, FriendshipStatus, Message, Player
from app.schemas import MessageCreate, MessageOut, ThreadOut

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_model=MessageOut)
def send_message(payload: MessageCreate, db: Session = Depends(get_db)):
    for player_id in (payload.sender_id, payload.receiver_id):
        if not db.query(Player).filter(Player.id == player_id).first():
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    message = Message(
        sender_id=payload.sender_id,
        receiver_id=payload.receiver_id,
        content=payload.content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/threads/{player_id}", response_model=List[ThreadOut])
def list_threads(player_id: str, db: Session = Depends(get_db)):
    """
    One row per friend, with their most recent message (if any) — this is
    what powers the Chat tab's inbox-style preview list. Registered BEFORE
    the /{player_id}/{other_id} route below, since both are two path
    segments and would otherwise collide (FastAPI matches in registration
    order — /threads/abc would wrongly hit the generic route first).
    """
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

    friends_by_id = {p.id: p for p in db.query(Player).filter(Player.id.in_(friend_ids)).all()}

    threads = []
    for friend_id in friend_ids:
        friend = friends_by_id.get(friend_id)
        if not friend:
            continue

        last_message = (
            db.query(Message)
            .filter(
                or_(
                    and_(Message.sender_id == player_id, Message.receiver_id == friend_id),
                    and_(Message.sender_id == friend_id, Message.receiver_id == player_id),
                ),
            )
            .order_by(Message.sent_at.desc())
            .first()
        )

        threads.append(
            ThreadOut(
                friend=friend,
                last_message=last_message.content if last_message else None,
                last_message_at=last_message.sent_at if last_message else None,
            ),
        )

    # Most recently active conversations first; friends with no messages yet
    # sink to the bottom rather than crashing the sort on a None timestamp.
    threads.sort(key=lambda t: t.last_message_at or datetime.min, reverse=True)
    return threads


@router.get("/{player_id}/{other_id}", response_model=List[MessageOut])
def get_conversation(player_id: str, other_id: str, db: Session = Depends(get_db)):
    """Full message history between two players, oldest first."""
    return (
        db.query(Message)
        .filter(
            or_(
                and_(Message.sender_id == player_id, Message.receiver_id == other_id),
                and_(Message.sender_id == other_id, Message.receiver_id == player_id),
            ),
        )
        .order_by(Message.sent_at.asc())
        .all()
    )
