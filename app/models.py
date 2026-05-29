"""
SQLAlchemy ORM models for WellSound.

Tables:
    users           — staff accounts (populated from Azure AD on first login)
    agencies        — water districts / organisations
    wells           — monitoring well records
    offsets         — reference point history per well
    measurements    — water level readings submitted by field staff
    wr_corrections  — Water Resources overrides on committed measurements
"""

from __future__ import annotations
import enum
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import (
    String, Integer, Float, Boolean, Date, DateTime,
    ForeignKey, Text, Enum as SAEnum, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    VIEWER   = "viewer"
    OPERATOR = "operator"
    SUPER    = "super"
    ADMIN    = "admin"


class WellStatus(str, enum.Enum):
    ACTIVE    = "active"
    INACTIVE  = "inactive"
    DESTROYED = "destroyed"
    DRAFT     = "draft"


class OffsetStatus(str, enum.Enum):
    ACTIVE        = "active"
    ABANDONED     = "abandoned"
    DESTROYED     = "destroyed"
    NOT_ACCESSIBLE = "not_accessible"
    TEMPORARY     = "temporary"


class ActivityType(str, enum.Enum):
    STATIC    = "Static"
    PUMPING   = "Pumping"
    INJECTING = "Injecting"


class MeasurementFocus(str, enum.Enum):
    ORIGINAL  = "original"
    SUPPRESSED = "suppressed"
    CORRECTED = "corrected"


class SubmissionStatus(str, enum.Enum):
    PENDING   = "pending"
    COMMITTED = "committed"
    CANCELLED = "cancelled"


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id:              Mapped[int]           = mapped_column(Integer, primary_key=True)
    azure_oid:       Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True)
    email:           Mapped[str]           = mapped_column(String(255), unique=True, index=True)
    username:        Mapped[str]           = mapped_column(String(100), unique=True, index=True)
    first_name:      Mapped[str]           = mapped_column(String(100))
    last_name:       Mapped[str]           = mapped_column(String(100))
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role:            Mapped[UserRole]      = mapped_column(SAEnum(UserRole), default=UserRole.OPERATOR)
    is_active:       Mapped[bool]          = mapped_column(Boolean, default=True)
    email_verified:  Mapped[bool]          = mapped_column(Boolean, default=False)
    created_at:      Mapped[datetime]      = mapped_column(DateTime, server_default=func.now())
    last_login:      Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    measurements:  Mapped[List["Measurement"]]  = relationship(back_populates="created_by_user")
    wr_corrections: Mapped[List["WRCorrection"]] = relationship(back_populates="corrected_by_user")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


# ── Agencies ──────────────────────────────────────────────────────────────────

class Agency(Base):
    __tablename__ = "agencies"

    id:            Mapped[int]           = mapped_column(Integer, primary_key=True)
    name:          Mapped[str]           = mapped_column(String(200), unique=True)
    contact_name:  Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(30),  nullable=True)
    address:       Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    state:         Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    zip_code:      Mapped[Optional[str]] = mapped_column(String(20),  nullable=True)
    created_at:    Mapped[datetime]      = mapped_column(DateTime, server_default=func.now())

    wells: Mapped[List["Well"]] = relationship(back_populates="agency")


# ── Wells ─────────────────────────────────────────────────────────────────────

class Well(Base):
    __tablename__ = "wells"

    id:                      Mapped[int]           = mapped_column(Integer, primary_key=True)
    name:                    Mapped[str]           = mapped_column(String(100), unique=True, index=True)
    agency_id:               Mapped[Optional[int]] = mapped_column(ForeignKey("agencies.id"), nullable=True)
    location:                Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    ground_surface_elevation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latitude:                Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude:               Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    screen_depth:            Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_depth:             Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    date_drilled:            Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status:                  Mapped[WellStatus]    = mapped_column(SAEnum(WellStatus), default=WellStatus.ACTIVE)
    comment:                 Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by:              Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at:              Mapped[datetime]      = mapped_column(DateTime, server_default=func.now())

    # Flag thresholds (stored per well)
    flag_sigma:          Mapped[float] = mapped_column(Float, default=2.0)
    flag_trend_dev:      Mapped[float] = mapped_column(Float, default=5.0)
    flag_use_sigma:      Mapped[bool]  = mapped_column(Boolean, default=True)
    flag_use_trend:      Mapped[bool]  = mapped_column(Boolean, default=True)

    agency:       Mapped[Optional["Agency"]]      = relationship(back_populates="wells")
    offsets:      Mapped[List["Offset"]]           = relationship(back_populates="well", order_by="Offset.date")
    measurements: Mapped[List["Measurement"]]      = relationship(back_populates="well", order_by="Measurement.measurement_date")


