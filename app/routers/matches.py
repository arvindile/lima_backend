from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Match, MatchStatus, Player
from app.schemas import LiveStateUpdate, MatchCreate, MatchFinish, MatchOut, ScoreUpdate
from app.scoring import calculate_points, is_recordable

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("", response_model=MatchOut)
def create_match(payload: MatchCreate, db: Session = Depends(get_db)):
    """Creates a match invite — status starts as PENDING until the
    opponent (sentinel) accepts it via /accept."""
    for player_id in (payload.vanguard_id, payload.sentinel_id):
        if not db.query(Player).filter(Player.id == player_id).first():
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    match = Match(
        vanguard_id=payload.vanguard_id,
        sentinel_id=payload.sentinel_id,
        referee_id=payload.referee_id,
        status=MatchStatus.PENDING,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


@router.get("/pending/{player_id}", response_model=List[MatchOut])
def list_pending_invites(player_id: str, db: Session = Depends(get_db)):
    """Invites waiting for this player to accept/decline — they're always
    the sentinel (opponent) side of a pending match."""
    return (
        db.query(Match)
        .filter(Match.sentinel_id == player_id, Match.status == MatchStatus.PENDING)
        .order_by(Match.started_at.desc())
        .all()
    )


@router.get("/{match_id}", response_model=MatchOut)
def get_match(match_id: str, db: Session = Depends(get_db)):
    return _get_match_or_404(match_id, db)


@router.post("/{match_id}/accept", response_model=MatchOut)
def accept_match(match_id: str, db: Session = Depends(get_db)):
    match = _get_match_or_404(match_id, db)
    if match.status != MatchStatus.PENDING:
        raise HTTPException(status_code=400, detail="Match is not pending")

    match.status = MatchStatus.IN_PROGRESS
    # This is the real "clock zero" — not when the invite was created, since
    # that could've been sitting pending for a while before acceptance.
    match.game_started_at = datetime.utcnow()
    db.commit()
    db.refresh(match)
    return match


@router.post("/{match_id}/decline", response_model=MatchOut)
def decline_match(match_id: str, db: Session = Depends(get_db)):
    match = _get_match_or_404(match_id, db)
    if match.status != MatchStatus.PENDING:
        raise HTTPException(status_code=400, detail="Match is not pending")

    match.status = MatchStatus.DECLINED
    db.commit()
    db.refresh(match)
    return match


@router.patch("/{match_id}/live", response_model=MatchOut)
def update_live_state(match_id: str, payload: LiveStateUpdate, db: Session = Depends(get_db)):
    """
    The backend is the single source of truth for a match IN PROGRESS.
    Both devices push every score/set/pause change here immediately, and
    both devices poll GET /matches/{id} to pick up what the other side did —
    this is what keeps two phones showing the same live match instead of
    each running its own disconnected copy.
    """
    match = _get_match_or_404(match_id, db)
    if match.status != MatchStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Match is not in progress")

    # Track accumulated paused time so elapsed-time math stays correct even
    # though the timer itself is computed client-side from timestamps.
    if payload.is_paused and not match.is_paused:
        match.paused_at = datetime.utcnow()
    elif not payload.is_paused and match.is_paused and match.paused_at:
        match.total_paused_seconds += int((datetime.utcnow() - match.paused_at).total_seconds())
        match.paused_at = None

    match.vanguard_score = payload.vanguard_score
    match.sentinel_score = payload.sentinel_score
    match.vanguard_sets_won = payload.vanguard_sets_won
    match.sentinel_sets_won = payload.sentinel_sets_won
    match.is_paused = payload.is_paused

    db.commit()
    db.refresh(match)
    return match


@router.patch("/{match_id}/score", response_model=MatchOut)
def update_score(match_id: str, payload: ScoreUpdate, db: Session = Depends(get_db)):
    match = _get_match_or_404(match_id, db)
    if match.status != MatchStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Match is not in progress")

    match.vanguard_score = payload.vanguard_score
    match.sentinel_score = payload.sentinel_score
    db.commit()
    db.refresh(match)
    return match


@router.post("/{match_id}/finish", response_model=MatchOut)
def finish_match(match_id: str, payload: MatchFinish, db: Session = Depends(get_db)):
    match = _get_match_or_404(match_id, db)
    if match.status != MatchStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Match is not in progress")

    match.ended_at = datetime.utcnow()
    match.total_time_seconds = payload.total_time_seconds
    match.time_per_set_seconds = payload.time_per_set_seconds

    recordable = is_recordable(payload.total_time_seconds, payload.time_per_set_seconds)

    if not recordable:
        match.status = MatchStatus.NOT_RECORDED
        db.commit()
        db.refresh(match)
        return match

    vanguard = db.query(Player).filter(Player.id == match.vanguard_id).first()
    sentinel = db.query(Player).filter(Player.id == match.sentinel_id).first()

    if match.vanguard_score == match.sentinel_score:
        # Tie — recorded for history, but no points change hands.
        match.status = MatchStatus.COMPLETED
        vanguard.matches_played += 1
        sentinel.matches_played += 1
        db.commit()
        db.refresh(match)
        return match

    winner_is_vanguard = match.vanguard_score > match.sentinel_score
    winner, loser = (vanguard, sentinel) if winner_is_vanguard else (sentinel, vanguard)

    result = calculate_points(winner_points=winner.points, loser_points=loser.points)

    winner.points += result.points_to_winner
    winner.wins += 1
    winner.matches_played += 1
    loser.points += result.points_to_loser
    loser.losses += 1
    loser.matches_played += 1

    match.status = MatchStatus.COMPLETED
    match.winner_id = winner.id
    match.points_awarded_to_winner = result.points_to_winner
    match.points_awarded_to_loser = result.points_to_loser

    db.commit()
    db.refresh(match)
    return match


def _get_match_or_404(match_id: str, db: Session) -> Match:
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match
