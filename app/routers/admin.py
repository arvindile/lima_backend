from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models import Player, Report, ReportStatus
from app.schemas import PlayerOut, ReportOut

router = APIRouter(prefix="/admin", tags=["admin"])

# Everything in this router is a deliberately minimal stopgap — a single
# shared secret (see app/dependencies.py:require_admin), not a real admin
# panel or role system. Meant to be used from Postman/curl with the
# X-Admin-Key header until an actual admin UI exists. Every endpoint here
# is gated the same way.


@router.get("/reports", response_model=List[ReportOut], dependencies=[Depends(require_admin)])
def list_reports(db: Session = Depends(get_db), status: str = "OPEN"):
    query = db.query(Report)
    if status:
        query = query.filter(Report.status == status)
    return query.order_by(Report.created_at.desc()).all()


@router.post("/reports/{report_id}/resolve", response_model=ReportOut, dependencies=[Depends(require_admin)])
def resolve_report(report_id: str, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report.status = ReportStatus.RESOLVED
    db.commit()
    db.refresh(report)
    return report


@router.post("/reports/{report_id}/dismiss", response_model=ReportOut, dependencies=[Depends(require_admin)])
def dismiss_report(report_id: str, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report.status = ReportStatus.DISMISSED
    db.commit()
    db.refresh(report)
    return report


@router.post("/players/{player_id}/ban", response_model=PlayerOut, dependencies=[Depends(require_admin)])
def ban_player(player_id: str, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    player.is_banned = True
    db.commit()
    db.refresh(player)
    return player


@router.post("/players/{player_id}/unban", response_model=PlayerOut, dependencies=[Depends(require_admin)])
def unban_player(player_id: str, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    player.is_banned = False
    db.commit()
    db.refresh(player)
    return player
