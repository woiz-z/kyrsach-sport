"""
ESPN Roster Scraper — bulk player bio + headshot importer.

One HTTP request per team returns ALL player data (name, position, DOB,
nationality, height, weight, jersey, headshot URL).  This is vastly faster
than per-player Wikipedia searches for 4000+ players.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import date
from typing import Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Match, Player, Season, Sport, Team

logger = logging.getLogger(__name__)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
AVATAR_CACHE_DIR = os.environ.get("AVATAR_CACHE_DIR", "/var/cache/sportpredict/avatars")
_USER_AGENT = "SportPredictAI/1.0"

# Inches → cm / lbs → kg conversion
def _inches_to_cm(inches: float | None) -> int | None:
    if inches is None:
        return None
    return round(inches * 2.54)


def _lbs_to_kg(lbs: float | None) -> int | None:
    if lbs is None:
        return None
    return round(lbs * 0.453592)


def _parse_dob(dob_str: str | None) -> date | None:
    if not dob_str:
        return None
    try:
        # ESPN format: "1993-07-28T00:00Z" or "1993-07-28"
        return date.fromisoformat(dob_str[:10])
    except (ValueError, TypeError):
        return None


def _http_get(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": _USER_AGENT})
            with urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8", errors="ignore"))
        except HTTPError as exc:
            if exc.code == 404:
                return {}
            if exc.code in (429, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            logger.warning("ESPN roster HTTP %s for %s", exc.code, url)
            return {}
        except Exception as exc:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                logger.warning("ESPN roster error for %s: %s", url, exc)
    return {}


def _download_photo(url: str, player_id: int) -> bool:
    """Download ESPN headshot to avatar cache. Returns True on success."""
    if not url:
        return False
    os.makedirs(AVATAR_CACHE_DIR, exist_ok=True)
    # Prefer jpg, fall back to the URL's extension
    ext = "jpg"
    if "." in url.split("?")[0].split("/")[-1]:
        ext = url.split("?")[0].split("/")[-1].split(".")[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

    dest = os.path.join(AVATAR_CACHE_DIR, f"p{player_id}.{ext}")
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        return True  # already cached

    try:
        req = Request(url, headers={"User-Agent": _USER_AGENT})
        with urlopen(req, timeout=20) as resp:
            data = resp.read()
        if len(data) < 500:
            return False
        with open(dest, "wb") as f:
            f.write(data)
        return True
    except Exception as exc:
        logger.debug("Photo download failed for player %s: %s", player_id, exc)
        return False


def fetch_team_roster(espn_sport: str, espn_league: str, espn_team_id: str) -> list[dict]:
    """
    Fetch all roster athletes for one ESPN team.
    Returns a list of normalized player dicts.
    """
    url = f"{ESPN_BASE}/{espn_sport}/{espn_league}/teams/{espn_team_id}/roster"
    data = _http_get(url)
    if not data:
        return []

    athletes_raw = data.get("athletes", [])
    # Some leagues return athletes grouped by position group
    if athletes_raw and isinstance(athletes_raw[0], dict) and "items" in athletes_raw[0]:
        flat: list[dict] = []
        for group in athletes_raw:
            flat.extend(group.get("items", []))
        athletes_raw = flat

    players: list[dict] = []
    for a in athletes_raw:
        headshot = a.get("headshot") or {}
        pos = a.get("position") or {}
        players.append({
            "espn_id": str(a.get("id") or ""),
            "name": a.get("displayName") or a.get("fullName") or "",
            "position": pos.get("abbreviation") or pos.get("name") or "",
            "jersey_number": _safe_int(a.get("jersey")),
            "date_of_birth": _parse_dob(a.get("dateOfBirth")),
            "nationality": a.get("citizenship") or a.get("nationality") or "",
            "height_cm": _inches_to_cm(_safe_float(a.get("height"))),
            "weight_kg": _lbs_to_kg(_safe_float(a.get("weight"))),
            "photo_url": headshot.get("href") or "",
        })
    return players


def _safe_int(val) -> int | None:
    try:
        return int(val) if val is not None and val != "" else None
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    try:
        return float(val) if val is not None and val != "" else None
    except (ValueError, TypeError):
        return None


async def import_rosters_for_all_teams(db: AsyncSession) -> dict:
    """
    Main entry point: iterates all teams with ESPN IDs, fetches their roster
    from ESPN, upserts player bio fields + headshot cache.
    Returns a summary dict.
    """
    # Build team → (espn_sport, espn_league) mapping via matches
    # (matches link teams to the exact league season they compete in)
    # ORDER BY season_id ASC ensures domestic leagues (lower ids) are preferred over UEFA competitions
    league_result = await db.execute(
        select(Team.id, Season.espn_sport, Season.espn_league)
        .join(Match, (Match.home_team_id == Team.id) | (Match.away_team_id == Team.id))
        .join(Season, Season.id == Match.season_id)
        .where(Team.espn_id.isnot(None))
        .where(Season.espn_sport.isnot(None))
        .where(Season.espn_league.isnot(None))
        .order_by(Team.id, Season.id)
        .distinct(Team.id)
    )
    league_map: dict[int, tuple[str, str]] = {
        row[0]: (row[1], row[2]) for row in league_result.all()
    }

    # Also load all teams with espn_id so tennis/other no-match teams are included
    teams_result = await db.execute(
        select(Team, Sport.name)
        .join(Sport, Sport.id == Team.sport_id)
        .where(Team.espn_id.isnot(None))
    )
    team_rows = teams_result.all()

    if not team_rows:
        logger.warning("No teams with espn_id found. Run full ESPN import first.")
        return {"teams_processed": 0, "players_updated": 0, "photos_cached": 0}

    teams_to_process: list[tuple[Team, str, str]] = []
    for team, sport_name in team_rows:
        if team.id in league_map:
            espn_sport, espn_league = league_map[team.id]
            teams_to_process.append((team, espn_sport, espn_league))
        # Skip teams without a matched league (tennis, etc.)

    logger.info("[RosterScraper] Processing %d teams…", len(teams_to_process))

    total_updated = 0

    for team, espn_sport, espn_league in teams_to_process:
        try:
            roster = await asyncio.get_event_loop().run_in_executor(
                None, fetch_team_roster, espn_sport, espn_league, team.espn_id
            )
        except Exception as exc:
            logger.warning("Roster fetch failed for team %s (%s): %s", team.name, team.espn_id, exc)
            continue

        if not roster:
            logger.debug("Empty roster for team %s", team.name)
            continue

        for pdata in roster:
            if not pdata["name"]:
                continue

            # Find player: first by espn_id, then by name+team_id
            player: Player | None = None
            if pdata["espn_id"]:
                res = await db.execute(
                    select(Player).where(Player.espn_id == pdata["espn_id"])
                )
                player = res.scalar_one_or_none()

            if player is None:
                res = await db.execute(
                    select(Player).where(
                        Player.name == pdata["name"],
                        Player.team_id == team.id,
                    )
                )
                player = res.scalar_one_or_none()

            if player is None:
                # Create new player record
                player = Player(
                    name=pdata["name"],
                    team_id=team.id,
                )
                db.add(player)
                await db.flush()  # get the new id

            # Update fields
            if pdata["espn_id"]:
                player.espn_id = pdata["espn_id"]
            if pdata["position"]:
                player.position = pdata["position"]
            if pdata["date_of_birth"]:
                player.date_of_birth = pdata["date_of_birth"]
            if pdata["nationality"]:
                player.nationality = pdata["nationality"]
            if pdata["height_cm"] is not None:
                player.height_cm = pdata["height_cm"]
            if pdata["weight_kg"] is not None:
                player.weight_kg = pdata["weight_kg"]
            if pdata["jersey_number"] is not None:
                player.jersey_number = pdata["jersey_number"]
            if pdata["photo_url"]:
                player.photo_url = pdata["photo_url"]

            total_updated += 1

        await db.commit()
        logger.info("[RosterScraper] ✓ %s — %d players", team.name, len(roster))

    logger.info(
        "[RosterScraper] Done. teams=%d updated=%d",
        len(teams_to_process), total_updated,
    )
    return {
        "teams_processed": len(teams_to_process),
        "players_updated": total_updated,
        "photos_cached": 0,
    }
