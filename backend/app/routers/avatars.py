from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.models import Player, Team, Season

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/avatars", tags=["Avatars"])

_UA = "Mozilla/5.0 (compatible; SportPredictAI/1.0)"


def _fetch_url_bytes(url: str, timeout: int = 10) -> Optional[bytes]:
    """Return raw bytes from URL, or None if request fails."""
    try:
        req = Request(url, headers={"User-Agent": _UA})
        with urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except Exception:
        pass
    return None


def _wikipedia_photo_url(player_name: str) -> Optional[str]:
    """Search Wikipedia for a player thumbnail via search API + summary endpoint."""
    from urllib.parse import quote
    import json

    # Step 1: search Wikipedia for the player
    search_url = (
        "https://en.wikipedia.org/w/api.php"
        f"?action=query&list=search&srsearch={quote(player_name + ' footballer')}&srlimit=3&format=json"
    )
    try:
        req = Request(search_url, headers={"User-Agent": _UA})
        with urlopen(req, timeout=10) as resp:
            results = json.loads(resp.read().decode("utf-8", errors="ignore"))
        hits = (results.get("query") or {}).get("search") or []
        if not hits:
            # Try without 'footballer' qualifier
            search_url2 = (
                "https://en.wikipedia.org/w/api.php"
                f"?action=query&list=search&srsearch={quote(player_name)}&srlimit=3&format=json"
            )
            req2 = Request(search_url2, headers={"User-Agent": _UA})
            with urlopen(req2, timeout=10) as resp2:
                results2 = json.loads(resp2.read().decode("utf-8", errors="ignore"))
            hits = (results2.get("query") or {}).get("search") or []
    except Exception:
        return None

    # Step 2: for each search hit, get summary and check for thumbnail
    for hit in hits[:3]:
        title = hit.get("title", "")
        if not title:
            continue
        try:
            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
            req3 = Request(summary_url, headers={"User-Agent": _UA})
            with urlopen(req3, timeout=10) as resp3:
                summary = json.loads(resp3.read().decode("utf-8", errors="ignore"))
            desc = (summary.get("description") or "").lower()
            if not any(kw in desc for kw in ("footballer", "player", "athlete", "born", "tennis", "basketball", "hockey")):
                continue
            thumb = (summary.get("thumbnail") or {}).get("source")
            if thumb:
                # Use the original thumbnail URL as-is (already a valid Wikimedia size)
                return thumb
        except Exception:
            continue

    return None


def _wikidata_photo_url(player_name: str, team_name: str) -> Optional[str]:
    """Search Wikidata for a player image URL (synchronous)."""
    from urllib.parse import quote
    import json

    queries = [f"{player_name} {team_name}".strip(), player_name]
    for query in queries:
        try:
            url = (
                "https://www.wikidata.org/w/api.php"
                f"?action=wbsearchentities&search={quote(query)}&language=en&format=json&limit=5"
            )
            req = Request(url, headers={"User-Agent": _UA})
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        except Exception:
            continue

        for candidate in data.get("search", []):
            entity_id = candidate.get("id")
            if not entity_id:
                continue
            desc = (candidate.get("description") or "").lower()
            if not any(kw in desc for kw in ("footballer", "player", "athlete", "tennis", "basketball", "hockey")):
                continue
            try:
                entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{quote(entity_id)}.json"
                req2 = Request(entity_url, headers={"User-Agent": _UA})
                with urlopen(req2, timeout=15) as resp2:
                    entity_data = json.loads(resp2.read().decode("utf-8", errors="ignore"))
                entity = (entity_data.get("entities") or {}).get(entity_id) or {}
                p18 = (entity.get("claims") or {}).get("P18") or []
                if p18:
                    fname = p18[0]["mainsnak"]["datavalue"]["value"]
                    return f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{quote(fname)}?width=512"
            except Exception:
                continue

    return None


def _color_palette(name: str) -> tuple[str, str, str, str, str]:
    palettes = [
        ("#123C7A", "#3B82F6", "#F2D3B1", "#111827", "#22C55E"),
        ("#164E63", "#06B6D4", "#E8C39E", "#334155", "#F59E0B"),
        ("#4C1D95", "#8B5CF6", "#F0C7A1", "#3F3F46", "#EF4444"),
        ("#7C2D12", "#F97316", "#EFC7AA", "#1F2937", "#14B8A6"),
        ("#065F46", "#10B981", "#F3D0AE", "#312E81", "#F43F5E"),
    ]
    idx = int(hashlib.md5((name or "").encode("utf-8")).hexdigest(), 16) % len(palettes)
    return palettes[idx]


