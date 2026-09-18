from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Player
from app.schemas import PlayerOut

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


def _order_column(category: str):
    """category is "singles" (default) or "doubles" — picks which point
    total to rank by. Doubles is tracked as its own separate ranking, not
    folded into singles points; see the Player model for why."""
    if category == "doubles":
        return Player.doubles_points
    if category == "singles":
        return Player.points
    raise HTTPException(status_code=400, detail="category must be 'singles' or 'doubles'")


@router.get("/barangay/{barangay_id}", response_model=List[PlayerOut])
def barangay_leaderboard(
    barangay_id: str,
    category: str = Query("singles"),
    db: Session = Depends(get_db),
):
    return (
        db.query(Player)
        .filter(Player.barangay_id == barangay_id, Player.is_deleted == False)  # noqa: E712
        .order_by(_order_column(category).desc())
        .limit(100)
        .all()
    )


@router.get("/city/{city_id}", response_model=List[PlayerOut])
def city_leaderboard(
    city_id: str,
    category: str = Query("singles"),
    db: Session = Depends(get_db),
):
    return (
        db.query(Player)
        .filter(Player.city_id == city_id, Player.is_deleted == False)  # noqa: E712
        .order_by(_order_column(category).desc())
        .limit(100)
        .all()
    )


@router.get("/province/{province_id}", response_model=List[PlayerOut])
def province_leaderboard(
    province_id: str,
    category: str = Query("singles"),
    db: Session = Depends(get_db),
):
    return (
        db.query(Player)
        .filter(Player.province_id == province_id, Player.is_deleted == False)  # noqa: E712
        .order_by(_order_column(category).desc())
        .limit(100)
        .all()
    )


@router.get("/national", response_model=List[PlayerOut])
def national_leaderboard(
    category: str = Query("singles"),
    db: Session = Depends(get_db),
):
    return (
        db.query(Player)
        .filter(Player.is_deleted == False)  # noqa: E712
        .order_by(_order_column(category).desc())
        .limit(100)
        .all()
    )
