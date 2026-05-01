"""
Wikipedia enricher — fetches bio + photo for players that are missing them.
Uses Wikipedia REST API (no key needed) and Wikidata for photos.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional
from urllib.parse import quote
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Player
from app.services.avatar_scraper import fetch_external_player_photo_url

logger = logging.getLogger(__name__)

_USER_AGENT = "SportPredictAI/1.0"


def _http_get_json_sync(url: str) -> dict:
    req = Request(url, headers={"User-Agent": _USER_AGENT})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _fetch_wikipedia_summary_sync(player_name: str, lang: str) -> tuple[Optional[str], Optional[str]]:
    """Return (bio, photo_url) from Wikipedia REST API for the given language."""
    slug = player_name.replace(" ", "_")
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(slug)}"
    try:
        data = _http_get_json_sync(url)
    except Exception as exc:
        logger.debug("Wikipedia [%s] lookup failed for %s: %s", lang, player_name, exc)
        return None, None

    if data.get("type") == "disambiguation" or data.get("status"):
        return None, None

    extract = data.get("extract") or ""
    if len(extract) < 30:
        return None, None

    bio = extract.strip()
    thumbnail = data.get("originalimage") or data.get("thumbnail")
    photo_url = thumbnail.get("source") if thumbnail else None
    return bio, photo_url


def _get_ukrainian_title_via_wikidata_sync(wikibase_item: str) -> Optional[str]:
    """Given a Wikidata QID (e.g. 'Q615'), return the Ukrainian Wikipedia article title or None."""
    url = (
        f"https://www.wikidata.org/w/api.php?action=wbgetentities"
        f"&ids={quote(wikibase_item)}&props=sitelinks&sitefilter=ukwiki&format=json"
    )
    try:
        data = _http_get_json_sync(url)
        entities = data.get("entities", {})
        entity = entities.get(wikibase_item, {})
        sitelinks = entity.get("sitelinks", {})
        ukwiki = sitelinks.get("ukwiki", {})
        return ukwiki.get("title") or None
    except Exception as exc:
        logger.debug("Wikidata lookup failed for %s: %s", wikibase_item, exc)
        return None


def _fetch_wikipedia_data_sync(player_name: str) -> tuple[Optional[str], Optional[str]]:
    """
    Return (bio, photo_url).
    Strategy: fetch English Wikipedia to get the Wikidata QID, use that to find
    the Ukrainian article title, then return the Ukrainian bio. Falls back to English.
    """
    slug = player_name.replace(" ", "_")
    en_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(slug)}"
    try:
        en_data = _http_get_json_sync(en_url)
    except Exception as exc:
        logger.debug("Wikipedia [en] lookup failed for %s: %s", player_name, exc)
        return None, None

    if en_data.get("type") == "disambiguation" or en_data.get("status"):
        return None, None

    en_extract = en_data.get("extract") or ""
    if len(en_extract) < 30:
        return None, None

    # Photo from English Wikipedia (fallback)
    thumbnail = en_data.get("originalimage") or en_data.get("thumbnail")
    en_photo = thumbnail.get("source") if thumbnail else None

    # Try to get Ukrainian bio via Wikidata QID
    wikibase_item = en_data.get("wikibase_item")
    if wikibase_item:
        uk_title = _get_ukrainian_title_via_wikidata_sync(wikibase_item)
        if uk_title:
            uk_url = f"https://uk.wikipedia.org/api/rest_v1/page/summary/{quote(uk_title.replace(' ', '_'))}"
            try:
                uk_data = _http_get_json_sync(uk_url)
                uk_extract = uk_data.get("extract") or ""
                if len(uk_extract) >= 30 and not uk_data.get("status"):
                    uk_photo = None
                    uk_thumb = uk_data.get("originalimage") or uk_data.get("thumbnail")
                    if uk_thumb:
                        uk_photo = uk_thumb.get("source")
                    return uk_extract.strip(), uk_photo or en_photo
            except Exception as exc:
                logger.debug("Wikipedia [uk] fetch failed for %s: %s", uk_title, exc)

    # Fallback: return English bio
    return en_extract.strip(), en_photo


async def _fetch_wikipedia_data(player_name: str) -> tuple[Optional[str], Optional[str]]:
    return await asyncio.to_thread(_fetch_wikipedia_data_sync, player_name)


def _fetch_thesportsdb_photo_sync(player_name: str) -> Optional[str]:
    """Return cutout (PNG) photo URL from TheSportsDB free API, or None."""
    url = f"https://www.thesportsdb.com/api/v1/json/3/searchplayers.php?p={quote(player_name)}"
    try:
        data = _http_get_json_sync(url)
    except Exception as exc:
        logger.debug("TheSportsDB lookup failed for %s: %s", player_name, exc)
        return None

    players = data.get("player") or []
    if not players:
        return None

    # Pick best match: exact name match preferred
    player_lower = player_name.lower()
    for p in players:
        if (p.get("strPlayer") or "").lower() == player_lower:
            return p.get("strCutout") or p.get("strThumb") or None

    # Fallback: first result
    best = players[0]
    return best.get("strCutout") or best.get("strThumb") or None


async def _fetch_thesportsdb_photo(player_name: str) -> Optional[str]:
    return await asyncio.to_thread(_fetch_thesportsdb_photo_sync, player_name)


async def enrich_player(player_id: int, db_factory) -> None:
    """
    Background task: fetch Wikipedia bio + photo for a single player if missing.
    `db_factory` is a callable that returns an AsyncSession (async context manager).
    """
    async with db_factory() as db:
        result = await db.execute(select(Player).where(Player.id == player_id))
        player = result.scalar_one_or_none()
        if not player:
            return

        needs_bio = not player.bio
        needs_photo = not player.photo_url or _is_espn_404(player.photo_url)

        if not needs_bio and not needs_photo:
            return

        player_name = player.name
        team_name = ""
        sport_hint = "soccer"  # will be good enough; Wikidata scoring handles all sports

        # Try Wikipedia for bio (and maybe photo)
        bio, wiki_photo = await _fetch_wikipedia_data(player_name)

        # Photo fallback chain: TheSportsDB → Wikidata
        if needs_photo and not wiki_photo:
            wiki_photo = await _fetch_thesportsdb_photo(player_name)

        if needs_photo and not wiki_photo:
            wiki_photo = await fetch_external_player_photo_url(
                player_name,
                team_name=team_name,
                sport_hint=sport_hint,
            )

        updated = False
        if needs_bio and bio:
            player.bio = bio
            updated = True
        if needs_photo and wiki_photo:
            player.photo_url = wiki_photo
            updated = True

        if updated:
            db.add(player)
            await db.commit()
            logger.info("Enriched player %d (%s): bio=%s photo=%s", player_id, player_name, bool(bio), bool(wiki_photo))


def _is_espn_404(url: str) -> bool:
    """Quick sync check — only validates ESPN CDN URLs to avoid latency on every request."""
    if not url or "espncdn.com/i/headshots" not in url:
        return False
    try:
        req = Request(url, method="HEAD", headers={"User-Agent": _USER_AGENT})
        with urlopen(req, timeout=5) as resp:
            return resp.status == 404
    except Exception:
        # If we can't check, assume it's fine
        return False