def _avatar_svg(name: str, size: int) -> str:
    background, accent, skin, hair, shirt = _color_palette(name)
    stroke = max(1, size // 64)
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' viewBox='0 0 128 128'>"
        f"<defs><linearGradient id='bg' x1='0%' y1='0%' x2='100%' y2='100%'>"
        f"<stop offset='0%' stop-color='{background}'/><stop offset='100%' stop-color='{accent}'/>"
        f"</linearGradient></defs>"
        f"<rect width='128' height='128' rx='64' fill='url(#bg)'/>"
        f"<circle cx='64' cy='48' r='24' fill='{skin}'/>"
        f"<path d='M40 47c0-16 11-28 24-28s24 12 24 28v6H40z' fill='{hair}'/>"
        f"<path d='M36 118c4-24 19-36 28-36s24 12 28 36z' fill='{shirt}'/>"
        f"<circle cx='55' cy='49' r='{stroke + 1}' fill='#111827'/><circle cx='73' cy='49' r='{stroke + 1}' fill='#111827'/>"
        f"<path d='M55 61c3 4 15 4 18 0' fill='none' stroke='#9A3412' stroke-width='{stroke + 1}' stroke-linecap='round'/>"
        f"<path d='M45 32c4-10 15-16 26-16s21 6 26 16c-8-4-17-6-26-6s-18 2-26 6z' fill='{hair}' opacity='0.92'/>"
        "</svg>"
    )


@router.get("/image")
async def avatar_image(
    name: str = Query("Player", min_length=1, max_length=120),
    size: int = Query(128, ge=32, le=512),
):
    settings = get_settings()
    cache_dir = Path(settings.AVATAR_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_key = hashlib.sha1(f"{name}|{size}".encode("utf-8")).hexdigest()
    cached_file = cache_dir / f"{cache_key}.svg"

    if not cached_file.exists():
        svg_content = _avatar_svg(name, size)
        cached_file.write_text(svg_content, encoding="utf-8")

    return FileResponse(
        cached_file,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=604800"},
    )


async def _fetch_and_cache_photo(
    player_id: int,
    player_name: str,
    team_name: str,
    photo_url: Optional[str],
    cache_dir: Path,
) -> None:
    """Background task: try all sources and save real photo to disk cache."""
    # Don't re-fetch if another request already cached it
    for ext in ("jpg", "png"):
        if (cache_dir / f"p{player_id}.{ext}").exists():
            return

    img_bytes: Optional[bytes] = None

    # 1. Try photo_url from DB first (ESPN, TheSportsDB, or any other source)
    if photo_url:
        b = await asyncio.to_thread(_fetch_url_bytes, photo_url, 10)
        if b and len(b) > 1000:
            img_bytes = b

    # 2. Try Wikipedia + Wikidata concurrently as fallback
    if not img_bytes:
        try:
            wiki_url, wikidata_url = await asyncio.wait_for(
                asyncio.gather(
                    asyncio.to_thread(_wikipedia_photo_url, player_name),
                    asyncio.to_thread(_wikidata_photo_url, player_name, team_name),
                ),
                timeout=25.0,
            )
        except asyncio.TimeoutError:
            wiki_url, wikidata_url = None, None

        for img_url in [u for u in [wiki_url, wikidata_url] if u]:
            b = await asyncio.to_thread(_fetch_url_bytes, img_url, 12)
            if b and len(b) > 1000:
                img_bytes = b
                break

    if img_bytes:
        ext = "jpg" if img_bytes[:3] == b"\xff\xd8\xff" else "png"
        (cache_dir / f"p{player_id}.{ext}").write_bytes(img_bytes)
        logger.info("Cached real photo for player %d (%s)", player_id, player_name)


@router.get("/photo/{player_id}")
async def proxy_player_photo(
    player_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Return the best available real photo for a player.
    Cache hit → serve instantly. Cache miss → return SVG now, fetch real photo in background.
    """
    settings = get_settings()
    cache_dir = Path(settings.AVATAR_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Serve real photo immediately if cached
    for ext, mime in [("jpg", "image/jpeg"), ("png", "image/png")]:
        cached = cache_dir / f"p{player_id}.{ext}"
        if cached.exists():
            return FileResponse(cached, media_type=mime, headers={"Cache-Control": "public, max-age=604800"})

    # Fetch player + team info from DB
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    team_result = await db.execute(select(Team).where(Team.id == player.team_id))
    team = team_result.scalar_one_or_none()
    team_name = team.name if team else ""

    # Kick off background fetch (does not block this response)
    background_tasks.add_task(
        _fetch_and_cache_photo,
        player_id, player.name, team_name, player.photo_url, cache_dir,
    )

    # Return SVG immediately — browser retries will serve real photo once cached
    svg_content = _avatar_svg(player.name, 128)
    return Response(
        svg_content.encode("utf-8"),
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},  # Don't cache SVG so next load can get real photo
    )


@router.post("/import-rosters")
async def trigger_roster_import(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a bulk ESPN roster import for all known teams.
    Runs in background; returns immediately with a confirmation.
    ESPN roster endpoint returns ALL players for a team in ONE request,
    so the entire import needs only ~1 HTTP call per team.
    """
    from app.services.roster_scraper import import_rosters_for_all_teams
    from app.database import async_session

    async def _run_import():
        async with async_session() as session:
            try:
                result = await import_rosters_for_all_teams(session)
                logger.info("[RosterImport] Completed: %s", result)
            except Exception as exc:
                logger.error("[RosterImport] Failed: %s", exc)

    background_tasks.add_task(_run_import)
    return {"status": "started", "message": "Roster import started in background. Check server logs for progress."}
