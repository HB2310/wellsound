"""
WellSound — FastAPI application entry point.

Startup order:
  1. Init DB (create tables if they don't exist)
  2. Load seed data if LOAD_SEED_DATA=true and DB is empty
  3. Mount static files (serves index.html)
  4. Register all routers
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.auth import router as auth_router
from app.routers.wells import router as wells_router
from app.routers.measurements import router as measurements_router
from app.routers.corrections import router as corrections_router
from app.routers.reference import router as reference_router
from app.routers.users import router as users_router

settings = get_settings()
STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    init_db()
    if settings.load_seed_data:
        try:
            from app.seed import seed_if_empty
            seed_if_empty()
        except Exception as e:
            print(f"[seed] Warning: {e}")
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────────
    # Nothing to clean up — SQLAlchemy handles connection pool


app = FastAPI(
    title="WellSound",
    description="Groundwater monitoring data entry and management system",
    version="1.0.0",
    lifespan=lifespan,
    # Disable docs in production
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS — only needed for local dev when frontend and backend are on different ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(wells_router)
app.include_router(measurements_router)
app.include_router(corrections_router)
app.include_router(reference_router)
app.include_router(users_router)

# ── Static files ──────────────────────────────────────────────────────────────
# Serves index.html for all non-API routes (SPA behaviour)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(request: Request, full_path: str):
        """Serve index.html for all frontend routes."""
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse({"error": "Frontend not found"}, status_code=404)

    @app.get("/", include_in_schema=False)
    async def root():
        return FileResponse(str(STATIC_DIR / "index.html"))
