from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Well, WellStatus, UserRole
from app.schemas import WellCreate, WellOut, WellSummary
from app.auth import get_current_user, require_operator, require_super, require_admin
from app.models import User

router = APIRouter(prefix="/api/wells", tags=["wells"])


@router.get("", response_model=List[WellSummary])
def list_wells(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Well).filter(Well.status != WellStatus.DESTROYED)
    if user.role in (UserRole.VIEWER, UserRole.OPERATOR):
        q = q.filter(Well.status == WellStatus.ACTIVE)
    if status:
        q = q.filter(Well.status == status)
    return q.order_by(Well.name).all()


@router.get("/{well_id}", response_model=WellOut)
def get_well(well_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    well = db.query(Well).filter(Well.id == well_id, Well.status != WellStatus.DESTROYED).first()
    if not well:
        raise HTTPException(404, "Well not found")
    return well


@router.post("", response_model=WellOut, status_code=201)
def create_well(payload: WellCreate, db: Session = Depends(get_db), user: User = Depends(require_operator)):
    well_status = WellStatus.ACTIVE if user.role in (UserRole.SUPER, UserRole.ADMIN) else WellStatus.DRAFT
    well = Well(**payload.model_dump(), status=well_status, created_by=user.id)
    db.add(well)
    db.commit()
    db.refresh(well)
    return well


@router.put("/{well_id}", response_model=WellOut)
def update_well(well_id: int, payload: WellCreate, db: Session = Depends(get_db), user: User = Depends(require_super)):
    well = db.query(Well).filter(Well.id == well_id).first()
    if not well:
        raise HTTPException(404, "Well not found")
    for k, v in payload.model_dump().items():
        setattr(well, k, v)
    db.commit()
    db.refresh(well)
    return well


@router.post("/{well_id}/approve", response_model=WellOut)
def approve_well(well_id: int, db: Session = Depends(get_db), user: User = Depends(require_super)):
    well = db.query(Well).filter(Well.id == well_id, Well.status == WellStatus.DRAFT).first()
    if not well:
        raise HTTPException(404, "Draft well not found")
    well.status = WellStatus.ACTIVE
    db.commit()
    db.refresh(well)
    return well


@router.delete("/{well_id}", status_code=204)
def delete_well(well_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    well = db.query(Well).filter(Well.id == well_id).first()
    if not well:
        raise HTTPException(404, "Well not found")
    db.delete(well)
    db.commit()
