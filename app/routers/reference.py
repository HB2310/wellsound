from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_operator
from app.database import get_db
from app.models import Offset, Well, User
from app.schemas import OffsetCreate, OffsetOut

router = APIRouter(prefix="/api/reference", tags=["reference"])


@router.get("/{well_id}", response_model=List[OffsetOut])
def list_offsets(well_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Offset).filter(Offset.well_id == well_id).order_by(Offset.date.desc()).all()


@router.post("/{well_id}", response_model=OffsetOut, status_code=201)
def create_offset(
    well_id: int,
    payload: OffsetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    well = db.query(Well).filter(Well.id == well_id).first()
    if not well:
        raise HTTPException(404, "Well not found")
    offset = Offset(**payload.model_dump(), well_id=well_id, created_by=user.id)
    db.add(offset)
    db.commit()
    db.refresh(offset)
    return offset


@router.put("/{offset_id}", response_model=OffsetOut)
def update_offset(
    offset_id: int,
    payload: OffsetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    offset = db.query(Offset).filter(Offset.id == offset_id).first()
    if not offset:
        raise HTTPException(404, "Offset not found")
    for k, v in payload.model_dump().items():
        setattr(offset, k, v)
    db.commit()
    db.refresh(offset)
    return offset


@router.delete("/{offset_id}", status_code=204)
def delete_offset(offset_id: int, db: Session = Depends(get_db), user: User = Depends(require_operator)):
    offset = db.query(Offset).filter(Offset.id == offset_id).first()
    if not offset:
        raise HTTPException(404, "Offset not found")
    db.delete(offset)
    db.commit()
