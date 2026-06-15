"""
Eluno OMS — FastAPI application entry point.

Startup sequence:
  1. Create / migrate DB tables
  2. Register all routers
  3. Start APScheduler for background SLA scanning
"""
from __future__ import annotations

import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import get_settings
from database import init_db
from routes import orders, inventory, alerts
from services.alert_service import scan_and_fire_alerts

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────
    logger.info("🚀  Starting %s (%s)", settings.app_name, settings.app_env)
    await init_db()
    logger.info("✅  Database ready")

    # Background job: SLA scan every 30 minutes
    scheduler.add_job(
        scan_and_fire_alerts,
        trigger=IntervalTrigger(minutes=30),
        id="sla_scan",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("⏰  SLA scheduler started (every 30 min)")

    yield

    # ── Shutdown ─────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("👋  Shutdown complete")


app = FastAPI(
    title="Eluno OMS",
    description=(
        "AI-powered Order Management System for Eluno Eyewear.\n\n"
        "Handles the full order lifecycle: intake → lab → QC → delivery, "
        "with real-time SLA tracking and AI-driven TAT prediction."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(orders.router,    prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(alerts.router,    prefix="/api/v1")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.get("/", tags=["System"])
async def root():
    return {
        "message": f"Welcome to {settings.app_name} API",
        "docs": "/docs",
        "health": "/health",
    }