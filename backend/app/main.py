from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging

logger = logging.getLogger(__name__)
from sqlalchemy import select, func, text as sa_text
from app.database import engine, Base, async_session
from app.routers import auth, sports, teams, matches, predictions, ai_models, dashboard, news, live, avatars, players
from app.services.background_jobs import (
    complete_past_matches,
    run_background_loop,
    run_data_refresh_loop,
    run_news_refresh_loop,
)
from app.services.live_poller import run_live_poller_loop
from app.services.mega_scraper import import_all_sports
from app.services.sport_bootstrap import ensure_default_sports
from app.config import get_settings
from app.models.models import Match


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # 1. Ensure all tables exist (creates new tables; existing ones untouched)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add new columns to existing matches table if they don't exist yet
        await conn.execute(sa_text(
            "ALTER TABLE matches ADD COLUMN IF NOT EXISTS external_id VARCHAR(80)"
        ))
        await conn.execute(sa_text(
            "ALTER TABLE matches ADD COLUMN IF NOT EXISTS enriched BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        # New columns for news feature
        await conn.execute(sa_text(
            "ALTER TABLE teams ADD COLUMN IF NOT EXISTS espn_id VARCHAR(30)"
        ))
        await conn.execute(sa_text(
            "ALTER TABLE seasons ADD COLUMN IF NOT EXISTS espn_sport VARCHAR(50)"
        ))
        await conn.execute(sa_text(
            "ALTER TABLE seasons ADD COLUMN IF NOT EXISTS espn_league VARCHAR(50)"
        ))
        # Player headshot photos
        await conn.execute(sa_text(
            "ALTER TABLE players ADD COLUMN IF NOT EXISTS photo_url VARCHAR(500)"
        ))
        await conn.execute(sa_text(
            "ALTER TABLE players ADD COLUMN IF NOT EXISTS height_cm INTEGER"
        ))
        await conn.execute(sa_text(
            "ALTER TABLE players ADD COLUMN IF NOT EXISTS weight_kg INTEGER"
        ))
        await conn.execute(sa_text(
            "ALTER TABLE players ADD COLUMN IF NOT EXISTS jersey_number INTEGER"
        ))
        await conn.execute(sa_text(
            "ALTER TABLE players ADD COLUMN IF NOT EXISTS espn_id VARCHAR(30)"
        ))
        await conn.execute(sa_text(
            "ALTER TABLE players ADD COLUMN IF NOT EXISTS stats_json JSONB"
        ))
        # Backfill NULL created_at for users
        await conn.execute(sa_text(
            "UPDATE users SET created_at = NOW() WHERE created_at IS NULL"
        ))

    async with async_session() as db:
        await ensure_default_sports(db)
        await db.commit()

    # 2. Full data import in background if DB is empty
    async def _bg_import():
        async with async_session() as db:
            match_count = await db.execute(select(func.count(Match.id)))
            if (match_count.scalar() or 0) == 0:
                try:
                    logger.info("[Startup] DB is empty — starting full ESPN import …")
                    summary = await import_all_sports(db, reset_existing=False)
                    logger.info(f"[Startup] ESPN import done: {summary}")
                except Exception as exc:
                    logger.error(f"[Startup] ESPN import failed: {exc}")

        # Always import esports (OpenDota) on startup
        try:
            from app.services.esports_scraper import import_esports
            async with async_session() as db:
                from app.models.models import Match as _Match
                from sqlalchemy import select as _select, func as _func
                from app.models.models import Sport as _Sport
                sport_res = await db.execute(_select(_Sport).where(_Sport.name == "Кіберспорт"))
                sport_obj = sport_res.scalar_one_or_none()
                if sport_obj:
                    esport_count_res = await db.execute(
                        _select(_func.count()).select_from(_Match).where(_Match.sport_id == sport_obj.id)
                    )
                    existing = esport_count_res.scalar() or 0
                    if existing < 10:
                        logger.info("[Startup] Running esports import (OpenDota) …")
                        summary = await import_esports(db, max_matches=200)
                        logger.info(f"[Startup] Esports import done: {summary}")
        except Exception as exc:
            logger.error(f"[Startup] Esports import failed: {exc}")

    # 3. Background loops
    background_tasks = [asyncio.create_task(_bg_import())]

    if settings.AUTO_SIMULATE_PAST_MATCHES:
        completed = await complete_past_matches(batch=200)
        if completed:
            logger.info(f"[Startup] Auto-completed {completed} past scheduled matches")
        background_tasks.append(asyncio.create_task(run_background_loop()))

    # Data refresh loop replaces the old esports retry loop
    background_tasks.append(asyncio.create_task(run_data_refresh_loop(interval_seconds=120)))
    # News refresh loop — fetches ESPN/Google News/Reddit for upcoming matches
    background_tasks.append(asyncio.create_task(run_news_refresh_loop(interval_seconds=3600)))
    background_tasks.append(asyncio.create_task(run_live_poller_loop()))

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
        "https://frontend-production-1532.up.railway.app",
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
app.include_router(news.router)
app.include_router(live.router)
app.include_router(avatars.router)
app.include_router(players.router)


@app.get("/api/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "version": "1.0.0", "service": "SportPredict AI"}


@app.get("/")
async def root():
    return {"message": "SportPredict AI — API v1.0.0", "docs": "/docs"}
