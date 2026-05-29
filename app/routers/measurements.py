"""
Measurements router.

Key behaviours:
  - New submissions enter PENDING status with a 24-hour auto_commit_at timestamp
  - A background check (called on list) auto-commits any expired pending records
  - Flag evaluation runs server-side using the well's flag_sigma / flag_trend_dev config
  - 20-day edit rule: Operators may not edit/delete records older than 20 days
  - CSV export endpoint respects all filters
"""
from __future__ import annotations
import csv
import io
import json
import math
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_operator, require_super
from app.database import get_db
from app.models import Measurement, MeasurementFocus, SubmissionStatus, UserRole, Well, WellStatus, User
from app.schemas import MeasurementCreate, MeasurementOut, MeasurementUpdate

router = APIRouter(prefix="/api/measurements", tags=["measurements"])

EDIT_WINDOW_DAYS = 20


# ── Helpers ───────────────────────────────────────────────────────────────────

def _auto_commit(db: Session, well_id: Optional[int] = None):
    """Commit any pending measurements whose auto_commit_at has passed."""
    q = db.query(Measurement).filter(
        Measurement.status == SubmissionStatus.PENDING,
        Measurement.auto_commit_at <= datetime.utcnow(),
    )
    if well_id:
        q = q.filter(Measurement.well_id == well_id)
    for m in q.all():
        m.status = SubmissionStatus.COMMITTED
    db.commit()


def _check_edit_window(m: Measurement, user: User):
    if user.role == UserRole.OPERATOR:
        cutoff = date.today() - timedelta(days=EDIT_WINDOW_DAYS)
        if m.measurement_date < cutoff:
            raise HTTPException(403, f"Operators may only edit measurements within {EDIT_WINDOW_DAYS} days")


def _compute_flags(well: Well, value: float, activity: str, db: Session) -> List[str]:
    """Return list of flag strings for this value against well's historical static data."""
    if activity != "Static" or value is None:
        return []

    static_vals = [
        m.water_level for m in
        db.query(Measurement).filter(
            Measurement.well_id == well.id,
            Measurement.activity == "Static",
            Measurement.status == SubmissionStatus.COMMITTED,
            Measurement.water_level.isnot(None),
        ).all()
    ]
    if len(static_vals) < 3:
        return []

    flags = []
    n = len(static_vals)
    mean = sum(static_vals) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in static_vals) / n)

    if well.flag_use_sigma and std > 0:
        upper = mean + well.flag_sigma * std
        lower = mean - well.flag_sigma * std
        if value > upper or value < lower:
            flags.append(f"Outside ±{well.flag_sigma}σ range ({lower:.1f}–{upper:.1f} ft)")

    if well.flag_use_trend and n >= 4:
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = mean
        num = sum((xs[i] - mean_x) * (static_vals[i] - mean_y) for i in range(n))
        den = sum((x - mean_x) ** 2 for x in xs)
        slope = num / den if den else 0
        intercept = mean_y - slope * mean_x
        projected = slope * n + intercept
        if abs(value - projected) > well.flag_trend_dev:
            flags.append(f"Deviates >{well.flag_trend_dev} ft from trend projection ({projected:.1f} ft)")

    return flags


