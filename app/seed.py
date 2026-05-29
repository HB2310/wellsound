"""
Seed data — loads mock wells, offsets, and measurements on first run.
Only runs when the wells table is empty.
"""
from datetime import date, datetime, timedelta
from app.database import SessionLocal
from app.models import (
    Agency, Well, Offset, Measurement, User,
    WellStatus, OffsetStatus, ActivityType, MeasurementFocus, SubmissionStatus, UserRole
)

MOCK_MEASUREMENTS = {
    "MW-01": [
        ("2023-05", "09:15", 143.0, None, "Electric wire"),
        ("2023-07", "10:00", 141.8, 182.0, "Electric wire"),
        ("2023-09", "08:55", 143.4, None, "Electric wire"),
        ("2023-10", "09:10", 141.8, 185.2, "Electric wire"),
        ("2023-12", "09:05", 139.2, 183.1, "Electric wire"),
        ("2024-01", "08:40", 138.7, None, "Electric wire"),
        ("2024-02", "09:50", 137.9, 182.4, "Electric wire"),
        ("2024-04", "09:00", 140.3, 184.0, "Electric wire"),
        ("2024-06", "09:45", 141.5, None, "Electric wire"),
        ("2024-08", "09:20", 142.1, None, "Electric wire"),
        ("2024-10", "09:35", 141.8, 185.2, "Electric wire"),
        ("2024-12", "09:00", 139.2, 183.1, "Electric wire"),
        ("2025-02", "09:55", 137.9, 182.4, "Electric wire"),
        ("2025-04", "09:10", 140.3, 184.0, "Electric wire"),
        ("2025-05", "08:35", 141.2, None, "Electric wire"),
    ],
    "MW-02": [
        ("2023-08", "09:15", 95.3, None, "Air"),
        ("2023-10", "09:30", 94.8, 132.0, "Air"),
        ("2023-12", "09:00", 92.4, None, "Air"),
        ("2024-02", "09:45", 90.7, 130.5, "Air"),
        ("2024-04", "09:20", 93.2, 131.8, "Air"),
        ("2024-06", "08:35", 94.0, None, "Air"),
        ("2024-08", "09:10", 95.3, None, "Air"),
        ("2024-10", "09:25", 94.8, 132.0, "Air"),
        ("2024-12", "09:50", 92.4, None, "Air"),
        ("2025-02", "09:00", 90.7, 130.5, "Air"),
        ("2025-04", "09:40", 93.2, 131.8, "Air"),
        ("2025-05", "10:05", 94.0, None, "Air"),
    ],
    "MW-03": [
        ("2023-08", "09:15", 201.0, None, "SCADA"),
        ("2023-10", "09:30", 200.5, None, "SCADA"),
        ("2023-12", "09:10", 198.0, None, "SCADA"),
        ("2024-02", "09:55", 196.8, None, "SCADA"),
        ("2024-04", "09:05", 199.5, None, "SCADA"),
        ("2024-06", "08:30", 200.1, None, "SCADA"),
        ("2024-08", "09:45", 201.0, None, "SCADA"),
        ("2024-10", "09:20", 200.5, None, "SCADA"),
        ("2024-12", "09:35", 198.0, None, "SCADA"),
        ("2025-02", "09:00", 196.8, None, "SCADA"),
        ("2025-04", "09:50", 199.5, None, "SCADA"),
        ("2025-05", "10:15", 200.1, None, "SCADA"),
    ],
    "MW-04": [
        ("2023-08", "09:00", 78.4, None, "Electric wire"),
        ("2023-10", "08:45", 77.9, None, "Electric wire"),
        ("2024-01", "09:15", 76.5, None, "Electric wire"),
        ("2024-06", "10:00", 77.2, None, "Electric wire"),
    ],
    "MW-05": [
        ("2023-08", "08:50", 165.2, 210.3, "Transducer"),
        ("2023-10", "10:05", 163.5, 208.4, "Transducer"),
        ("2023-12", "08:40", 161.4, 206.5, "Transducer"),
        ("2024-02", "10:20", 159.8, 204.7, "Transducer"),
        ("2024-04", "08:35", 162.5, 207.3, "Transducer"),
        ("2024-06", "09:50", 163.8, 208.6, "Transducer"),
        ("2024-08", "10:10", 165.2, 210.3, "Transducer"),
        ("2024-10", "08:45", 163.5, 208.4, "Transducer"),
        ("2024-12", "10:00", 161.4, 206.5, "Transducer"),
        ("2025-02", "08:30", 159.8, 204.7, "Transducer"),
        ("2025-04", "10:05", 162.5, 207.3, "Transducer"),
        ("2025-05", "09:20", 163.8, 208.6, "Transducer"),
    ],
}

