from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_player
from app.models import Match, MatchCategory, MatchStatus, Player
from app.routers.blocks import is_blocked_either_way
from app.schemas import LiveStateUpdate, MatchCreate, MatchFinish, MatchOut, ScoreUpdate
from app.scoring import calculate_points, is_recordable

router = APIRouter(prefix="/matches", tags=["matches"])


def _all_participants(match: Match) -> List[str]:
    """Every player involved in a match — 2 for singles, 4 for doubles."""
    ids = [match.vanguard_id, match.sentinel_id]
    if match.vanguard_partner_id:
        ids.append(match.vanguard_partner_id)
    if match.sentinel_partner_id:
        ids.append(match.sentinel_partner_id)
    return ids


@router.post("", response_model=MatchOut)
def create_match(
    payload: MatchCreate,
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    """
    Creates a match invite — status starts as PENDING until everyone
    who needs to accept has done so (see /accept). For SINGLES that's
    just the sentinel (opponent); for DOUBLES it's the sentinel PLUS both
    partners — the creator (vanguard) is implicitly in, since they're
    the one sending the invite.
    """
    if current_player.id != payload.vanguard_id:
        raise HTTPException(status_code=403, detail="You can only send an invite as yourself")

    if payload.category == MatchCategory.DOUBLES:
        if not payload.vanguard_partner_id or not payload.sentinel_partner_id:
            raise HTTPException(status_code=400, detail="Doubles matches need a partner for both sides")
        participant_ids = [
            payload.vanguard_id,
            payload.sentinel_id,
            payload.vanguard_partner_id,
            payload.sentinel_partner_id,
        ]
        if len(set(participant_ids)) != 4:
            raise HTTPException(status_code=400, detail="All four players in a doubles match must be different people")
    else:
        participant_ids = [payload.vanguard_id, payload.sentinel_id]

    for player_id in participant_ids:
        if not db.query(Player).filter(Player.id == player_id).first():
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    # Check every cross-pair for a block, not just vanguard<->sentinel —
    # nobody in either team should have blocked (or be blocked by) anyone
    # else involved, on either team.
    for i, a in enumerate(participant_ids):
        for b in participant_ids[i + 1:]:
            if is_blocked_either_way(db, a, b):
                raise HTTPException(status_code=403, detail="One of these players can't be invited to a match with you")

    match = Match(
        category=payload.category,
        vanguard_id=payload.vanguard_id,
        sentinel_id=payload.sentinel_id,
        referee_id=payload.referee_id,
        vanguard_partner_id=payload.vanguard_partner_id if payload.category == MatchCategory.DOUBLES else None,
        sentinel_partner_id=payload.sentinel_partner_id if payload.category == MatchCategory.DOUBLES else None,
        status=MatchStatus.PENDING,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


@router.get("/pending/{player_id}", response_model=List[MatchOut])
def list_pending_invites(player_id: str, db: Session = Depends(get_db)):
    """
    Invites waiting for this player to accept/decline. For SINGLES
    they're always the sentinel. For DOUBLES they could be the sentinel,
    the vanguard's partner, or the sentinel's partner — the vanguard
    themselves never shows up here, since they're the one who sent it.
    """
    return (
        db.query(Match)
        .filter(
            Match.status == MatchStatus.PENDING,
            or_(
                Match.sentinel_id == player_id,
                Match.vanguard_partner_id == player_id,
                Match.sentinel_partner_id == player_id,
            ),
        )
        .order_by(Match.started_at.desc())
        .all()
    )


@router.get("/{match_id}", response_model=MatchOut)
def get_match(match_id: str, db: Session = Depends(get_db)):
    return _get_match_or_404(match_id, db)


@router.post("/{match_id}/accept", response_model=MatchOut)
def accept_match(
    match_id: str,
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    match = _get_match_or_404(match_id, db)
    if match.status != MatchStatus.PENDING:
        raise HTTPException(status_code=400, detail="Match is not pending")

    if match.category == MatchCategory.SINGLES:
        if current_player.id != match.sentinel_id:
            raise HTTPException(status_code=403, detail="Only the invited player can accept this match")
        match.sentinel_accepted = True
    else:
        if current_player.id == match.sentinel_id:
            match.sentinel_accepted = True
        elif current_player.id == match.vanguard_partner_id:
            match.vanguard_partner_accepted = True
        elif current_player.id == match.sentinel_partner_id:
            match.sentinel_partner_accepted = True
        else:
            raise HTTPException(status_code=403, detail="You're not invited to this match")

    all_accepted = (
        match.category == MatchCategory.SINGLES and match.sentinel_accepted
    ) or (
        match.category == MatchCategory.DOUBLES
        and match.sentinel_accepted
        and match.vanguard_partner_accepted
        and match.sentinel_partner_accepted
    )

    if all_accepted:
        match.status = MatchStatus.IN_PROGRESS
        # This is the real "clock zero" — not when the invite was created,
        # since that could've been sitting pending a while (in doubles,
        # potentially waiting on multiple people) before everyone was in.
        match.game_started_at = datetime.utcnow()

    db.commit()
    db.refresh(match)
    return match


@router.post("/{match_id}/decline", response_model=MatchOut)
def decline_match(
    match_id: str,
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    match = _get_match_or_404(match_id, db)
    if match.status != MatchStatus.PENDING:
        raise HTTPException(status_code=400, detail="Match is not pending")

    invited_ids = {match.sentinel_id, match.vanguard_partner_id, match.sentinel_partner_id} - {None}
    if current_player.id not in invited_ids:
        raise HTTPException(status_code=403, detail="You're not invited to this match")

    # Anyone declining cancels the whole match for everyone — a doubles
    # game can't go ahead 3-vs-1 just because the other two said yes.
    match.status = MatchStatus.DECLINED
    db.commit()
    db.refresh(match)
    return match


@router.patch("/{match_id}/live", response_model=MatchOut)
def update_live_state(
    match_id: str,
    payload: LiveStateUpdate,
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    """
    The backend is the single source of truth for a match IN PROGRESS.
    Every device involved pushes every score/set/pause change here
    immediately, and polls GET /matches/{id} to pick up what anyone else
    did — this is what keeps everyone's screen showing the same live
    match instead of disconnected copies. For doubles that's up to 4
    devices instead of 2, but the mechanism is identical.
    """
    match = _get_match_or_404(match_id, db)
    if current_player.id not in _all_participants(match):
        raise HTTPException(status_code=403, detail="You're not a participant in this match")
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
def update_score(
    match_id: str,
    payload: ScoreUpdate,
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    match = _get_match_or_404(match_id, db)
    if current_player.id not in _all_participants(match):
        raise HTTPException(status_code=403, detail="You're not a participant in this match")
    if match.status != MatchStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Match is not in progress")

    match.vanguard_score = payload.vanguard_score
    match.sentinel_score = payload.sentinel_score
    db.commit()
    db.refresh(match)
    return match


@router.post("/{match_id}/finish", response_model=MatchOut)
def finish_match(
    match_id: str,
    payload: MatchFinish,
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    match = _get_match_or_404(match_id, db)
    if current_player.id not in _all_participants(match):
        raise HTTPException(status_code=403, detail="You're not a participant in this match")
    if match.status != MatchStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Match is not in progress")

    match.ended_at = datetime.utcnow()
    match.total_time_seconds = payload.total_time_seconds
    match.time_per_set_seconds = payload.time_per_set_seconds

    recordable = is_recordable(payload.total_time_seconds, payload.time_per_set_seconds)

    if match.category == MatchCategory.DOUBLES:
        return _finish_doubles(match, recordable, db)
    return _finish_singles(match, recordable, db)


def _finish_singles(match: Match, recordable: bool, db: Session) -> Match:
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


def _finish_doubles(match: Match, recordable: bool, db: Session) -> Match:
    if not recordable:
        match.status = MatchStatus.NOT_RECORDED
        db.commit()
        db.refresh(match)
        return match

    vanguard = db.query(Player).filter(Player.id == match.vanguard_id).first()
    vanguard_partner = db.query(Player).filter(Player.id == match.vanguard_partner_id).first()
    sentinel = db.query(Player).filter(Player.id == match.sentinel_id).first()
    sentinel_partner = db.query(Player).filter(Player.id == match.sentinel_partner_id).first()

    vanguard_team = [vanguard, vanguard_partner]
    sentinel_team = [sentinel, sentinel_partner]

    if match.vanguard_score == match.sentinel_score:
        # Tie — recorded for history, but no points change hands.
        match.status = MatchStatus.COMPLETED
        for player in vanguard_team + sentinel_team:
            player.doubles_matches_played += 1
        db.commit()
        db.refresh(match)
        return match

    winner_is_vanguard = match.vanguard_score > match.sentinel_score
    winning_team, losing_team = (vanguard_team, sentinel_team) if winner_is_vanguard else (sentinel_team, vanguard_team)

    # Team skill is each side's average doubles rating — a fair basis for
    # the same skill-gap multiplier singles uses, without needing a
    # separate formula.
    winner_avg = round(sum(p.doubles_points for p in winning_team) / 2)
    loser_avg = round(sum(p.doubles_points for p in losing_team) / 2)
    result = calculate_points(winner_points=winner_avg, loser_points=loser_avg)

    # Both partners on the winning side get the FULL points each (not
    # split) — the match result reflects the team's performance, and
    # each player individually gets credit for that result, the same way
    # DUPR-style doubles rating systems work.
    for player in winning_team:
        player.doubles_points += result.points_to_winner
        player.doubles_wins += 1
        player.doubles_matches_played += 1
    for player in losing_team:
        player.doubles_points += result.points_to_loser
        player.doubles_losses += 1
        player.doubles_matches_played += 1

    match.status = MatchStatus.COMPLETED
    match.winner_id = winning_team[0].id  # one of the two winners, for reference
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
