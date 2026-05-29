from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_admin, get_current_user
from app.database import get_db
from app.models import Measurement, WRCorrection, SubmissionStatus, User
from app.schemas import WRCorrectionCreate, WRCorrectionOut

router = APIRouter(prefix="/api/corrections", tags=["corrections"])


@router.post("/{measurement_id}", response_model=WRCorrectionOut, status_code=201)
def upsert_correction(
    measurement_id: int,
    payload: WRCorrectionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    m = db.query(Measurement).filter(
        Measurement.id == measurement_id,
        Measurement.status == SubmissionStatus.COMMITTED,
    ).first()
    if not m:
        raise HTTPException(404, "Committed measurement not found")

    existing = db.query(WRCorrection).filter(WRCorrection.measurement_id == measurement_id).first()
    if existing:
        for k, v in payload.model_dump(exclude_none=True).items():
            setattr(existing, k, v)
        existing.corrected_by = user.id
        db.commit()
        db.refresh(existing)
        wr = existing
    else:
        wr = WRCorrection(
            measurement_id=measurement_id,
            well_id=m.well_id,
            corrected_by=user.id,
            **payload.model_dump(),
        )
        db.add(wr)
        db.commit()
        db.refresh(wr)

    out = WRCorrectionOut.model_validate(wr)
    corrector = db.get(User, wr.corrected_by)
    out.corrector_name = corrector.full_name if corrector else None
    return out


@router.delete("/{measurement_id}", status_code=204)
def delete_correction(
    measurement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    wr = db.query(WRCorrection).filter(WRCorrection.measurement_id == measurement_id).first()
    if not wr:
        raise HTTPException(404, "Correction not found")
    db.delete(wr)
    db.commit()