WELLS_META = {
    "MW-01": {"loc": "North Basin",  "gse": 1250.5, "lat": 34.052, "lon": -118.243, "status": WellStatus.ACTIVE,   "sigma": 2.0, "trend": 5.0},
    "MW-02": {"loc": "South Basin",  "gse": 1248.3, "lat": 34.048, "lon": -118.250, "status": WellStatus.ACTIVE,   "sigma": 2.0, "trend": 4.0},
    "MW-03": {"loc": "East Margin",  "gse": 1255.0, "lat": 34.055, "lon": -118.235, "status": WellStatus.ACTIVE,   "sigma": 2.0, "trend": 3.0},
    "MW-04": {"loc": "West Sector",  "gse": 1244.0, "lat": 34.050, "lon": -118.260, "status": WellStatus.INACTIVE, "sigma": 2.0, "trend": 5.0},
    "MW-05": {"loc": "Central",      "gse": 1260.2, "lat": 34.053, "lon": -118.245, "status": WellStatus.ACTIVE,   "sigma": 2.0, "trend": 6.0},
}

OFFSETS = {
    "MW-01": [("2020-05-16", 2.5, 85.0, 150.0, "Electric wire"), ("2022-03-10", 2.5, 85.0, 152.0, "Electric wire")],
    "MW-02": [("2020-06-21", 2.3, 60.0, 130.0, "Air")],
    "MW-03": [("2020-05-20", 3.1, 120.0, 200.0, "SCADA")],
    "MW-04": [("2020-04-10", 2.1, 45.0, 110.0, "Electric wire")],
    "MW-05": [("2020-07-01", 2.8, 100.0, 175.0, "Transducer")],
}


def seed_if_empty():
    db = SessionLocal()
    try:
        if db.query(Well).count() > 0:
            print("[seed] Database already has wells — skipping seed")
            return

        print("[seed] Loading mock data...")

        # Admin user
        admin = User(
            email="admin@wellsound.local",
            username="admin",
            first_name="System",
            last_name="Admin",
            role=UserRole.ADMIN,
            is_active=True,
            email_verified=True,
        )
        db.add(admin)
        db.flush()

        # Agency
        agency = Agency(name="Sample Water District", state="California")
        db.add(agency)
        db.flush()

        # Wells
        well_map = {}
        offset_map = {}

        for name, meta in WELLS_META.items():
            well = Well(
                name=name,
                location=meta["loc"],
                ground_surface_elevation=meta["gse"],
                latitude=meta["lat"],
                longitude=meta["lon"],
                status=meta["status"],
                agency_id=agency.id,
                created_by=admin.id,
                flag_sigma=meta["sigma"],
                flag_trend_dev=meta["trend"],
            )
            db.add(well)
            db.flush()
            well_map[name] = well

            # Offsets
            for off_date, gto, airline, pump, method in OFFSETS.get(name, []):
                y, m, d = map(int, off_date.split("-"))
                off = Offset(
                    well_id=well.id,
                    date=date(y, m, d),
                    ground_to_offset=gto,
                    air_line_setting=airline,
                    pump_depth=pump,
                    method=method,
                    status=OffsetStatus.ACTIVE,
                    created_by=admin.id,
                )
                db.add(off)
                db.flush()
                offset_map[name] = off  # keep last for FK

        # Measurements
        for well_name, records in MOCK_MEASUREMENTS.items():
            well = well_map[well_name]
            offset = offset_map.get(well_name)
            for ym, t, static_val, pump_val, method in records:
                y, m = map(int, ym.split("-"))
                meas_date = date(y, m, 15)
                for activity, value in [("Static", static_val), ("Pumping", pump_val)]:
                    if value is None:
                        continue
                    meas = Measurement(
                        well_id=well.id,
                        offset_id=offset.id if offset else None,
                        measurement_date=meas_date,
                        measurement_time=t,
                        water_level=value,
                        activity=activity,
                        measurement_method=method,
                        focus=MeasurementFocus.ORIGINAL,
                        status=SubmissionStatus.COMMITTED,
                        created_by=admin.id,
                        submitted_at=datetime(y, m, 15, int(t.split(":")[0]), int(t.split(":")[1])),
                    )
                    db.add(meas)

        db.commit()
        print(f"[seed] Done — {len(WELLS_META)} wells, measurements loaded")

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
