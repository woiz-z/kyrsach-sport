"""
Full roster import - processes all teams with missing player ESPN data.
Run directly in backend container:
  python scripts/run_full_roster_import.py
"""
import asyncio
import json
import logging
import os
import sys
import time
from datetime import date
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# Add app to path
sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

from sqlalchemy import select, text
from app.database import async_session
from app.models.models import Player, Team, Sport, Season, Match

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
UA = "SportPredictAI/1.0"


def _safe_int(v):
    try:
        return int(v) if v not in (None, "") else None
    except:
        return None


def _safe_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except:
        return None


def _inches_to_cm(v):
    f = _safe_float(v)
    return round(f * 2.54) if f else None


def _lbs_to_kg(v):
    f = _safe_float(v)
    return round(f * 0.453592) if f else None


def _parse_dob(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except:
        return None


def _http_get(url, retries=3):
    for i in range(retries):
        try:
            req = Request(url, headers={"User-Agent": UA})
            with urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8", errors="ignore"))
        except HTTPError as e:
            if e.code == 404:
                return {}
            if e.code in (429, 503) and i < retries - 1:
                time.sleep(2 ** i)
                continue
            return {}
        except Exception as e:
            if i < retries - 1:
                time.sleep(1)
    return {}


def fetch_roster(espn_sport, espn_league, team_espn_id):
    url = f"{ESPN_BASE}/{espn_sport}/{espn_league}/teams/{team_espn_id}/roster"
    data = _http_get(url)
    if not data:
        return []

    raw = data.get("athletes", [])
    # Flatten grouped rosters (NFL, basketball)
    if raw and isinstance(raw[0], dict) and "items" in raw[0]:
        flat = []
        for g in raw:
            flat.extend(g.get("items", []))
        raw = flat

    players = []
    for a in raw:
        hs = a.get("headshot") or {}
        pos = a.get("position") or {}
        players.append({
            "espn_id": str(a.get("id") or ""),
            "name": a.get("displayName") or a.get("fullName") or "",
            "position": pos.get("abbreviation") or pos.get("name") or "",
            "jersey_number": _safe_int(a.get("jersey")),
            "date_of_birth": _parse_dob(a.get("dateOfBirth")),
            "nationality": a.get("citizenship") or a.get("nationality") or "",
            "height_cm": _inches_to_cm(a.get("height")),
            "weight_kg": _lbs_to_kg(a.get("weight")),
            "photo_url": hs.get("href") or "",
        })
    return players


async def main():
    async with async_session() as db:
        # Build team -> (espn_sport, espn_league) using lowest season_id (domestic first)
        rows = await db.execute(text("""
            SELECT DISTINCT ON (t.id)
                t.id, t.name, t.espn_id, s.espn_sport, s.espn_league
            FROM teams t
            JOIN matches m ON m.home_team_id = t.id OR m.away_team_id = t.id
            JOIN seasons s ON s.id = m.season_id
            WHERE t.espn_id IS NOT NULL
              AND s.espn_sport IS NOT NULL
              AND s.espn_league IS NOT NULL
              AND s.espn_league != 'wta'
              AND s.espn_league != 'atp'
            ORDER BY t.id, s.id ASC
        """))
        teams = rows.fetchall()

        logger.info("Total teams to process: %d", len(teams))

        total_updated = 0
        total_created = 0

        for i, (team_id, team_name, team_espn_id, espn_sport, espn_league) in enumerate(teams):
            logger.info("[%d/%d] %s (ESPN:%s %s/%s)",
                        i+1, len(teams), team_name, team_espn_id, espn_sport, espn_league)

            try:
                roster = await asyncio.get_event_loop().run_in_executor(
                    None, fetch_roster, espn_sport, espn_league, team_espn_id
                )
            except Exception as e:
                logger.warning("  ERROR: %s", e)
                continue

            if not roster:
                logger.warning("  Empty roster - skipping")
                continue

            team_updated = 0
            for pdata in roster:
                if not pdata["name"]:
                    continue

                # Find by espn_id first, then name+team
                player = None
                if pdata["espn_id"]:
                    res = await db.execute(
                        select(Player).where(Player.espn_id == pdata["espn_id"])
                    )
                    player = res.scalar_one_or_none()

                if player is None:
                    res = await db.execute(
                        select(Player).where(
                            Player.name == pdata["name"],
                            Player.team_id == team_id,
                        )
                    )
                    player = res.scalar_one_or_none()

                if player is None:
                    player = Player(name=pdata["name"], team_id=team_id)
                    db.add(player)
                    await db.flush()
                    total_created += 1

                changed = False
                for field in ("espn_id", "position", "date_of_birth", "nationality",
                              "height_cm", "weight_kg", "jersey_number", "photo_url"):
                    val = pdata.get(field)
                    if val is not None and val != "" and getattr(player, field) != val:
                        setattr(player, field, val)
                        changed = True

                if changed:
                    team_updated += 1
                    total_updated += 1

            await db.commit()
            logger.info("  -> updated %d players (roster size: %d)", team_updated, len(roster))

        logger.info("=== DONE: %d teams, %d players updated, %d created ===",
                    len(teams), total_updated, total_created)


if __name__ == "__main__":
    asyncio.run(main())