# ── Offsets (Reference Points) ────────────────────────────────────────────────

class Offset(Base):
    __tablename__ = "offsets"

    id:                Mapped[int]           = mapped_column(Integer, primary_key=True)
    well_id:           Mapped[int]           = mapped_column(ForeignKey("wells.id"), index=True)
    date:              Mapped[date]          = mapped_column(Date)
    ground_to_offset:  Mapped[float]         = mapped_column(Float)
    air_line_setting:  Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pump_depth:        Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    method:            Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status:            Mapped[OffsetStatus]  = mapped_column(SAEnum(OffsetStatus), default=OffsetStatus.ACTIVE)
    comment:           Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by:        Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at:        Mapped[datetime]      = mapped_column(DateTime, server_default=func.now())

    well: Mapped["Well"] = relationship(back_populates="offsets")


# ── Measurements ──────────────────────────────────────────────────────────────

class Measurement(Base):
    __tablename__ = "measurements"

    id:                  Mapped[int]              = mapped_column(Integer, primary_key=True)
    well_id:             Mapped[int]              = mapped_column(ForeignKey("wells.id"), index=True)
    offset_id:           Mapped[Optional[int]]    = mapped_column(ForeignKey("offsets.id"), nullable=True)
    measurement_date:    Mapped[date]             = mapped_column(Date, index=True)
    measurement_time:    Mapped[Optional[str]]    = mapped_column(String(10), nullable=True)  # "HH:MM"
    water_level:         Mapped[Optional[float]]  = mapped_column(Float, nullable=True)
    activity:            Mapped[ActivityType]     = mapped_column(SAEnum(ActivityType), default=ActivityType.STATIC)
    measurement_method:  Mapped[str]              = mapped_column(String(50))
    comments:            Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
    focus:               Mapped[MeasurementFocus] = mapped_column(SAEnum(MeasurementFocus), default=MeasurementFocus.ORIGINAL)
    status:              Mapped[SubmissionStatus] = mapped_column(SAEnum(SubmissionStatus), default=SubmissionStatus.COMMITTED)
    auto_commit_at:      Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    flags:               Mapped[Optional[str]]    = mapped_column(Text, nullable=True)  # JSON array of flag strings
    method_ack:          Mapped[bool]             = mapped_column(Boolean, default=False)
    flag_ack:            Mapped[bool]             = mapped_column(Boolean, default=False)
    created_by:          Mapped[Optional[int]]    = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at:        Mapped[datetime]         = mapped_column(DateTime, server_default=func.now())

    well:              Mapped["Well"]              = relationship(back_populates="measurements")
    created_by_user:   Mapped[Optional["User"]]   = relationship(back_populates="measurements")
    wr_correction:     Mapped[Optional["WRCorrection"]] = relationship(back_populates="measurement", uselist=False)


# ── WR Corrections ────────────────────────────────────────────────────────────

class WRCorrection(Base):
    __tablename__ = "wr_corrections"

    id:               Mapped[int]           = mapped_column(Integer, primary_key=True)
    measurement_id:   Mapped[int]           = mapped_column(ForeignKey("measurements.id"), unique=True, index=True)
    well_id:          Mapped[int]           = mapped_column(ForeignKey("wells.id"), index=True)

    # Corrected values — any field can be overridden
    activity:             Mapped[Optional[str]]   = mapped_column(String(20), nullable=True)
    water_level:          Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    measurement_method:   Mapped[Optional[str]]   = mapped_column(String(50), nullable=True)
    comments:             Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    reason:               Mapped[str]             = mapped_column(Text)

    corrected_by:  Mapped[int]      = mapped_column(ForeignKey("users.id"))
    corrected_at:  Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    measurement:        Mapped["Measurement"] = relationship(back_populates="wr_correction")
    corrected_by_user:  Mapped["User"]        = relationship(back_populates="wr_corrections")
