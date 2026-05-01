"""News router: GET news by match / team / season / recent."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database import get_db
from app.models.models import NewsArticle, MatchNews, TeamNews, SeasonNews, User
from app.schemas.schemas import NewsArticleResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/news", tags=["News"])


@router.get("/match/{match_id}", response_model=List[NewsArticleResponse])
async def get_match_news(
    match_id: int,
    limit: int = Query(default=30, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get all news articles linked to a specific match."""
    r = await db.execute(
        select(NewsArticle)
        .join(MatchNews, MatchNews.article_id == NewsArticle.id)
        .where(MatchNews.match_id == match_id)
        .order_by(NewsArticle.published_at.desc().nullslast())
        .limit(limit)
    )
    return r.scalars().all()


@router.get("/team/{team_id}", response_model=List[NewsArticleResponse])
async def get_team_news(
    team_id: int,
    limit: int = Query(default=30, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get all news articles linked to a specific team."""
    r = await db.execute(
        select(NewsArticle)
        .join(TeamNews, TeamNews.article_id == NewsArticle.id)
        .where(TeamNews.team_id == team_id)
        .order_by(NewsArticle.published_at.desc().nullslast())
        .limit(limit)
    )
    return r.scalars().all()


@router.get("/season/{season_id}", response_model=List[NewsArticleResponse])
async def get_season_news(
    season_id: int,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get all news articles linked to a specific season/league."""
    r = await db.execute(
        select(NewsArticle)
        .join(SeasonNews, SeasonNews.article_id == NewsArticle.id)
        .where(SeasonNews.season_id == season_id)
        .order_by(NewsArticle.published_at.desc().nullslast())
        .limit(limit)
    )
    return r.scalars().all()


@router.get("/recent", response_model=List[NewsArticleResponse])
async def get_recent_news(
    limit: int = Query(default=30, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recently fetched news articles across all entities."""
    r = await db.execute(
        select(NewsArticle)
        .order_by(NewsArticle.fetched_at.desc())
        .limit(limit)
    )
    return r.scalars().all()


@router.post("/refresh/match/{match_id}")
async def trigger_match_news_refresh(
    match_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a news refresh for a match (authenticated users)."""
    from app.services.news_scraper import refresh_match_news
    count = await refresh_match_news(db, match_id)
    return {"match_id": match_id, "articles_saved": count}


@router.post("/refresh/team/{team_id}")
async def trigger_team_news_refresh(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a news refresh for a team (authenticated users)."""
    from app.services.news_scraper import refresh_team_news
    count = await refresh_team_news(db, team_id)
    return {"team_id": team_id, "articles_saved": count}


@router.post("/refresh/season/{season_id}")
async def trigger_season_news_refresh(
    season_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a news refresh for a season/league (authenticated users)."""
    from app.services.news_scraper import refresh_season_news
    count = await refresh_season_news(db, season_id)
    return {"season_id": season_id, "articles_saved": count}
