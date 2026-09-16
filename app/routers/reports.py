from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_player
from app.models import Player, Report
from app.schemas import REPORT_REASONS, ReportCreate, ReportOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportOut)
def report_player(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_player: Player = Depends(get_current_player),
):
    if current_player.id == payload.reported_id:
        raise HTTPException(status_code=400, detail="You can't report yourself")
    if payload.reason not in REPORT_REASONS:
        raise HTTPException(status_code=400, detail=f"reason must be one of: {', '.join(REPORT_REASONS)}")

    target = db.query(Player).filter(Player.id == payload.reported_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Player not found")

    report = Report(
        reporter_id=current_player.id,
        reported_id=payload.reported_id,
        reason=payload.reason,
        details=payload.details,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