def _enrich(m: Measurement, db: Session) -> MeasurementOut:
    """Attach operator name and WR correction name to output."""
    out = MeasurementOut.model_validate(m)
    if m.created_by:
        u = db.get(User, m.created_by)
        out.operator_name = u.full_name if u else None
    if m.wr_correction and m.wr_correction.corrected_by:
        u = db.get(User, m.wr_correction.corrected_by)
        if out.wr_correction:
            out.wr_correction.corrector_name = u.full_name if u else None
    return out


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[MeasurementOut])
def list_measurements(
    well_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if well_id:
        _auto_commit(db, well_id)

    q = (db.query(Measurement)
         .options(joinedload(Measurement.wr_correction))
         .filter(Measurement.status != SubmissionStatus.CANCELLED))

    if user.role == UserRole.VIEWER:
        q = q.filter(Measurement.focus != MeasurementFocus.SUPPRESSED)

    if well_id:
        q = q.filter(Measurement.well_id == well_id)
    if status:
        q = q.filter(Measurement.status == status)
    if from_date:
        q = q.filter(Measurement.measurement_date >= from_date)
    if to_date:
        q = q.filter(Measurement.measurement_date <= to_date)

    return [_enrich(m, db) for m in q.order_by(Measurement.measurement_date.asc()).all()]


@router.get("/export-csv")
def export_csv(
    well_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = list_measurements(well_id=well_id, status=status, from_date=from_date, to_date=to_date, db=db, user=user)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Well ID", "Date", "Time", "Operator", "Activity",
        "Water Level (ft bgs)", "Method", "Status", "Focus",
        "Flags", "Method Ack", "Flag Ack", "Comments", "Submitted At",
        "WR Activity", "WR Water Level", "WR Method", "WR Comments", "WR Reason", "WR Corrected By",
    ])
    for m in rows:
        wr = m.wr_correction
        writer.writerow([
            m.id, m.well_id, m.measurement_date, m.measurement_time or "",
            m.operator_name or "", m.activity, m.water_level or "",
            m.measurement_method, m.status, m.focus,
            m.flags or "", m.method_ack, m.flag_ack, m.comments or "",
            m.submitted_at,
            wr.activity if wr else "", wr.water_level if wr else "",
            wr.measurement_method if wr else "", wr.comments if wr else "",
            wr.reason if wr else "", wr.corrector_name if wr else "",
        ])

    output.seek(0)
    filename = f"wellsound_measurements_{date.today()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{measurement_id}", response_model=MeasurementOut)
def get_measurement(measurement_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = db.query(Measurement).options(joinedload(Measurement.wr_correction)).filter(Measurement.id == measurement_id).first()
    if not m:
        raise HTTPException(404, "Measurement not found")
    return _enrich(m, db)


@router.post("", response_model=MeasurementOut, status_code=201)
def create_measurement(
    payload: MeasurementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    well = db.query(Well).filter(Well.id == payload.well_id, Well.status == WellStatus.ACTIVE).first()
    if not well:
        raise HTTPException(404, "Active well not found")

    flags = _compute_flags(well, payload.water_level or 0, payload.activity, db)

    m = Measurement(
        **payload.model_dump(exclude={"flags"}),
        flags=json.dumps(flags) if flags else None,
        focus=MeasurementFocus.ORIGINAL,
        status=SubmissionStatus.PENDING,
        auto_commit_at=datetime.utcnow() + timedelta(hours=24),
        created_by=user.id,
        submitted_at=datetime.utcnow(),
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return _enrich(m, db)


@router.put("/{measurement_id}", response_model=MeasurementOut)
def update_measurement(
    measurement_id: int,
    payload: MeasurementUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    m = db.query(Measurement).filter(Measurement.id == measurement_id).first()
    if not m:
        raise HTTPException(404, "Measurement not found")
    _check_edit_window(m, user)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return _enrich(m, db)


@router.delete("/{measurement_id}", status_code=204)
def delete_measurement(
    measurement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    m = db.query(Measurement).filter(Measurement.id == measurement_id).first()
    if not m:
        raise HTTPException(404, "Measurement not found")
    _check_edit_window(m, user)
    m.status = SubmissionStatus.CANCELLED
    db.commit()


@router.post("/{measurement_id}/cancel", status_code=204)
def cancel_measurement(
    measurement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    m = db.query(Measurement).filter(
        Measurement.id == measurement_id,
        Measurement.status == SubmissionStatus.PENDING,
    ).first()
    if not m:
        raise HTTPException(404, "Pending measurement not found")
    if user.role == UserRole.OPERATOR and m.created_by != user.id:
        raise HTTPException(403, "Can only cancel your own submissions")
    m.status = SubmissionStatus.CANCELLED
    db.commit()
