from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Player
from app.schemas import PlayerOut

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/barangay/{barangay_id}", response_model=List[PlayerOut])
def barangay_leaderboard(barangay_id: str, db: Session = Depends(get_db)):
    return (
        db.query(Player)
        .filter(Player.barangay_id == barangay_id)
        .order_by(Player.points.desc())
        .limit(100)
        .all()
    )


@router.get("/city/{city_id}", response_model=List[PlayerOut])
def city_leaderboard(city_id: str, db: Session = Depends(get_db)):
    return (
        db.query(Player)
        .filter(Player.city_id == city_id)
        .order_by(Player.points.desc())
        .limit(100)
        .all()
    )


@router.get("/province/{province_id}", response_model=List[PlayerOut])
def province_leaderboard(province_id: str, db: Session = Depends(get_db)):
    return (
        db.query(Player)
        .filter(Player.province_id == province_id)
        .order_by(Player.points.desc())
        .limit(100)
        .all()
    )


@router.get("/national", response_model=List[PlayerOut])
def national_leaderboard(db: Session = Depends(get_db)):
    return db.query(Player).order_by(Player.points.desc()).limit(100).all()
