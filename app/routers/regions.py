from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PhAddress

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("/provinces", response_model=List[str])
def list_provinces(db: Session = Depends(get_db)):
    rows = db.query(PhAddress.province).distinct().order_by(PhAddress.province).all()
    return [r[0] for r in rows]


@router.get("/cities", response_model=List[str])
def list_cities(province: str = Query(...), db: Session = Depends(get_db)):
    rows = (
        db.query(PhAddress.city_municipality)
        .filter(PhAddress.province == province)
        .distinct()
        .order_by(PhAddress.city_municipality)
        .all()
    )
    return [r[0] for r in rows]


@router.get("/barangays", response_model=List[str])
def list_barangays(province: str = Query(...), city: str = Query(...), db: Session = Depends(get_db)):
    rows = (
        db.query(PhAddress.barangay)
        .filter(PhAddress.province == province, PhAddress.city_municipality == city)
        .order_by(PhAddress.barangay)
        .all()
    )
    return [r[0] for r in rows]
