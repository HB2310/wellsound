"""
Pydantic schemas for request validation and API responses.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr


# ── Users ─────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    username: str
    first_name: str
    last_name: str
    full_name: str
    role: str
    is_active: bool


# ── Wells ─────────────────────────────────────────────────────────────────────

class WellCreate(BaseModel):
    name: str
    location: Optional[str] = None
    ground_surface_elevation: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    screen_depth: Optional[float] = None
    total_depth: Optional[float] = None
    date_drilled: Optional[date] = None
    comment: Optional[str] = None
    agency_id: Optional[int] = None
    flag_sigma: float = 2.0
    flag_trend_dev: float = 5.0
    flag_use_sigma: bool = True
    flag_use_trend: bool = True


class WellOut(WellCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    created_at: datetime


class WellSummary(BaseModel):
    """Lightweight well list for sidebar."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    location: Optional[str]
    status: str
    ground_surface_elevation: Optional[float]
    latitude: Optional[float]
    longitude: Optional[float]
    flag_sigma: float
    flag_trend_dev: float
    flag_use_sigma: bool
    flag_use_trend: bool


# ── Offsets ───────────────────────────────────────────────────────────────────

class OffsetCreate(BaseModel):
    date: date
    ground_to_offset: float
    air_line_setting: Optional[float] = None
    pump_depth: Optional[float] = None
    method: Optional[str] = None
    status: str = "active"
    comment: Optional[str] = None


class OffsetOut(OffsetCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    well_id: int
    created_at: datetime
    created_by: Optional[int]


# ── Measurements ──────────────────────────────────────────────────────────────

class MeasurementCreate(BaseModel):
    well_id: int
    offset_id: Optional[int] = None
    measurement_date: date
    measurement_time: Optional[str] = None
    water_level: Optional[float] = None
    activity: str = "Static"
    measurement_method: str
    comments: Optional[str] = None
    method_ack: bool = False
    flag_ack: bool = False
    flags: Optional[str] = None  # JSON string


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    well_id: int
    offset_id: Optional[int]
    measurement_date: date
    measurement_time: Optional[str]
    water_level: Optional[float]
    activity: str
    measurement_method: str
    comments: Optional[str]
    focus: str
    status: str
    flags: Optional[str]
    method_ack: bool
    flag_ack: bool
    submitted_at: datetime
    auto_commit_at: Optional[datetime]
    created_by: Optional[int]
    operator_name: Optional[str] = None
    wr_correction: Optional["WRCorrectionOut"] = None


class MeasurementUpdate(BaseModel):
    measurement_date: Optional[date] = None
    measurement_time: Optional[str] = None
    water_level: Optional[float] = None
    activity: Optional[str] = None
    measurement_method: Optional[str] = None
    comments: Optional[str] = None


# ── WR Corrections ────────────────────────────────────────────────────────────

class WRCorrectionCreate(BaseModel):
    activity: Optional[str] = None
    water_level: Optional[float] = None
    measurement_method: Optional[str] = None
    comments: Optional[str] = None
    reason: str


class WRCorrectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    measurement_id: int
    well_id: int
    activity: Optional[str]
    water_level: Optional[float]
    measurement_method: Optional[str]
    comments: Optional[str]
    reason: str
    corrected_by: int
    corrected_at: datetime
    corrector_name: Optional[str] = None


# Update forward ref
MeasurementOut.model_rebuild()
