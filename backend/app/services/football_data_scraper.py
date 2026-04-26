"""Scraper/importer for openfootball JSON datasets (free historical + fixtures)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from sqlalchemy import select, and_, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    User,
    UserRole,
    Sport,
    Team,
    Season,
    Match,
    MatchStatus,
    MatchResult,
    TeamStatistics,
    HeadToHead,
    Prediction,
    AIModel,
    Player,
)
from app.services.auth import hash_password

TREE_API_URL = "https://api.github.com/repos/openfootball/football.json/git/trees/master?recursive=1"
RAW_BASE = "https://raw.githubusercontent.com/openfootball/football.json/master/"


@dataclass
class ImportResult:
    links_found: int
    links_used: int
    teams: int
    seasons: int
    matches_total: int
    matches_completed: int
    matches_scheduled: int
    new_matches_added: int


def _http_get_json(url: str) -> dict:
    try:
        with urlopen(url, timeout=45) as r:
            data = r.read().decode("utf-8", errors="ignore")
        return json.loads(data)
    except HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} fetching {url}") from e
    except URLError as e:
        raise RuntimeError(f"Network error fetching {url}: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from {url}: {e}") from e


def _parse_season_code(folder: str) -> int:
    # "2025-26" -> 2526
    try:
        left, right = folder.split("-")
        return int(left[-2:] + right)
    except Exception:
        return 0


def _dt_from_match(m: dict) -> Optional[datetime]:
    d = m.get("date")
    if not d:
        return None
    t = (m.get("time") or "18:00").strip()
    if len(t) == 5:
        t += ":00"
    try:
        return datetime.fromisoformat(f"{d} {t}")
    except ValueError:
        try:
            return datetime.fromisoformat(f"{d} 18:00:00")
        except ValueError:
            return None


def _result_from_scores(hg: Optional[int], ag: Optional[int]) -> Optional[MatchResult]:
    if hg is None or ag is None:
        return None
    if hg > ag:
        return MatchResult.home_win
    if ag > hg:
        return MatchResult.away_win
    return MatchResult.draw


async def _ensure_default_users(db: AsyncSession) -> None:
    existing = (await db.execute(select(User.id))).scalars().first()
    if existing:
        return
    db.add_all([
        User(username="admin", email="admin@sportpredict.ua", password_hash=hash_password("admin123"), role=UserRole.admin),
        User(username="analyst", email="analyst@sportpredict.ua", password_hash=hash_password("analyst123"), role=UserRole.analyst),
        User(username="user", email="user@sportpredict.ua", password_hash=hash_password("user123"), role=UserRole.user),
    ])


async def _ensure_sport(db: AsyncSession) -> Sport:
    r = await db.execute(select(Sport).where(Sport.name == "Футбол"))
    sport = r.scalar_one_or_none()
    if sport:
        return sport
    sport = Sport(name="Футбол", description="Association football", icon="⚽")
    db.add(sport)
    await db.flush()
    return sport


async def _get_or_create_team(db: AsyncSession, cache: Dict[str, Team], sport_id: int, name: str) -> Team:
    key = name.strip()
    if key in cache:
        return cache[key]
    r = await db.execute(select(Team).where(and_(Team.sport_id == sport_id, Team.name == key)))
    team = r.scalar_one_or_none()
    if not team:
        team = Team(name=key, sport_id=sport_id, country="Unknown", city="", logo_url="")
        db.add(team)
        await db.flush()
    cache[key] = team
    return team


async def _get_or_create_season(
    db: AsyncSession,
    cache: Dict[str, Season],
    sport_id: int,
    file_path: str,
    season_name: str,
    season_folder: str,
) -> Season:
    # use file path in display name to avoid collisions between leagues
    display = f"{season_name} [{file_path.split('/')[-1].replace('.json', '').upper()}]"
    if display in cache:
        return cache[display]

    r = await db.execute(select(Season).where(and_(Season.sport_id == sport_id, Season.name == display)))
    season = r.scalar_one_or_none()
    if not season:
        try:
            y1, y2 = season_folder.split("-")
            start_date = date(int(y1), 7, 1)
            end_date = date(int("20" + y2), 6, 30)
        except Exception:
            yy = datetime.utcnow().year
            start_date = date(yy, 1, 1)
            end_date = date(yy, 12, 31)

        season = Season(sport_id=sport_id, name=display, start_date=start_date, end_date=end_date)
        db.add(season)
        await db.flush()

    cache[display] = season
    return season


async def _clear_sports_data(db: AsyncSession) -> None:
    await db.execute(
        text(
            """
            TRUNCATE TABLE
              predictions,
              ai_models,
              head_to_head,
              team_statistics,
              players,
              matches,
              seasons,
              teams,
              sports
            RESTART IDENTITY CASCADE
            """
        )
    )


async def _rebuild_derived_tables(db: AsyncSession) -> None:
    await db.execute(delete(TeamStatistics))
    await db.execute(delete(HeadToHead))

    q = await db.execute(
        select(Match)
        .where(Match.status == MatchStatus.completed)
        .order_by(Match.match_date.asc())
    )
    matches = q.scalars().all()

    stats: Dict[Tuple[int, int], dict] = {}
    h2h: Dict[Tuple[int, int], dict] = {}

    for m in matches:
        if m.home_score is None or m.away_score is None or m.result is None:
            continue

        for team_id, is_home in ((m.home_team_id, True), (m.away_team_id, False)):
            k = (m.season_id, team_id)
            if k not in stats:
                stats[k] = {
                    "matches_played": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "points": 0,
                    "form": [],
                }
            s = stats[k]
            s["matches_played"] += 1
            gf = m.home_score if is_home else m.away_score
            ga = m.away_score if is_home else m.home_score
            s["goals_for"] += gf
            s["goals_against"] += ga

            if m.result == MatchResult.draw:
                s["draws"] += 1
                s["points"] += 1
                s["form"].append("D")
            elif (m.result == MatchResult.home_win and is_home) or (m.result == MatchResult.away_win and not is_home):
                s["wins"] += 1
                s["points"] += 3
                s["form"].append("W")
            else:
                s["losses"] += 1
                s["form"].append("L")

        a, b = sorted((m.home_team_id, m.away_team_id))
        hk = (a, b)
        if hk not in h2h:
            h2h[hk] = {"total": 0, "a_wins": 0, "b_wins": 0, "draws": 0}
        h = h2h[hk]
        h["total"] += 1
        if m.result == MatchResult.draw:
            h["draws"] += 1
        elif m.result == MatchResult.home_win:
            if m.home_team_id == a:
                h["a_wins"] += 1
            else:
                h["b_wins"] += 1
        elif m.result == MatchResult.away_win:
            if m.away_team_id == a:
                h["a_wins"] += 1
            else:
                h["b_wins"] += 1

    db.add_all([
        TeamStatistics(
            season_id=season_id,
            team_id=team_id,
            matches_played=s["matches_played"],
            wins=s["wins"],
            draws=s["draws"],
            losses=s["losses"],
            goals_for=s["goals_for"],
            goals_against=s["goals_against"],
            points=s["points"],
            form_last5=s["form"][-5:],
        )
        for (season_id, team_id), s in stats.items()
    ])

    db.add_all([
        HeadToHead(
            team1_id=a,
            team2_id=b,
            total_matches=h["total"],
            team1_wins=h["a_wins"],
            team2_wins=h["b_wins"],
            draws=h["draws"],
        )
        for (a, b), h in h2h.items()
    ])


def _discover_openfootball_files(min_season_code: int, league_codes: Optional[List[str]]) -> List[str]:
    tree = _http_get_json(TREE_API_URL)
    items = tree.get("tree") or []
    allowed = set(x.lower() for x in (league_codes or []))

    out = []
    for item in items:
        path = item.get("path") or ""
        if not path.endswith(".json"):
            continue
        parts = path.split("/")
        if len(parts) != 2:
            continue

        season_folder, league_file = parts
        sc = _parse_season_code(season_folder)
        if sc < min_season_code:
            continue

        league_code = league_file.replace(".json", "").lower()  # e.g. en.1
        if allowed and league_code not in allowed:
            continue

        out.append(path)

    out.sort(reverse=True)
    return out


async def import_from_football_data(
    db: AsyncSession,
    reset_existing: bool = True,
    min_season_code: int = 2324,
    max_links: int = 0,
    league_codes: Optional[List[str]] = None,
) -> ImportResult:
    if reset_existing:
        await _clear_sports_data(db)

    await _ensure_default_users(db)
    sport = await _ensure_sport(db)

    files = _discover_openfootball_files(min_season_code=min_season_code, league_codes=league_codes)
    if max_links and max_links > 0:
        files = files[:max_links]

    team_cache: Dict[str, Team] = {}
    season_cache: Dict[str, Season] = {}
    added_matches = 0

    for path in files:
        payload = _http_get_json(RAW_BASE + path)
        season_name = payload.get("name") or path
        season_folder = path.split("/")[0]
        matches = payload.get("matches") or []

        season = await _get_or_create_season(
            db=db,
            cache=season_cache,
            sport_id=sport.id,
            file_path=path,
            season_name=season_name,
            season_folder=season_folder,
        )

        for m in matches:
            home_name = (m.get("team1") or "").strip()
            away_name = (m.get("team2") or "").strip()
            if not home_name or not away_name:
                continue

            dt = _dt_from_match(m)
            if dt is None:
                continue

            score = m.get("score") or {}
            ft = score.get("ft") or []
            hg = int(ft[0]) if isinstance(ft, list) and len(ft) > 1 and ft[0] is not None else None
            ag = int(ft[1]) if isinstance(ft, list) and len(ft) > 1 and ft[1] is not None else None
            result = _result_from_scores(hg, ag)
            status = MatchStatus.completed if result is not None else MatchStatus.scheduled

            home_team = await _get_or_create_team(db, team_cache, sport.id, home_name)
            away_team = await _get_or_create_team(db, team_cache, sport.id, away_name)

            existing = await db.execute(
                select(Match).where(
                    and_(
                        Match.season_id == season.id,
                        Match.home_team_id == home_team.id,
                        Match.away_team_id == away_team.id,
                        Match.match_date == dt,
                    )
                )
            )
            row = existing.scalar_one_or_none()
            if row:
                row.status = status
                row.home_score = hg
                row.away_score = ag
                row.result = result
            else:
                db.add(
                    Match(
                        sport_id=sport.id,
                        season_id=season.id,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        match_date=dt,
                        venue="",
                        status=status,
                        home_score=hg,
                        away_score=ag,
                        result=result,
                    )
                )
                added_matches += 1

    await _rebuild_derived_tables(db)
    await db.commit()

    all_matches = (await db.execute(select(Match))).scalars().all()
    completed = sum(1 for m in all_matches if m.status == MatchStatus.completed)
    scheduled = sum(1 for m in all_matches if m.status == MatchStatus.scheduled)
    seasons_count = (await db.execute(select(Season))).scalars().all()
    teams_count = (await db.execute(select(Team))).scalars().all()

    return ImportResult(
        links_found=len(files),
        links_used=len(files),
        teams=len(teams_count),
        seasons=len(seasons_count),
        matches_total=len(all_matches),
        matches_completed=completed,
        matches_scheduled=scheduled,
        new_matches_added=added_matches,
    )
