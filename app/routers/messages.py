from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Message, Player
from app.schemas import MessageCreate, MessageOut

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
