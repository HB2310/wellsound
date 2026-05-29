# WellSound — Deployment Guide (Linux / Ubuntu)

This guide takes you from a fresh Ubuntu server to a fully running WellSound instance.
Estimated time: **2–4 hours** for someone comfortable with a terminal.

---

## Prerequisites

- Ubuntu 22.04 LTS server (physical machine, VM, or mini PC)
- Static local IP assigned by your router or IT (e.g. `192.168.1.50`)
- SSH access or keyboard/monitor on the machine
- Internet access during setup (only for installing packages)

---

## Step 1 — Update the system

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget build-essential
```

---

## Step 2 — Install Python 3.11

```bash
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
python3.11 --version   # should print Python 3.11.x
```

---

## Step 3 — Install PostgreSQL

```bash
sudo apt install -y postgresql postgresql-contrib

# Start and enable PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create the database and user
sudo -u postgres psql << 'SQL'
CREATE USER wellsound WITH PASSWORD 'change_this_password';
CREATE DATABASE wellsound OWNER wellsound;
GRANT ALL PRIVILEGES ON DATABASE wellsound TO wellsound;
SQL
```

---

## Step 4 — Install Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
```

---

## Step 5 — Create application user and directory

```bash
# Create a dedicated system user (no login shell for security)
sudo useradd -r -s /bin/false wellsound

# Create app directory
sudo mkdir -p /opt/wellsound
sudo chown wellsound:wellsound /opt/wellsound
```

---

## Step 6 — Deploy the application

```bash
# Copy your wellsound project folder to the server
# Option A: from local machine via scp
scp -r ./wellsound/ youruser@192.168.1.50:/tmp/wellsound

# Option B: clone from git (if you have a repo)
# git clone https://your-repo-url /tmp/wellsound

# Move to the app directory
sudo cp -r /tmp/wellsound/* /opt/wellsound/
sudo chown -R wellsound:wellsound /opt/wellsound/
```

---

## Step 7 — Create virtual environment and install dependencies

```bash
cd /opt/wellsound

# Create venv as the wellsound user
sudo -u wellsound python3.11 -m venv venv

# Install dependencies
sudo -u wellsound /opt/wellsound/venv/bin/pip install --upgrade pip
sudo -u wellsound /opt/wellsound/venv/bin/pip install -r requirements.txt
```

---

## Step 8 — Configure the application

```bash
# Copy the example env file
sudo cp /opt/wellsound/.env.example /opt/wellsound/.env
sudo chown wellsound:wellsound /opt/wellsound/.env
sudo chmod 600 /opt/wellsound/.env   # Only owner can read

# Edit the config
sudo nano /opt/wellsound/.env
```

Update these values in `.env`:

```env
# Your PostgreSQL password from Step 3
DATABASE_URL=postgresql://wellsound:change_this_password@localhost:5432/wellsound

# Generate a real secret key:
# python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=paste_your_generated_key_here

# Microsoft OAuth (see Step 9 below)
AZURE_CLIENT_ID=your-azure-client-id
AZURE_CLIENT_SECRET=your-azure-client-secret
AZURE_TENANT_ID=your-azure-tenant-id
AZURE_REDIRECT_URI=http://192.168.1.50/auth/callback   # ← your server's LAN IP

LOAD_SEED_DATA=true
```

---

## Step 9 — Set up Microsoft OAuth (Azure AD)

> Skip this step if using mock login for now. Set AZURE_CLIENT_ID to empty string in .env.

