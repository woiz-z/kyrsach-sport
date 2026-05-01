"""
Multi-source news scraper: ESPN API + Google News RSS + Reddit JSON.

Sources (all free, no API keys required):
  1. ESPN News API   — /apis/site/v2/sports/{sport}/{league}/news
  2. ESPN Team News  — /apis/site/v2/sports/{sport}/{league}/teams/{id}/news
  3. Google News RSS — news.google.com/rss/search?q=...
  4. Reddit JSON API — reddit.com/r/{sub}/search.json or /search.json
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Match, MatchStatus, Team, Season,
    NewsArticle, MatchNews, TeamNews, SeasonNews,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# Sport name → list of (espn_sport, espn_league) for news API
SPORT_ESPN_MAP: dict[str, list[tuple[str, str]]] = {
    "Футбол": [
        ("soccer", "eng.1"),
        ("soccer", "esp.1"),
        ("soccer", "ger.1"),
        ("soccer", "ita.1"),
        ("soccer", "fra.1"),
        ("soccer", "uefa.champions"),
    ],
    "Баскетбол": [("basketball", "nba")],
    "Хокей": [("hockey", "nhl")],
    "Теніс": [("tennis", "atp"), ("tennis", "wta")],
}

# Sport name → relevant subreddits (ordered by size/relevance)
SPORT_SUBREDDITS: dict[str, list[str]] = {
    "Футбол": ["soccer", "PremierLeague", "LaLiga", "Bundesliga", "SerieA", "championsleague"],
    "Баскетбол": ["nba", "nbadiscussion"],
    "Хокей": ["nhl", "hockey"],
    "Теніс": ["tennis"],
}

# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _http_raw(url: str, retries: int = 3, timeout: int = 20) -> bytes:
    """Fetch raw bytes with browser-like headers."""
    req = Request(url, headers={
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except HTTPError as e:
            if e.code in (429, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return b""
        except (URLError, OSError):
            if attempt < retries - 1:
                time.sleep(1)
    return b""


def _http_json(url: str) -> dict:
    raw = _http_raw(url)
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception:
        return {}


async def _get_json(url: str) -> dict:
    return await asyncio.to_thread(_http_json, url)


async def _get_raw(url: str) -> bytes:
    return await asyncio.to_thread(_http_raw, url)


# ── ESPN News API ─────────────────────────────────────────────────────────────

def _parse_espn_items(data: dict, source_label: str) -> list[dict]:
    articles = []
    for item in (data.get("articles") or []):
        title = (item.get("headline") or item.get("title") or "").strip()
        if not title:
            continue

        summary = (item.get("description") or item.get("summary") or "").strip()

        links = item.get("links") or {}
        url = ""
        if isinstance(links, dict):
            url = (links.get("web") or {}).get("href", "")
        if not url:
            url = item.get("url") or item.get("link") or ""
        if not url:
            continue

        images = item.get("images") or []
        image_url = images[0].get("url", "") if images and isinstance(images[0], dict) else ""

        published_at = None
        pub_raw = item.get("published") or item.get("lastModified") or ""
        if pub_raw:
            try:
                published_at = datetime.fromisoformat(
                    pub_raw.replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except Exception:
                pass

        articles.append({
            "title": title[:500],
            "summary": summary[:2000] or None,
            "url": url[:2000],
            "image_url": image_url[:2000] or None,
            "source": source_label,
            "language": "en",
            "published_at": published_at,
        })
    return articles


async def fetch_espn_league_news(espn_sport: str, espn_league: str, limit: int = 30) -> list[dict]:
    """Fetch top news articles for a league from ESPN."""
    url = f"{ESPN_BASE}/{espn_sport}/{espn_league}/news?limit={limit}"
    data = await _get_json(url)
    return _parse_espn_items(data, f"ESPN {espn_sport}/{espn_league}")


async def fetch_espn_team_news(espn_sport: str, espn_league: str, espn_team_id: str, limit: int = 15) -> list[dict]:
    """Fetch news for a specific team from ESPN."""
    url = f"{ESPN_BASE}/{espn_sport}/{espn_league}/teams/{espn_team_id}/news?limit={limit}"
    data = await _get_json(url)
    return _parse_espn_items(data, "ESPN")


# ── Google News RSS ───────────────────────────────────────────────────────────

_GN_MEDIA_NS = "http://search.yahoo.com/mrss/"


def _parse_google_rss(raw: bytes) -> list[dict]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    articles = []
    for item in channel.findall("item"):
        title_el = item.find("title")
        title = (title_el.text or "").strip() if title_el is not None else ""
        if not title:
            continue

        link_el = item.find("link")
        url = (link_el.text or "").strip() if link_el is not None else ""
        if not url:
            continue

        # Strip HTML from description
        desc_el = item.find("description")
        description = ""
        if desc_el is not None and desc_el.text:
            description = re.sub(r"<[^>]+>", " ", desc_el.text).strip()
            description = re.sub(r"\s+", " ", description).strip()

        published_at = None
        pub_el = item.find("pubDate")
        if pub_el is not None and pub_el.text:
            try:
                published_at = parsedate_to_datetime(pub_el.text.strip()).replace(tzinfo=None)
            except Exception:
                pass

        # Image from media:content namespace
        image_url = None
        media = item.find(f"{{{_GN_MEDIA_NS}}}content")
        if media is not None:
            image_url = media.get("url")

        articles.append({
            "title": title[:500],
            "summary": description[:2000] or None,
            "url": url[:2000],
            "image_url": image_url[:2000] if image_url else None,
            "source": "Google News",
            "language": None,  # mixed languages, don't guess
            "published_at": published_at,
        })
    return articles


async def fetch_google_news(query: str, limit: int = 15) -> list[dict]:
    """Search Google News RSS for articles matching query."""
    encoded = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en&gl=US&ceid=US:en"
    raw = await _get_raw(url)
    if not raw:
        return []
    return _parse_google_rss(raw)[:limit]


# ── Reddit JSON API ───────────────────────────────────────────────────────────

def _parse_reddit(data: dict) -> list[dict]:
    articles = []
    for post in ((data.get("data") or {}).get("children") or []):
        p = post.get("data") or {}
        title = (p.get("title") or "").strip()
        if not title:
            continue

        # Skip deleted/removed posts
        selftext = p.get("selftext") or ""
        if selftext in ("[deleted]", "[removed]"):
            continue
        if p.get("removed_by_category"):
            continue

        permalink = p.get("permalink", "")
        if p.get("is_self"):
            url = f"https://www.reddit.com{permalink}"
        else:
            url = p.get("url") or f"https://www.reddit.com{permalink}"
        if not url:
            continue

        summary = selftext.strip()[:500] if selftext.strip() else f"↑{p.get('score', 0)} upvotes on r/{p.get('subreddit', '')}"

        # Best image: preview > thumbnail
        image_url = None
        preview_images = (p.get("preview") or {}).get("images", [])
        if preview_images:
            raw_url = preview_images[0].get("source", {}).get("url", "")
            image_url = raw_url.replace("&amp;", "&") or None
        if not image_url:
            thumb = p.get("thumbnail", "")
            if thumb and thumb.startswith("http"):
                image_url = thumb

        published_at = None
        cre = p.get("created_utc")
        if cre:
            try:
                published_at = datetime.utcfromtimestamp(float(cre))
            except Exception:
                pass

        articles.append({
            "title": f"[Reddit] {title}"[:500],
            "summary": summary[:2000],
            "url": url[:2000],
            "image_url": image_url[:2000] if image_url else None,
            "source": f"Reddit r/{p.get('subreddit', 'unknown')}",
            "language": "en",
            "published_at": published_at,
        })
    return articles


async def fetch_reddit(query: str, subreddit: Optional[str] = None, limit: int = 8) -> list[dict]:
    """Search Reddit for posts matching query."""
    encoded = quote_plus(query)
    if subreddit:
        url = (
            f"https://www.reddit.com/r/{subreddit}/search.json"
            f"?q={encoded}&sort=new&limit={limit}&restrict_sr=1"
        )
    else:
        url = f"https://www.reddit.com/search.json?q={encoded}&sort=new&limit={limit}"
    data = await _get_json(url)
    return _parse_reddit(data)


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _upsert_article(db: AsyncSession, art: dict) -> Optional[NewsArticle]:
    """Insert article if URL not already stored. Returns the article row."""
    url = (art.get("url") or "").strip()
    if len(url) < 10:
        return None
    r = await db.execute(select(NewsArticle).where(NewsArticle.url == url))
    existing = r.scalar_one_or_none()
    if existing:
        return existing
    article = NewsArticle(**art)
    db.add(article)
    await db.flush()
    return article


async def _link_match(db: AsyncSession, article_id: int, match_id: int) -> None:
    r = await db.execute(
        select(MatchNews).where(
            and_(MatchNews.match_id == match_id, MatchNews.article_id == article_id)
        )
    )
    if not r.scalar_one_or_none():
        db.add(MatchNews(match_id=match_id, article_id=article_id))


async def _link_team(db: AsyncSession, article_id: int, team_id: int) -> None:
    r = await db.execute(
        select(TeamNews).where(
            and_(TeamNews.team_id == team_id, TeamNews.article_id == article_id)
        )
    )
    if not r.scalar_one_or_none():
        db.add(TeamNews(team_id=team_id, article_id=article_id))


async def _link_season(db: AsyncSession, article_id: int, season_id: int) -> None:
    r = await db.execute(
        select(SeasonNews).where(
            and_(SeasonNews.season_id == season_id, SeasonNews.article_id == article_id)
        )
    )
    if not r.scalar_one_or_none():
        db.add(SeasonNews(season_id=season_id, article_id=article_id))


# ── High-level refresh functions ──────────────────────────────────────────────

async def refresh_match_news(db: AsyncSession, match_id: int) -> int:
    """
    Fetch and save news for a specific match from all sources.
    Links articles to both the match and each team.
    Returns number of new articles saved.
    """
    r = await db.execute(
        select(Match)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.sport),
        )
        .where(Match.id == match_id)
    )
    match = r.scalar_one_or_none()
    if not match or not match.home_team or not match.away_team:
        return 0

    home = match.home_team.name
    away = match.away_team.name
    sport_name = match.sport.name if match.sport else ""
    query = f"{home} vs {away}"
    saved = 0

    # Google News — primary source (most comprehensive)
    for art in await fetch_google_news(query, limit=12):
        a = await _upsert_article(db, art)
        if a:
            await _link_match(db, a.id, match.id)
            await _link_team(db, a.id, match.home_team_id)
            await _link_team(db, a.id, match.away_team_id)
            saved += 1

    # Reddit — gossip, fan reactions
    subs = SPORT_SUBREDDITS.get(sport_name, [])
    for sub in subs[:2]:
        for art in await fetch_reddit(query, subreddit=sub, limit=5):
            a = await _upsert_article(db, art)
            if a:
                await _link_match(db, a.id, match.id)
                await _link_team(db, a.id, match.home_team_id)
                await _link_team(db, a.id, match.away_team_id)
                saved += 1
        await asyncio.sleep(0.5)

    # Extra team-specific articles
    for team_name, team_id in [(home, match.home_team_id), (away, match.away_team_id)]:
        for art in await fetch_google_news(f"{team_name} football news", limit=5):
            a = await _upsert_article(db, art)
            if a:
                await _link_match(db, a.id, match.id)
                await _link_team(db, a.id, team_id)
                saved += 1

    await db.commit()
    return saved


async def refresh_team_news(db: AsyncSession, team_id: int) -> int:
    """Fetch and save news for a specific team. Returns new article count."""
    r = await db.execute(
        select(Team)
        .options(selectinload(Team.sport))
        .where(Team.id == team_id)
    )
    team = r.scalar_one_or_none()
    if not team:
        return 0

    sport_name = team.sport.name if team.sport else ""
    saved = 0

    # Google News
    for art in await fetch_google_news(team.name, limit=15):
        a = await _upsert_article(db, art)
        if a:
            await _link_team(db, a.id, team.id)
            saved += 1

    # ESPN team-specific news (requires ESPN ID stored on team)
    if team.espn_id:
        espn_configs = SPORT_ESPN_MAP.get(sport_name, [])
        if espn_configs:
            sp, lg = espn_configs[0]
            for art in await fetch_espn_team_news(sp, lg, team.espn_id, limit=15):
                a = await _upsert_article(db, art)
                if a:
                    await _link_team(db, a.id, team.id)
                    saved += 1

    # Reddit
    subs = SPORT_SUBREDDITS.get(sport_name, [])
    if subs:
        for art in await fetch_reddit(team.name, subreddit=subs[0], limit=8):
            a = await _upsert_article(db, art)
            if a:
                await _link_team(db, a.id, team.id)
                saved += 1

    await db.commit()
    return saved


async def refresh_season_news(db: AsyncSession, season_id: int) -> int:
    """Fetch and save news for a league/season. Returns new article count."""
    r = await db.execute(
        select(Season)
        .options(selectinload(Season.sport))
        .where(Season.id == season_id)
    )
    season = r.scalar_one_or_none()
    if not season:
        return 0

    sport_name = season.sport.name if season.sport else ""
    # Strip year suffix: "Premier League 2024/2025" → "Premier League"
    league_short = re.sub(r"\s+\d{4}[/\-]\d{2,4}$", "", season.name).strip()
    saved = 0

    # ESPN league news
    if season.espn_sport and season.espn_league:
        for art in await fetch_espn_league_news(season.espn_sport, season.espn_league, limit=30):
            a = await _upsert_article(db, art)
            if a:
                await _link_season(db, a.id, season.id)
                saved += 1
    else:
        # Fallback: try all ESPN configs for this sport
        for sp, lg in SPORT_ESPN_MAP.get(sport_name, [])[:2]:
            for art in await fetch_espn_league_news(sp, lg, limit=20):
                a = await _upsert_article(db, art)
                if a:
                    await _link_season(db, a.id, season.id)
                    saved += 1
            await asyncio.sleep(0.4)

    # Google News for league
    for art in await fetch_google_news(f"{league_short} news latest", limit=12):
        a = await _upsert_article(db, art)
        if a:
            await _link_season(db, a.id, season.id)
            saved += 1

    # Reddit
    subs = SPORT_SUBREDDITS.get(sport_name, [])
    if subs:
        for art in await fetch_reddit(league_short, subreddit=subs[0], limit=8):
            a = await _upsert_article(db, art)
            if a:
                await _link_season(db, a.id, season.id)
                saved += 1

    await db.commit()
    return saved


# ── Background bulk refresh ───────────────────────────────────────────────────

async def refresh_upcoming_matches_news(db: AsyncSession, days_ahead: int = 7) -> dict:
    """
    Refresh news for all matches scheduled in the next N days.
    Called from the background news loop.
    """
    now = datetime.utcnow()
    cutoff = now + timedelta(days=days_ahead)

    r = await db.execute(
        select(Match.id)
        .where(
            and_(
                Match.status == MatchStatus.scheduled,
                Match.match_date >= now,
                Match.match_date <= cutoff,
            )
        )
        .limit(40)
    )
    match_ids = [row[0] for row in r.fetchall()]

    total_saved = 0
    for mid in match_ids:
        try:
            saved = await refresh_match_news(db, mid)
            total_saved += saved
            await asyncio.sleep(1.5)  # polite rate limiting
        except Exception as e:
            logger.warning("[News] Match %d news error: %s", mid, e)

    return {"matches_processed": len(match_ids), "articles_saved": total_saved}


async def refresh_all_seasons_news(db: AsyncSession) -> dict:
    """Refresh league news for all seasons. Called periodically."""
    r = await db.execute(select(Season.id))
    season_ids = [row[0] for row in r.fetchall()]

    total_saved = 0
    for sid in season_ids:
        try:
            saved = await refresh_season_news(db, sid)
            total_saved += saved
            await asyncio.sleep(2.0)
        except Exception as e:
            logger.warning("[News] Season %d news error: %s", sid, e)

    return {"seasons_processed": len(season_ids), "articles_saved": total_saved}
