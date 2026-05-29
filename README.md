[README.md](https://github.com/user-attachments/files/28408478/README.md)
# WellSound

Groundwater monitoring data entry and management system for Elsinore Valley Municipal Water District.

Built for internal use — runs entirely on a local office network, no internet required, no cloud dependency.

---

## What it does

- Field operators log monthly water level measurements from a browser on any office computer
- Real-time chart shows historical data while the operator is entering a new reading — so errors are caught before submission
- Automatic flagging when a value is outside the normal range (±2σ) or deviates from the trend
- Method-change detection with required acknowledgement
- 24-hour pending window — submissions can be cancelled before they auto-commit
- Water Resources staff can add corrections to committed measurements without altering the original record
- Full measurement history with filtering, drill-down modal, and CSV export
- Reference information tracking per well (air line setting, pump depth, offset distance)
- Role-based access: Viewer, Operator, Super, Admin
- Microsoft Azure AD OAuth login — staff use their existing work credentials

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 · FastAPI · Uvicorn |
| Database | PostgreSQL |
| ORM | SQLAlchemy 2.0 |
| Auth | Microsoft OAuth (Azure AD) · JWT cookies |
| Frontend | Single HTML file — no build step, no framework |
| Web server | Nginx (reverse proxy) |
| OS | Ubuntu 22.04 LTS |

---

## Project structure

```
wellsound/
├── app/
│   ├── main.py              # FastAPI app entry point, startup lifecycle
│   ├── config.py            # Settings loaded from .env
│   ├── database.py          # PostgreSQL connection, SQLAlchemy engine
│   ├── models.py            # All database tables (ORM models)
│   ├── schemas.py           # Pydantic request/response models
│   ├── auth.py              # Microsoft OAuth flow + JWT session handling
│   ├── seed.py              # Loads mock well data on first run
│   └── routers/
│       ├── wells.py         # Well CRUD + approval workflow
│       ├── measurements.py  # Measurements, flag logic, auto-commit, CSV export
│       ├── corrections.py   # WR corrections (Admin only)
│       ├── reference.py     # Reference info / offsets per well
│       └── users.py         # User management
├── static/
│   └── index.html           # Entire frontend — served directly by FastAPI
├── .env.example             # All config variables documented
├── requirements.txt         # Python dependencies
├── nginx.conf               # Drop-in Nginx config for local deployment
├── wellsound.service        # systemd unit file — auto-starts on server boot
└── DEPLOY.md                # Full step-by-step Linux deployment guide
```

---

## Roles

| Role | Permissions |
|---|---|
| Viewer | Read-only access to committed measurements |
| Operator | Submit measurements, cancel own pending submissions within 20 days |
| Super | All operator permissions + approve wells, cancel any pending submission |
| Admin | All super permissions + WR corrections, user management |

New users who sign in via Microsoft OAuth are created with Operator role by default. An Admin can promote them via the users API.

---

## Database tables

| Table | Purpose |
|---|---|
| `users` | Staff accounts — populated from Azure AD on first login |
| `agencies` | Water districts / organisations |
| `wells` | Monitoring well records with per-well flag thresholds |
| `offsets` | Reference point history per well (air line, pump depth, offset distance) |
| `measurements` | Water level readings — status: pending → committed or cancelled |
| `wr_corrections` | Water Resources overrides on committed measurements, linked by measurement ID |

---

## Quick start (local development)

```bash
# 1. Clone and create virtual environment
git clone https://github.com/your-org/wellsound.git
cd wellsound
python3.11 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY, and Azure credentials
# For local dev without Azure, leave AZURE_CLIENT_ID empty to use mock login

# 4. Start PostgreSQL and create the database
createdb wellsound

# 5. Run the app
uvicorn app.main:app --reload
```

App runs at `http://localhost:8000`. On first start, tables are created and mock well data is loaded automatically if `LOAD_SEED_DATA=true` in `.env`.

---

## Configuration

All configuration is set in `.env`. Copy `.env.example` and fill in the values.

```env
# Required
DATABASE_URL=postgresql://wellsound:password@localhost:5432/wellsound
SECRET_KEY=generate_with_python_secrets_token_hex_32

# Microsoft OAuth (leave blank to use mock login for development)
AZURE_CLIENT_ID=your-azure-app-client-id
AZURE_CLIENT_SECRET=your-azure-app-client-secret
AZURE_TENANT_ID=your-azure-tenant-id
AZURE_REDIRECT_URI=http://192.168.1.50/auth/callback

# Seed mock data on first run
LOAD_SEED_DATA=true
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Azure AD setup (for production login)

1. Go to **portal.azure.com** → Azure Active Directory → App registrations → New registration
2. Name: `WellSound` · Supported account types: this org only
3. Redirect URI: `http://YOUR_SERVER_IP/auth/callback`
4. Copy **Application (client) ID** → `AZURE_CLIENT_ID`
5. Copy **Directory (tenant) ID** → `AZURE_TENANT_ID`
6. Certificates & secrets → New client secret → copy value → `AZURE_CLIENT_SECRET`
7. API permissions → Add → Microsoft Graph → Delegated → `User.Read`, `openid`, `profile`, `email` → Grant admin consent

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/auth/login` | Redirect to Microsoft login |
| GET | `/auth/callback` | OAuth callback — creates session cookie |
| POST | `/auth/mock-login-json` | Dev-only login (when no Azure configured) |
| POST | `/auth/logout` | Clear session cookie |
| GET | `/auth/me` | Current user info |
| GET | `/api/wells` | List all active wells |
| POST | `/api/wells` | Create a new well |
| GET | `/api/measurements` | List measurements (filterable by well, status, date) |
| POST | `/api/measurements` | Submit a new measurement (server-side flag evaluation) |
| POST | `/api/measurements/{id}/cancel` | Cancel a pending submission |
| GET | `/api/measurements/export-csv` | Export filtered measurements as CSV |
| POST | `/api/corrections/{measurement_id}` | Add/update WR correction (Admin only) |
| DELETE | `/api/corrections/{measurement_id}` | Remove WR correction (Admin only) |
| GET | `/api/reference/{well_id}` | Get reference info history for a well |
| POST | `/api/reference/{well_id}` | Save new reference data entry |
| GET | `/api/users` | List all users (Super/Admin only) |
| PUT | `/api/users/{id}/role` | Change a user's role (Admin only) |

Full interactive docs available at `/docs` when `DEBUG=true` in `.env`.

---

## Deployment

See **DEPLOY.md** for the full step-by-step guide covering:

- Ubuntu 22.04 setup
- PostgreSQL installation and database creation
- Python virtual environment and dependency installation
- `.env` configuration
- Azure AD app registration
- Database initialisation and seed data
- systemd service setup (auto-start on boot)
- Nginx configuration
- Sharing the app URL with office staff
- Backup and maintenance commands
- Troubleshooting common issues

---