1. Go to **portal.azure.com** → Azure Active Directory → App registrations → New registration
2. Name: `WellSound`
3. Supported account types: **Accounts in this organizational directory only**
4. Redirect URI: `http://192.168.1.50/auth/callback` (your server's LAN IP)
5. Click **Register**
6. Copy the **Application (client) ID** → paste as `AZURE_CLIENT_ID` in `.env`
7. Copy the **Directory (tenant) ID** → paste as `AZURE_TENANT_ID` in `.env`
8. Go to **Certificates & secrets** → New client secret → Copy value → paste as `AZURE_CLIENT_SECRET`
9. Go to **API permissions** → Add permission → Microsoft Graph → Delegated → add: `User.Read`, `openid`, `profile`, `email`
10. Click **Grant admin consent**

> **Important:** The redirect URI in Azure must exactly match `AZURE_REDIRECT_URI` in your `.env`.

---

## Step 10 — Initialize the database and load seed data

```bash
cd /opt/wellsound
sudo -u wellsound /opt/wellsound/venv/bin/python -c "
from app.database import init_db
from app.seed import seed_if_empty
init_db()
seed_if_empty()
print('Database ready')
"
```

---

## Step 11 — Install and start the systemd service

```bash
# Copy the service file
sudo cp /opt/wellsound/wellsound.service /etc/systemd/system/

# Reload systemd and enable
sudo systemctl daemon-reload
sudo systemctl enable wellsound
sudo systemctl start wellsound

# Check it's running
sudo systemctl status wellsound

# View live logs
sudo journalctl -u wellsound -f
```

---

## Step 12 — Configure Nginx

```bash
# Copy the nginx config
sudo cp /opt/wellsound/nginx.conf /etc/nginx/sites-available/wellsound

# Enable the site
sudo ln -s /etc/nginx/sites-available/wellsound /etc/nginx/sites-enabled/

# Remove default site
sudo rm -f /etc/nginx/sites-enabled/default

# Test config and reload
sudo nginx -t
sudo systemctl reload nginx
```

---

## Step 13 — Test it

On any computer on the same office network, open a browser and go to:

```
http://192.168.1.50
```

You should see the WellSound login screen.

---

## Step 14 — Set up mock users (for testing before OAuth is live)

If OAuth is not configured yet, mock login is available. Add users to the database:

```bash
sudo -u wellsound /opt/wellsound/venv/bin/python << 'EOF'
from app.database import SessionLocal
from app.models import User, UserRole

db = SessionLocal()

users = [
    User(email="joe@example.com",  username="joe",  first_name="Joe",  last_name="Smith",  role=UserRole.OPERATOR, is_active=True),
    User(email="mike@example.com", username="mike", first_name="Mike", last_name="Wilson", role=UserRole.OPERATOR, is_active=True),
    User(email="paul@example.com", username="paul", first_name="Paul", last_name="Johnson",role=UserRole.OPERATOR, is_active=True),
    User(email="lisa@example.com", username="lisa", first_name="Lisa", last_name="Brown",  role=UserRole.SUPER,    is_active=True),
    User(email="tom@example.com",  username="tom",  first_name="Tom",  last_name="Davis",  role=UserRole.ADMIN,    is_active=True),
]

for u in users:
    if not db.query(User).filter(User.username==u.username).first():
        db.add(u)

db.commit()
print("Users created")
db.close()
EOF
```

---

## Maintenance Commands

```bash
# Restart the app (after updates)
sudo systemctl restart wellsound

# View logs
sudo journalctl -u wellsound -n 100

# Update the application
cd /opt/wellsound
sudo -u wellsound git pull          # if using git
sudo systemctl restart wellsound

# Backup the database
sudo -u postgres pg_dump wellsound > wellsound_backup_$(date +%Y%m%d).sql

# Restore from backup
sudo -u postgres psql wellsound < wellsound_backup_20260519.sql
```

---

## Troubleshooting

**App won't start:**
```bash
sudo journalctl -u wellsound -n 50 --no-pager
```

**Database connection error:**
```bash
# Test connection manually
sudo -u wellsound /opt/wellsound/venv/bin/python -c "
from app.database import engine
with engine.connect() as c:
    print('DB connection OK')
"
```

**Nginx 502 Bad Gateway:**
- The FastAPI app isn't running. Check: `sudo systemctl status wellsound`

**OAuth redirect mismatch:**
- Make sure `AZURE_REDIRECT_URI` in `.env` exactly matches what's in Azure portal
- Include or exclude `www`, `http` vs `https`, trailing slash — must be identical

**Staff can't reach the app:**
- Check the server's IP: `ip addr show`
- Check firewall: `sudo ufw status` — ensure port 80 is allowed: `sudo ufw allow 80`

---

## Switching to Your Own Database Later

If you later connect an existing database instead of the WellSound PostgreSQL:

1. Update `DATABASE_URL` in `.env` to point to your existing DB
2. Run `init_db()` — this creates the WellSound tables in your DB without touching existing tables
3. The seed data script checks if wells exist before inserting — safe to run against a populated DB
4. For schema migration, use Alembic: `alembic revision --autogenerate -m "init"` then `alembic upgrade head`

---

## Connecting from Windows Computers on the Same Network

No installation needed on staff computers. They just:

1. Open Chrome or Edge
2. Type `http://192.168.1.50` (your server's local IP)
3. Log in with Microsoft credentials (or mock login during testing)

If you want a friendlier URL instead of an IP, ask IT to create a local DNS entry:
- `wellsound.local` → `192.168.1.50`

Staff can then go to `http://wellsound.local` instead.
