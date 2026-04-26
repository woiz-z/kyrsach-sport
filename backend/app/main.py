from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
import warnings

# Suppress deprecation warnings from sklearn that flood the logs
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")

logger = logging.getLogger(__name__)
from sqlalchemy import select, func
from app.database import engine, Base, async_session
from app.routers import auth, sports, teams, matches, predictions, ai_models, dashboard
from app.services.background_jobs import (
    complete_past_matches,
    run_background_loop,
    run_esports_import_retry_loop,
    run_model_retrain_loop,
)
from app.services.real_data_importer import import_real_data
from app.services.football_data_scraper import import_from_football_data
from app.services.sport_bootstrap import ensure_default_sports
from app.services.model_training import train_best_models_per_sport
from app.config import get_settings
from app.models.models import Match, AIModel


async def _auto_train_on_startup():
    """Train best-per-sport models on startup if no models exist in DB."""

    async with async_session() as db:
        existing_count = await db.execute(select(func.count(AIModel.id)))
        if (existing_count.scalar() or 0) > 0:
            return

        summary = await train_best_models_per_sport(db, min_samples=30, seed=42, train_ratio=0.8)
        logger.info(
            "[Startup] best-per-sport training: "
            f"trained={summary.get('sports_trained', 0)} "
            f"skipped={summary.get('sports_skipped', 0)} "
            f"failed={summary.get('sports_failed', 0)}"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # 1. Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        await ensure_default_sports(db)
        await db.commit()

    # 2. Sync data once if DB is empty — run in background so startup is not blocked
    async def _bg_import():
        if settings.AUTO_SYNC_FOOTBALL_DATA:
            async with async_session() as db:
                match_count = await db.execute(select(func.count(Match.id)))
                if (match_count.scalar() or 0) == 0:
                    imported = await import_from_football_data(
                        db,
                        reset_existing=False,
                        min_season_code=settings.FOOTBALL_DATA_MIN_SEASON,
                        max_links=settings.FOOTBALL_DATA_MAX_LINKS,
                    )
                    logger.info(f"[Startup] football-data synced: {imported}")
        elif settings.AUTO_SYNC_REAL_DATA:
            async with async_session() as db:
                match_count = await db.execute(select(func.count(Match.id)))
                if (match_count.scalar() or 0) == 0:
                    imported = await import_real_data(db, reset_existing=False)
                    logger.info(f"[Startup] Real data synced: {imported}")

    # 3. Optional background loops
    background_tasks = [asyncio.create_task(_bg_import())]
    if settings.AUTO_SIMULATE_PAST_MATCHES:
        completed = await complete_past_matches(batch=200)
        if completed:
            logger.info(f"[Startup] Auto-completed {completed} past scheduled matches")
        background_tasks.append(asyncio.create_task(run_background_loop()))

    if settings.AUTO_RETRY_ESPORTS_IMPORT:
        background_tasks.append(
            asyncio.create_task(
                run_esports_import_retry_loop(
                    initial_delay=settings.ESPORTS_RETRY_INITIAL_DELAY_SECONDS,
                    max_delay=settings.ESPORTS_RETRY_MAX_DELAY_SECONDS,
                )
            )
        )

    if settings.AUTO_RETRAIN_MODELS:
        background_tasks.append(
            asyncio.create_task(
                run_model_retrain_loop(
                    interval_seconds=settings.MODEL_RETRAIN_INTERVAL_SECONDS,
                    min_samples=settings.MODEL_RETRAIN_MIN_SAMPLES,
                )
            )
        )

    # 4. Train ML models if none exist
    await _auto_train_on_startup()

    yield

    for task in background_tasks:
        task.cancel()

    for task in background_tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="SportPredict AI",
    description="Інформаційна система для прогнозування результатів спортивних подій з АІ",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sports.router)
app.include_router(teams.router)
app.include_router(matches.router)
app.include_router(predictions.router)
app.include_router(ai_models.router)
app.include_router(dashboard.router)


@app.get("/api/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "version": "1.0.0", "service": "SportPredict AI"}


@app.get("/")
async def root():
    return {"message": "SportPredict AI — API v1.0.0", "docs": "/docs"}
