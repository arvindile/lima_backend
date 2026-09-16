from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_player
from app.models import Block, Friendship, Match, MatchStatus, Player
from app.schemas import BlockCreate, BlockOut

router = APIRouter(prefix="/blocks", tags=["blocks"])


def is_blocked_either_way(db: Session, player_a_id: str, player_b_id: str) -> bool:
    """
    True if either player has blocked the other. Used by messages,
    friend requests, and match invites to stop contact in both
    directions — being blocked stops you contacting them, and blocking
    someone stops them contacting you back too.
    """
    existing = (
        db.query(Block)
        .filter(
            or_(
                (Block.blocker_id == player_a_id) & (Block.blocked_id == player_b_id),
                (Block.blocker_id == player_b_id) & (Block.blocked_id == player_a_id),
            ),
        )
        .first()
    )
    return existing is not None


@router.post("", response_model=BlockOut)
def block_player(
    payload: BlockCreate,
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    if current_player.id == payload.blocked_id:
        raise HTTPException(status_code=400, detail="You can't block yourself")

    target = db.query(Player).filter(Player.id == payload.blocked_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Player not found")

    existing = (
        db.query(Block)
        .filter(Block.blocker_id == current_player.id, Block.blocked_id == payload.blocked_id)
        .first()
    )
    if existing:
        return BlockOut(
            id=existing.id,
            blocked_id=existing.blocked_id,
            blocked_username=target.username,
            created_at=existing.created_at,
        )

    block = Block(blocker_id=current_player.id, blocked_id=payload.blocked_id)
    db.add(block)

    # Blocking someone ends any existing relationship with them — a
    # friendship left in place, or a match invite still sitting pending,
    # would be a strange contradiction with "I don't want contact from
    # this person."
    db.query(Friendship).filter(
        or_(
            (Friendship.requester_id == current_player.id) & (Friendship.addressee_id == payload.blocked_id),
            (Friendship.requester_id == payload.blocked_id) & (Friendship.addressee_id == current_player.id),
        ),
    ).delete(synchronize_session=False)

    pending_invites = (
        db.query(Match)
        .filter(
            Match.status == MatchStatus.PENDING,
            or_(
                (Match.vanguard_id == current_player.id) & (Match.sentinel_id == payload.blocked_id),
                (Match.vanguard_id == payload.blocked_id) & (Match.sentinel_id == current_player.id),
            ),
        )
        .all()
    )
    for match in pending_invites:
        match.status = MatchStatus.DECLINED

    db.commit()
    db.refresh(block)
    return BlockOut(
        id=block.id,
        blocked_id=block.blocked_id,
        blocked_username=target.username,
        created_at=block.created_at,
    )


@router.delete("/{blocked_id}", status_code=204)
def unblock_player(
    blocked_id: str,
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    block = (
        db.query(Block)
        .filter(Block.blocker_id == current_player.id, Block.blocked_id == blocked_id)
        .first()
    )
    if block:
        db.delete(block)
        db.commit()


@router.get("", response_model=List[BlockOut])
def list_my_blocks(
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    blocks = db.query(Block).filter(Block.blocker_id == current_player.id).all()
    if not blocks:
        return []

    players_by_id = {
        p.id: p for p in db.query(Player).filter(Player.id.in_([b.blocked_id for b in blocks])).all()
    }
    return [
        BlockOut(
            id=b.id,
            blocked_id=b.blocked_id,
            # Falls back to a placeholder rather than crashing if the
            # blocked player's row is somehow gone — shouldn't normally
            # happen, but a display list is the wrong place to 500 over it.
            blocked_username=players_by_id[b.blocked_id].username if b.blocked_id in players_by_id else "Unknown player",
            created_at=b.created_at,
        )
        for b in blocks
    ]
