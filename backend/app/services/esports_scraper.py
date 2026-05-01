"""
Esports data importer — uses the free OpenDota public API (no key required).
Fetches real professional Dota 2 matches, teams, and players.

Strategy: minimal API calls to avoid rate limits.
  /proMatches  — 1-2 calls → last ~100-200 pro matches (team names inline)
  /proPlayers  — 1 call → all pro players with team assignments
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Match, MatchResult, MatchStatus,
    Player, Season, Sport, Team, TeamStatistics,
)

logger = logging.getLogger(__name__)

_OPENDOTA_BASE = "https://api.opendota.com/api"
_HEADERS = {"User-Agent": "SportsPredictApp/1.0 (opendota-client)"}


async def _fetch(client: httpx.AsyncClient, path: str) -> list | dict:
    import asyncio
    url = _OPENDOTA_BASE + path
    for attempt in range(3):
        try:
            resp = await client.get(url, timeout=20)
            if resp.status_code == 429:
                await asyncio.sleep(2 ** attempt * 3)
                continue
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError:
            raise
        except Exception:
            if attempt < 2:
                await asyncio.sleep(1)
    return {}


async def import_esports(db: AsyncSession, max_matches: int = 200) -> dict:
    """
    Fetch real Dota 2 pro matches from OpenDota and persist to DB.
    Uses only 2 API calls: /proMatches and /proPlayers.
    """
    # 1. Resolve sport
    res = await db.execute(select(Sport).where(Sport.name == "Кіберспорт"))
    sport = res.scalar_one_or_none()
    if not sport:
        logger.warning("[Esports] Sport 'Кіберспорт' not found")
        return {"error": "sport_not_found"}
    sport_id = sport.id

    async with httpx.AsyncClient(headers=_HEADERS) as client:
        # 2. Fetch pro matches (up to 200)
        raw_matches: list[dict] = []
        for offset in range(0, min(max_matches, 200), 100):
            batch = await _fetch(client, f"/proMatches?offset={offset}")
            if not isinstance(batch, list) or not batch:
                break
            raw_matches.extend(batch)

        logger.info(f"[Esports] Fetched {len(raw_matches)} raw matches")
        if not raw_matches:
            return {"error": "no_matches_fetched"}

        # 3. Fetch all pro players (single call)
        pro_players = await _fetch(client, "/proPlayers")

    # 4. team_id → player names map
    team_players: dict[int, list[str]] = {}
    if isinstance(pro_players, list):
        for pp in pro_players:
            tid = pp.get("team_id")
            pname = pp.get("name") or pp.get("personaname")
            if tid and pname:
                team_players.setdefault(int(tid), []).append(str(pname)[:150])

    # 5. team_id → name from matches
    team_names: dict[int, str] = {}
    for m in raw_matches:
        if m.get("radiant_team_id") and m.get("radiant_name"):
            team_names[int(m["radiant_team_id"])] = m["radiant_name"]
        if m.get("dire_team_id") and m.get("dire_name"):
            team_names[int(m["dire_team_id"])] = m["dire_name"]

    # 6. League -> Season cache
    league_seasons: dict[int, int] = {}

    async def _get_or_create_season(league_id: int, league_name: str) -> int:
        if league_id in league_seasons:
            return league_seasons[league_id]
        sname = f"{league_name} (Dota 2)"[:120]
        r = await db.execute(select(Season).where(Season.name == sname))
        season = r.scalar_one_or_none()
        if not season:
            season = Season(
                name=sname, sport_id=sport_id,
                start_date=datetime(2025, 1, 1).date(),
                end_date=datetime(2026, 12, 31).date(),
            )
            db.add(season)
            await db.flush()
        league_seasons[league_id] = season.id
        return season.id

    # 7. Team cache
    team_cache: dict[int, Team] = {}

    async def _get_or_create_team(ext_id: int, name: str) -> Optional[Team]:
        if ext_id in team_cache:
            return team_cache[ext_id]
        ext_str = str(ext_id)
        r = await db.execute(
            select(Team).where(and_(Team.sport_id == sport_id, Team.espn_id == ext_str))
        )
        team = r.scalar_one_or_none()
        if team is None:
            team = Team(name=name[:100], sport_id=sport_id, country="International", espn_id=ext_str)
            db.add(team)
            await db.flush()
            for pname in team_players.get(ext_id, [])[:10]:
                db.add(Player(name=pname, team_id=team.id, position="Player"))
            await db.flush()
        team_cache[ext_id] = team
        return team

    # 8. Import matches
    new_matches = 0
    skipped = 0

    for raw in raw_matches:
        match_id = str(raw.get("match_id", ""))
        if not match_id:
            continue

        r = await db.execute(
            select(Match).where(and_(Match.sport_id == sport_id, Match.external_id == match_id))
        )
        if r.scalar_one_or_none():
            skipped += 1
            continue

        league_id = raw.get("leagueid")
        if not league_id:
            continue
        league_name = raw.get("league_name") or f"League {league_id}"

        radiant_id = raw.get("radiant_team_id")
        dire_id = raw.get("dire_team_id")
        if not radiant_id or not dire_id:
            continue

        season_id = await _get_or_create_season(int(league_id), league_name)
        home_team = await _get_or_create_team(int(radiant_id), team_names.get(int(radiant_id), f"Team {radiant_id}"))
        away_team = await _get_or_create_team(int(dire_id), team_names.get(int(dire_id), f"Team {dire_id}"))
        if not home_team or not away_team:
            continue

        start_ts = raw.get("start_time")
        match_date = (
            datetime.fromtimestamp(start_ts, tz=timezone.utc).replace(tzinfo=None)
            if start_ts else datetime.utcnow()
        )

        radiant_win = raw.get("radiant_win")
        if radiant_win is True:
            result, home_score, away_score = MatchResult.home_win, 1, 0
        elif radiant_win is False:
            result, home_score, away_score = MatchResult.away_win, 0, 1
        else:
            result, home_score, away_score = None, None, None

        status = MatchStatus.completed if radiant_win is not None else MatchStatus.scheduled

        db.add(Match(
            home_team_id=home_team.id, away_team_id=away_team.id,
            sport_id=sport_id, season_id=season_id, match_date=match_date,
            status=status, home_score=home_score, away_score=away_score,
            result=result, external_id=match_id,
        ))
        new_matches += 1

        if status == MatchStatus.completed:
            for team_obj, gf, ga, won in [
                (home_team, home_score, away_score, result == MatchResult.home_win),
                (away_team, away_score, home_score, result == MatchResult.away_win),
            ]:
                r2 = await db.execute(
                    select(TeamStatistics).where(
                        and_(TeamStatistics.team_id == team_obj.id,
                             TeamStatistics.season_id == season_id)
                    )
                )
                ts = r2.scalar_one_or_none()
                if ts is None:
                    ts = TeamStatistics(
                        team_id=team_obj.id, season_id=season_id,
                        matches_played=0, wins=0, draws=0, losses=0,
                        goals_for=0, goals_against=0, points=0, form_last5=[],
                    )
                    db.add(ts)
                ts.matches_played = (ts.matches_played or 0) + 1
                ts.goals_for = (ts.goals_for or 0) + (gf or 0)
                ts.goals_against = (ts.goals_against or 0) + (ga or 0)
                if won:
                    ts.wins = (ts.wins or 0) + 1
                    ts.points = (ts.points or 0) + 3
                    letter = "W"
                else:
                    ts.losses = (ts.losses or 0) + 1
                    letter = "L"
                form = list(ts.form_last5 or [])
                form.append(letter)
                ts.form_last5 = form[-5:]

        if new_matches % 25 == 0:
            await db.flush()

    await db.commit()
    logger.info(
        f"[Esports] Done: new={new_matches}, skipped={skipped}, "
        f"teams={len(team_cache)}, leagues={len(league_seasons)}"
    )
    return {"new_matches": new_matches, "skipped": skipped,
            "teams": len(team_cache), "leagues": len(league_seasons)}


async def refresh_esports(db: AsyncSession) -> dict:
    """Incremental refresh — only fetches latest 100 matches."""
    return await import_esports(db, max_matches=100)
