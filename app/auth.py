"""
Authentication module.

Supports two modes:
  1. Microsoft OAuth (production) — redirects to Azure AD, creates/updates user on callback
  2. Mock login (fallback) — used when AZURE_CLIENT_ID is not configured

JWT cookie-based sessions. No passwords stored for OAuth users.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse, JSONResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User, UserRole

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "wellsound_session"
ALGORITHM   = "HS256"

# Azure AD endpoints
AUTHORITY     = f"https://login.microsoftonline.com/{settings.azure_tenant_id}"
AUTH_ENDPOINT = f"{AUTHORITY}/oauth2/v2.0/authorize"
TOKEN_ENDPOINT = f"{AUTHORITY}/oauth2/v2.0/token"
GRAPH_ME      = "https://graph.microsoft.com/v1.0/me"

SCOPES = "openid profile email User.Read"

# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_session_token(user_id: int, role: str) -> str:
    expire = datetime.utcnow() + timedelta(seconds=settings.session_expire_seconds)
    return jwt.encode(
        {"sub": str(user_id), "role": role, "exp": expire},
        settings.secret_key, algorithm=ALGORITHM
    )


def decode_session_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME, value=token,
        httponly=True, samesite="lax", secure=False,  # set secure=True when HTTPS
        max_age=settings.session_expire_seconds,
    )


# ── Dependency: get current user ──────────────────────────────────────────────

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_session_token(token)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


def require_role(*roles: UserRole):
    """Dependency factory — raises 403 if user's role is not in allowed list."""
    def _check(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _check


require_operator = require_role(UserRole.OPERATOR, UserRole.SUPER, UserRole.ADMIN)
require_super    = require_role(UserRole.SUPER, UserRole.ADMIN)
require_admin    = require_role(UserRole.ADMIN)


# ── OAuth flow ────────────────────────────────────────────────────────────────

@router.get("/login")
def login(request: Request):
    """Redirect to Microsoft login page."""
    if not settings.azure_client_id:
        # Dev fallback — redirect to mock login page
        return RedirectResponse(url="/login.html")

    params = {
        "client_id":     settings.azure_client_id,
        "response_type": "code",
        "redirect_uri":  settings.azure_redirect_uri,
        "scope":         SCOPES,
        "response_mode": "query",
    }
    url = AUTH_ENDPOINT + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=url)


@router.get("/callback")
async def auth_callback(code: str, request: Request, db: Session = Depends(get_db)):
    """Microsoft redirects here after login. Exchange code for token, create/update user."""
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(TOKEN_ENDPOINT, data={
            "client_id":     settings.azure_client_id,
            "client_secret": settings.azure_client_secret,
            "code":          code,
            "redirect_uri":  settings.azure_redirect_uri,
            "grant_type":    "authorization_code",
        })

    if token_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="OAuth token exchange failed")

    tokens = token_resp.json()
    access_token = tokens.get("access_token")

    # Fetch user profile from Microsoft Graph
    async with httpx.AsyncClient() as client:
        me_resp = await client.get(GRAPH_ME, headers={"Authorization": f"Bearer {access_token}"})

    if me_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch user profile from Microsoft")

    profile = me_resp.json()
    azure_oid  = profile.get("id")
    email      = profile.get("mail") or profile.get("userPrincipalName", "")
    first_name = profile.get("givenName", "")
    last_name  = profile.get("surname", "")
    username   = email.split("@")[0]

    # Find or create user
    user = db.query(User).filter(User.azure_oid == azure_oid).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()

    if not user:
        # First login — create with Operator role by default
        user = User(
            azure_oid=azure_oid, email=email, username=username,
            first_name=first_name, last_name=last_name,
            role=UserRole.OPERATOR, is_active=True, email_verified=True,
        )
        db.add(user)

    # Update profile fields on every login
    user.azure_oid  = azure_oid
    user.first_name = first_name or user.first_name
    user.last_name  = last_name  or user.last_name
    user.last_login = datetime.utcnow()
    user.email_verified = True
    db.commit()
    db.refresh(user)

    # Create session cookie and redirect to app
    token = create_session_token(user.id, user.role.value)
    response = RedirectResponse(url="/", status_code=302)
    set_session_cookie(response, token)
    return response


# ── Mock login (dev / no Azure configured) ───────────────────────────────────

@router.post("/mock-login")
def mock_login(request: Request, response: Response, db: Session = Depends(get_db)):
    """Development-only login. Accepts username, returns session cookie."""
    if settings.azure_client_id:
        raise HTTPException(status_code=400, detail="Mock login disabled when OAuth is configured")

    body = json.loads(request.headers.get("content-length", "{}"))
    # FastAPI will parse JSON body via form — see route below


@router.post("/mock-login-json")
async def mock_login_json(request: Request, db: Session = Depends(get_db)):
    if settings.azure_client_id:
        raise HTTPException(status_code=400, detail="Use OAuth")
    data = await request.json()
    username = data.get("username", "").strip()
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    user.last_login = datetime.utcnow()
    db.commit()
    token = create_session_token(user.id, user.role.value)
    response = JSONResponse({"ok": True, "name": user.full_name, "role": user.role.value})
    set_session_cookie(response, token)
    return response


@router.post("/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id":         user.id,
        "username":   user.username,
        "name":       user.full_name,
        "email":      user.email,
        "role":       user.role.value,
        "is_active":  user.is_active,
    }
