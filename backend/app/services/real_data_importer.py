"""Import real multi-sport data from public APIs (TheSportsDB + ESPN)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen
import json
import time
from typing import Dict, List, Optional

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    AIModel,
    HeadToHead,
    Match,
    MatchResult,
    MatchStatus,
    Player,
    Prediction,
    Season,
    Sport,
    Team,
    TeamStatistics,
    User,
    UserRole,
)
from app.services.auth import hash_password

THESPORTSDB_BASE_URL = "https://www.thesportsdb.com/api/v1/json/3"
VLR_API_BASE_URL = "https://vlrggapi.vercel.app"
SEASON_CODES = ["2023-2024", "2024-2025", "2025-2026"]
THESPORTSDB_MIN_INTERVAL_SECONDS = 1.2
ESPN_MAX_CONCURRENT_REQUESTS = 8
_LAST_THESPORTSDB_CALL_TS = 0.0


@dataclass(frozen=True)
class SportImportConfig:
    key: str
    sport_name: str
    description: str
    icon: str
    provider: str
    league_name: Optional[str] = None
    league_id: Optional[str] = None
    espn_scoreboard_url: Optional[str] = None
    espn_scoreboard_urls: Optional[List[str]] = None
    espn_days_back: int = 0
    espn_days_ahead: int = 0
    espn_date_step_days: int = 1


SPORT_IMPORTS: List[SportImportConfig] = [
    SportImportConfig(
        key="football",
        sport_name="Футбол",
        description="Асоціативний футбол",
        icon="⚽",
        provider="thesportsdb_league",
        league_name="Ukrainian Premier League",
        league_id="4354",
    ),
    SportImportConfig(
        key="basketball",
        sport_name="Баскетбол",
        description="Класичний командний баскетбол",
        icon="🏀",
        provider="espn_scoreboard",
        espn_scoreboard_urls=[
            "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        ],
        espn_days_back=365,
        espn_days_ahead=30,
        espn_date_step_days=2,
    ),
    SportImportConfig(
        key="tennis",
        sport_name="Теніс",
        description="Професійний теніс",
        icon="🎾",
        provider="espn_scoreboard",
        espn_scoreboard_urls=[
            "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard",
            "https://site.api.espn.com/apis/site/v2/sports/tennis/wta/scoreboard",
        ],
        espn_days_back=180,
        espn_days_ahead=14,
        espn_date_step_days=2,
    ),
    SportImportConfig(
        key="hockey",
        sport_name="Хокей",
        description="Хокей на льоду",
        icon="🏒",
        provider="espn_scoreboard",
        espn_scoreboard_urls=[
            "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
        ],
        espn_days_back=365,
        espn_days_ahead=30,
        espn_date_step_days=2,
    ),
    SportImportConfig(
        key="volleyball",
        sport_name="Волейбол",
        description="Професійний волейбол",
        icon="🏐",
        provider="espn_scoreboard",
        espn_scoreboard_urls=[
            "https://site.api.espn.com/apis/site/v2/sports/volleyball/womens-college-volleyball/scoreboard",
            "https://site.api.espn.com/apis/site/v2/sports/volleyball/mens-college-volleyball/scoreboard",
        ],
        espn_days_back=365,
        espn_days_ahead=30,
        espn_date_step_days=7,
    ),
    SportImportConfig(
        key="esports",
        sport_name="Кіберспорт",
        description="Змагальні кіберспортивні дисципліни",
        icon="🎮",
        provider="vlr_api",
        league_name="VLR Valorant",
    ),
]


def _fetch_json_url(url: str, retries: int = 5, sleep_base: float = 1.0) -> dict:
    for attempt in range(retries):
        try:
            with urlopen(url, timeout=30) as resp:
                payload = resp.read().decode("utf-8")
            return json.loads(payload)
        except HTTPError as exc:
            if exc.code == 429 and attempt < retries - 1:
                time.sleep(sleep_base * (attempt + 1))
                continue
            raise

    return {}


def _fetch_thesportsdb(path: str, params: Optional[dict] = None) -> dict:
    global _LAST_THESPORTSDB_CALL_TS

    now = time.time()
    wait_for = THESPORTSDB_MIN_INTERVAL_SECONDS - (now - _LAST_THESPORTSDB_CALL_TS)
    if wait_for > 0:
        time.sleep(wait_for)

    query = f"?{urlencode(params)}" if params else ""
    url = f"{THESPORTSDB_BASE_URL}/{path}{query}"
    payload = _fetch_json_url(url)
    _LAST_THESPORTSDB_CALL_TS = time.time()
    return payload


def _fetch_vlr(path: str, params: Optional[dict] = None) -> dict:
    query = f"?{urlencode(params)}" if params else ""
    url = f"{VLR_API_BASE_URL}/{path}{query}"
    return _fetch_json_url(url, retries=3, sleep_base=0.5)


async def _fetch_json_url_async(url: str, retries: int = 5, sleep_base: float = 1.0) -> dict:
    return await asyncio.to_thread(_fetch_json_url, url, retries, sleep_base)


def _parse_int(value) -> Optional[int]:
    if value in (None, "", "null"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_dt(date_event: Optional[str], time_event: Optional[str]) -> datetime:
    if not date_event:
        return datetime.utcnow()

    safe_time = (time_event or "18:00:00").split("+")[0].strip()
    if len(safe_time) == 5:
        safe_time += ":00"
    try:
        return datetime.fromisoformat(f"{date_event} {safe_time}")
    except ValueError:
        return datetime.fromisoformat(f"{date_event} 18:00:00")


def _season_date_range(season_name: str) -> tuple[date, date]:
    try:
        start_y, end_y = season_name.split("-")
        return date(int(start_y), 7, 1), date(int(end_y), 6, 30)
    except Exception:
        year = int(season_name)
        return date(year, 1, 1), date(year, 12, 31)


def _season_code_from_datetime(dt: datetime) -> str:
    if dt.month >= 7:
        return f"{dt.year}-{dt.year + 1}"
    return f"{dt.year - 1}-{dt.year}"


def _safe_name(value: Optional[str], fallback: str) -> str:
    cleaned = (value or "").strip()
    return cleaned or fallback


def _build_espn_scoreboard_urls(base_url: str, config: SportImportConfig) -> List[str]:
    urls = [base_url]
    step_days = max(1, int(config.espn_date_step_days or 1))
    start_day = datetime.utcnow().date() - timedelta(days=max(0, config.espn_days_back))
    end_day = datetime.utcnow().date() + timedelta(days=max(0, config.espn_days_ahead))

    day = start_day
    while day <= end_day:
        date_code = day.strftime("%Y%m%d")
        sep = "&" if "?" in base_url else "?"
        urls.append(f"{base_url}{sep}dates={date_code}")
        day += timedelta(days=step_days)

    return urls


async def _fetch_espn_payloads(urls: List[str], quality: dict) -> List[dict]:
    semaphore = asyncio.Semaphore(ESPN_MAX_CONCURRENT_REQUESTS)

    async def fetch_one(url: str) -> dict | None:
        try:
            async with semaphore:
                return await _fetch_json_url_async(url, retries=3, sleep_base=0.4)
        except Exception as exc:
            quality["provider_errors"].append(f"espn_fetch_error:{url}:{exc}")
            return None

    results = await asyncio.gather(*(fetch_one(url) for url in urls))
    return [payload for payload in results if payload]


def _parse_vlr_completed_time(value: str) -> datetime:
    # Examples: "1d 2h ago", "5h 20m ago"
    now = datetime.utcnow()
    text = (value or "").strip().lower()
    if not text.endswith("ago"):
        return now

    minutes = 0
    tokens = text.replace("ago", "").strip().split()
    for token in tokens:
        if token.endswith("d"):
            minutes += int(token[:-1]) * 24 * 60
        elif token.endswith("h"):
            minutes += int(token[:-1]) * 60
        elif token.endswith("m"):
            minutes += int(token[:-1])

    return now if minutes <= 0 else now.replace(microsecond=0) - timedelta(minutes=minutes)


def _parse_vlr_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        pass

    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.utcnow()


def _init_quality_report() -> dict:
    return {
        "teams_missing_country": 0,
        "teams_missing_city": 0,
        "teams_missing_badge": 0,
        "events_missing_team_names": 0,
        "events_unknown_teams": 0,
        "events_missing_datetime": 0,
        "events_completed": 0,
        "events_scheduled": 0,
        "events_upserted": 0,
        "provider_errors": [],
    }


async def _ensure_default_users(db: AsyncSession) -> None:
    existing = (await db.execute(select(User.id))).scalars().first()
    if existing:
        return

    users = [
        User(username="admin", email="admin@sportpredict.ua", password_hash=hash_password("admin123"), role=UserRole.admin),
        User(username="analyst", email="analyst@sportpredict.ua", password_hash=hash_password("analyst123"), role=UserRole.analyst),
        User(username="user", email="user@sportpredict.ua", password_hash=hash_password("user123"), role=UserRole.user),
    ]
    db.add_all(users)


async def _ensure_sport(db: AsyncSession, config: SportImportConfig) -> Sport:
    r = await db.execute(select(Sport).where(Sport.name == config.sport_name))
    sport = r.scalar_one_or_none()
    if sport:
        sport.description = sport.description or config.description
        sport.icon = sport.icon or config.icon
        return sport

    sport = Sport(name=config.sport_name, description=config.description, icon=config.icon)
    db.add(sport)
    await db.flush()
    return sport


async def _get_or_create_season(db: AsyncSession, sport_id: int, league_name: str, season_name: str) -> Season:
    display = f"{league_name} {season_name.replace('-', '/')}"
    r = await db.execute(select(Season).where(and_(Season.sport_id == sport_id, Season.name == display)))
    season = r.scalar_one_or_none()
    if season:
        return season

    start_date, end_date = _season_date_range(season_name)
    season = Season(sport_id=sport_id, name=display, start_date=start_date, end_date=end_date)
    db.add(season)
    await db.flush()
    return season


async def _get_or_create_team(db: AsyncSession, sport_id: int, name: str) -> Team:
    r = await db.execute(select(Team).where(and_(Team.sport_id == sport_id, Team.name == name)))
    team = r.scalar_one_or_none()
    if team:
        return team

    team = Team(sport_id=sport_id, name=name, country="", city="", logo_url="")
    db.add(team)
    await db.flush()
    return team


async def _upsert_match(
    db: AsyncSession,
    sport_id: int,
    season_id: int,
    home_team_id: int,
    away_team_id: int,
    dt: datetime,
    venue: str,
    status: MatchStatus,
    home_score: Optional[int],
    away_score: Optional[int],
    result: Optional[MatchResult],
    quality: dict,
) -> int:
    existing = await db.execute(
        select(Match).where(
            and_(
                Match.season_id == season_id,
                Match.home_team_id == home_team_id,
                Match.away_team_id == away_team_id,
                Match.match_date == dt,
            )
        )
    )
    match = existing.scalar_one_or_none()
    if match:
        match.status = status
        match.home_score = home_score
        match.away_score = away_score
        match.result = result
        match.venue = venue or match.venue
        return 0

    db.add(
        Match(
            sport_id=sport_id,
            season_id=season_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            match_date=dt,
            venue=venue,
            status=status,
            home_score=home_score,
            away_score=away_score,
            result=result,
        )
    )
    quality["events_upserted"] += 1
    return 1


async def _import_events_payload(
    db: AsyncSession,
    sport_id: int,
    league_name: str,
    teams_map: Dict[str, Team],
    events: List[dict],
    quality: dict,
) -> int:
    imported = 0
    season_cache: Dict[str, Season] = {}

    for ev in events:
        home_name = _safe_name(ev.get("strHomeTeam"), "")
        away_name = _safe_name(ev.get("strAwayTeam"), "")
        if not home_name or not away_name:
            quality["events_missing_team_names"] += 1
            continue

        home_team = teams_map.get(home_name) or await _get_or_create_team(db, sport_id, home_name)
        away_team = teams_map.get(away_name) or await _get_or_create_team(db, sport_id, away_name)
        teams_map[home_name] = home_team
        teams_map[away_name] = away_team

        dt = _parse_dt(ev.get("dateEvent"), ev.get("strTime"))
        if not ev.get("dateEvent"):
            quality["events_missing_datetime"] += 1

        season_code = (ev.get("strSeason") or "").strip() or _season_code_from_datetime(dt)
        season = season_cache.get(season_code)
        if season is None:
            season = await _get_or_create_season(db, sport_id, league_name, season_code)
            season_cache[season_code] = season

        home_score = _parse_int(ev.get("intHomeScore"))
        away_score = _parse_int(ev.get("intAwayScore"))
        if home_score is not None and away_score is not None:
            status = MatchStatus.completed
            quality["events_completed"] += 1
            if home_score > away_score:
                result = MatchResult.home_win
            elif away_score > home_score:
                result = MatchResult.away_win
            else:
                result = MatchResult.draw
        else:
            status = MatchStatus.scheduled
            result = None
            quality["events_scheduled"] += 1

        imported += await _upsert_match(
            db,
            sport_id,
            season.id,
            home_team.id,
            away_team.id,
            dt,
            _safe_name(ev.get("strVenue"), ""),
            status,
            home_score,
            away_score,
            result,
            quality,
        )

    return imported


async def _import_thesportsdb_league(db: AsyncSession, config: SportImportConfig, sport: Sport, quality: dict) -> int:
    if not config.league_name or not config.league_id:
        quality["provider_errors"].append("league_name_or_id_missing")
        return 0

    teams_raw = _fetch_thesportsdb("search_all_teams.php", {"l": config.league_name}).get("teams") or []
    teams_map: Dict[str, Team] = {}
    for item in teams_raw:
        team_name = _safe_name(item.get("strTeam"), "")
        if not team_name:
            continue
        team = await _get_or_create_team(db, sport.id, team_name)
        team.country = team.country or _safe_name(item.get("strCountry"), "")
        team.city = team.city or _safe_name(item.get("strStadiumLocation"), "")
        team.logo_url = team.logo_url or _safe_name(item.get("strBadge"), "")
        team.founded_year = team.founded_year or _parse_int(item.get("intFormedYear"))
        teams_map[team_name] = team

        if not team.country:
            quality["teams_missing_country"] += 1
        if not team.city:
            quality["teams_missing_city"] += 1
        if not team.logo_url:
            quality["teams_missing_badge"] += 1

    imported = 0
    for season_code in SEASON_CODES:
        payload = _fetch_thesportsdb("eventsseason.php", {"id": config.league_id, "s": season_code})
        imported += await _import_events_payload(
            db,
            sport.id,
            config.league_name,
            teams_map,
            payload.get("events") or [],
            quality,
        )

    payload_past = _fetch_thesportsdb("eventspastleague.php", {"id": config.league_id})
    imported += await _import_events_payload(
        db,
        sport.id,
        config.league_name,
        teams_map,
        payload_past.get("events") or [],
        quality,
    )

    payload_next = _fetch_thesportsdb("eventsnextleague.php", {"id": config.league_id})
    imported += await _import_events_payload(
        db,
        sport.id,
        config.league_name,
        teams_map,
        payload_next.get("events") or [],
        quality,
    )

    return imported


async def _import_thesportsdb_team_events(db: AsyncSession, config: SportImportConfig, sport: Sport, quality: dict) -> int:
    candidate_leagues = [name for name in [config.league_name] if name]
    if config.key == "esports":
        candidate_leagues.extend([
            "LCS",
            "LEC",
            "LCK",
            "Overwatch League",
            "Call of Duty League",
        ])

    teams_raw = []
    selected_league = None
    for league_name in candidate_leagues:
        teams_raw = _fetch_thesportsdb("search_all_teams.php", {"l": league_name}).get("teams") or []
        if teams_raw:
            selected_league = league_name
            break

    if not teams_raw:
        quality["provider_errors"].append("no_teams_for_league")
        return 0

    teams_map: Dict[str, Team] = {}
    source_team_ids: List[str] = []
    for item in teams_raw:
        team_name = _safe_name(item.get("strTeam"), "")
        if not team_name:
            continue
        team = await _get_or_create_team(db, sport.id, team_name)
        team.country = team.country or _safe_name(item.get("strCountry"), "")
        team.city = team.city or _safe_name(item.get("strStadiumLocation"), "")
        team.logo_url = team.logo_url or _safe_name(item.get("strBadge"), "")
        teams_map[team_name] = team
        team_id = _safe_name(item.get("idTeam"), "")
        if team_id:
            source_team_ids.append(team_id)

    seen_event_ids = set()
    merged_events: List[dict] = []
    for team_id in source_team_ids[:8]:
        for endpoint in ["eventslast.php", "eventsnext.php"]:
            payload = _fetch_thesportsdb(endpoint, {"id": team_id})
            events = payload.get("results") or payload.get("events") or []
            for ev in events:
                ev_id = _safe_name(ev.get("idEvent"), "")
                if ev_id and ev_id in seen_event_ids:
                    continue
                if ev_id:
                    seen_event_ids.add(ev_id)
                merged_events.append(ev)

    return await _import_events_payload(db, sport.id, selected_league or (config.league_name or sport.name), teams_map, merged_events, quality)


async def _import_vlr_esports(db: AsyncSession, config: SportImportConfig, sport: Sport, quality: dict) -> int:
    league_name = config.league_name or "VLR Valorant"
    imported = 0
    teams_map: Dict[str, Team] = {}

    # Completed matches.
    results_payload = _fetch_vlr("match", {"q": "results"})
    result_segments = ((results_payload.get("data") or {}).get("segments") or [])
    for seg in result_segments:
        team1 = _safe_name(seg.get("team1"), "")
        team2 = _safe_name(seg.get("team2"), "")
        if not team1 or not team2:
            quality["events_missing_team_names"] += 1
            continue

        dt = _parse_vlr_completed_time(_safe_name(seg.get("time_completed"), ""))
        season_code = _season_code_from_datetime(dt)
        season = await _get_or_create_season(db, sport.id, league_name, season_code)

        home_team = teams_map.get(team1) or await _get_or_create_team(db, sport.id, team1)
        away_team = teams_map.get(team2) or await _get_or_create_team(db, sport.id, team2)
        teams_map[team1] = home_team
        teams_map[team2] = away_team

        score1 = _parse_int(seg.get("score1"))
        score2 = _parse_int(seg.get("score2"))
        if score1 is None or score2 is None:
            quality["events_missing_team_names"] += 1
            continue

        quality["events_completed"] += 1
        if score1 > score2:
            result = MatchResult.home_win
        elif score2 > score1:
            result = MatchResult.away_win
        else:
            result = MatchResult.draw

        imported += await _upsert_match(
            db,
            sport.id,
            season.id,
            home_team.id,
            away_team.id,
            dt,
            _safe_name(seg.get("tournament_name"), ""),
            MatchStatus.completed,
            score1,
            score2,
            result,
            quality,
        )

    # Upcoming matches.
    upcoming_payload = _fetch_vlr("match", {"q": "upcoming"})
    upcoming_segments = ((upcoming_payload.get("data") or {}).get("segments") or [])
    for seg in upcoming_segments:
        team1 = _safe_name(seg.get("team1"), "")
        team2 = _safe_name(seg.get("team2"), "")
        if not team1 or not team2:
            quality["events_missing_team_names"] += 1
            continue

        dt = _parse_vlr_timestamp(_safe_name(seg.get("unix_timestamp"), ""))
        season_code = _season_code_from_datetime(dt)
        season = await _get_or_create_season(db, sport.id, league_name, season_code)

        home_team = teams_map.get(team1) or await _get_or_create_team(db, sport.id, team1)
        away_team = teams_map.get(team2) or await _get_or_create_team(db, sport.id, team2)
        teams_map[team1] = home_team
        teams_map[team2] = away_team

        quality["events_scheduled"] += 1
        imported += await _upsert_match(
            db,
            sport.id,
            season.id,
            home_team.id,
            away_team.id,
            dt,
            _safe_name(seg.get("match_event"), ""),
            MatchStatus.scheduled,
            None,
            None,
            None,
            quality,
        )

    return imported


async def _import_espn_scoreboard(db: AsyncSession, config: SportImportConfig, sport: Sport, quality: dict) -> int:
    urls = config.espn_scoreboard_urls or ([config.espn_scoreboard_url] if config.espn_scoreboard_url else [])
    if not urls:
        quality["provider_errors"].append("espn_scoreboard_url_missing")
        return 0

    events: List[dict] = []
    for base_url in urls:
        payloads = await _fetch_espn_payloads(_build_espn_scoreboard_urls(base_url, config), quality)
        for payload in payloads:
            events.extend(payload.get("events") or [])

    imported = 0

    teams_map: Dict[str, Team] = {}
    league_name = f"ESPN {config.sport_name}"
    season_cache: Dict[str, Season] = {}
    seen_competitions = set()

    for event in events:
        event_id = _safe_name(event.get("id"), "")
        competition_list = event.get("competitions") or []
        if not competition_list:
            # Tennis scoreboard uses event.groupings[*].competitions[*].
            for grouping in event.get("groupings") or []:
                competition_list.extend(grouping.get("competitions") or [])

        for competition in competition_list:
            competition_id = _safe_name(competition.get("id"), "")
            dedupe_key = (event_id, competition_id)
            if dedupe_key in seen_competitions:
                continue
            seen_competitions.add(dedupe_key)

            dt_raw = competition.get("date") or event.get("date") or ""
            try:
                dt = datetime.fromisoformat(dt_raw.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                dt = datetime.utcnow()
                quality["events_missing_datetime"] += 1

            competitors = competition.get("competitors") or []
            if len(competitors) < 2:
                quality["events_missing_team_names"] += 1
                continue

            home = None
            away = None
            for comp in competitors:
                if comp.get("homeAway") == "home":
                    home = comp
                elif comp.get("homeAway") == "away":
                    away = comp

            if home is None or away is None:
                home, away = competitors[0], competitors[1]

            home_name = _safe_name(
                (home.get("team") or {}).get("displayName"),
                _safe_name(
                    (home.get("athlete") or {}).get("displayName"),
                    _safe_name(home.get("displayName"), ""),
                ),
            )
            away_name = _safe_name(
                (away.get("team") or {}).get("displayName"),
                _safe_name(
                    (away.get("athlete") or {}).get("displayName"),
                    _safe_name(away.get("displayName"), ""),
                ),
            )
            if not home_name or not away_name:
                quality["events_missing_team_names"] += 1
                continue

            home_team = teams_map.get(home_name) or await _get_or_create_team(db, sport.id, home_name)
            away_team = teams_map.get(away_name) or await _get_or_create_team(db, sport.id, away_name)
            teams_map[home_name] = home_team
            teams_map[away_name] = away_team

            home_score = _parse_int(home.get("score"))
            away_score = _parse_int(away.get("score"))
            completed = bool(((competition.get("status") or {}).get("type") or {}).get("completed"))
            if completed and home_score is not None and away_score is not None:
                status = MatchStatus.completed
                quality["events_completed"] += 1
                if home_score > away_score:
                    result = MatchResult.home_win
                elif away_score > home_score:
                    result = MatchResult.away_win
                else:
                    result = MatchResult.draw
            else:
                status = MatchStatus.scheduled
                result = None
                quality["events_scheduled"] += 1

            season_code = _season_code_from_datetime(dt)
            season = season_cache.get(season_code)
            if season is None:
                season = await _get_or_create_season(db, sport.id, league_name, season_code)
                season_cache[season_code] = season

            imported += await _upsert_match(
                db,
                sport.id,
                season.id,
                home_team.id,
                away_team.id,
                dt,
                _safe_name((competition.get("venue") or {}).get("fullName"), ""),
                status,
                home_score,
                away_score,
                result,
                quality,
            )

    return imported


async def _import_sport_dataset(db: AsyncSession, config: SportImportConfig) -> dict:
    quality = _init_quality_report()
    sport = await _ensure_sport(db, config)
    print(f"[Import] {config.sport_name}: provider={config.provider}")

    try:
        if config.provider == "thesportsdb_league":
            imported = await _import_thesportsdb_league(db, config, sport, quality)
            league_name = config.league_name
        elif config.provider == "espn_scoreboard":
            imported = await _import_espn_scoreboard(db, config, sport, quality)
            league_name = "ESPN scoreboard"
        elif config.provider == "thesportsdb_team_events":
            imported = await _import_thesportsdb_team_events(db, config, sport, quality)
            league_name = config.league_name
        elif config.provider == "vlr_api":
            imported = await _import_vlr_esports(db, config, sport, quality)
            league_name = config.league_name or "VLR Valorant"
        else:
            imported = 0
            league_name = None
            quality["provider_errors"].append("unknown_provider")
    except Exception as exc:
        imported = 0
        league_name = config.league_name
        quality["provider_errors"].append(str(exc))

    team_count = len((await db.execute(select(Team).where(Team.sport_id == sport.id))).scalars().all())
    match_count = len((await db.execute(select(Match).where(Match.sport_id == sport.id))).scalars().all())

    return {
        "sport": config.sport_name,
        "league": league_name,
        "teams": team_count,
        "matches": match_count,
        "new_matches_added": imported,
        "quality": quality,
    }


async def _rebuild_stats_and_h2h(db: AsyncSession) -> None:
    await db.execute(delete(TeamStatistics))
    await db.execute(delete(HeadToHead))

    seasons = (await db.execute(select(Season))).scalars().all()
    teams = (await db.execute(select(Team))).scalars().all()

    for season in seasons:
        season_teams = [t for t in teams if t.sport_id == season.sport_id]
        for team in season_teams:
            q = await db.execute(
                select(Match).where(
                    and_(
                        Match.season_id == season.id,
                        Match.status == MatchStatus.completed,
                        (Match.home_team_id == team.id) | (Match.away_team_id == team.id),
                    )
                )
            )
            mlist = q.scalars().all()
            if not mlist:
                continue

            w = d = l = gf = ga = 0
            form: List[str] = []
            for m in sorted(mlist, key=lambda x: x.match_date):
                is_home = m.home_team_id == team.id
                hg = m.home_score or 0
                ag = m.away_score or 0
                gf += hg if is_home else ag
                ga += ag if is_home else hg

                if m.result == MatchResult.draw:
                    d += 1
                    form.append("D")
                elif (m.result == MatchResult.home_win and is_home) or (m.result == MatchResult.away_win and not is_home):
                    w += 1
                    form.append("W")
                else:
                    l += 1
                    form.append("L")

            existing_ts = await db.execute(
                select(TeamStatistics).where(
                    and_(TeamStatistics.team_id == team.id, TeamStatistics.season_id == season.id)
                )
            )
            ts = existing_ts.scalar_one_or_none()
            if ts is None:
                ts = TeamStatistics(team_id=team.id, season_id=season.id)
                db.add(ts)

            ts.matches_played = len(mlist)
            ts.wins = w
            ts.draws = d
            ts.losses = l
            ts.goals_for = gf
            ts.goals_against = ga
            ts.points = w * 3 + d
            ts.form_last5 = form[-5:]

    for sport in (await db.execute(select(Sport))).scalars().all():
        sport_teams = [t for t in teams if t.sport_id == sport.id]
        for i in range(len(sport_teams)):
            for j in range(i + 1, len(sport_teams)):
                t1, t2 = sport_teams[i], sport_teams[j]
                q = await db.execute(
                    select(Match).where(
                        and_(
                            Match.status == MatchStatus.completed,
                            (
                                ((Match.home_team_id == t1.id) & (Match.away_team_id == t2.id))
                                | ((Match.home_team_id == t2.id) & (Match.away_team_id == t1.id))
                            ),
                        )
                    )
                )
                mlist = q.scalars().all()
                if not mlist:
                    continue

                t1w = t2w = dr = 0
                for m in mlist:
                    if m.result == MatchResult.draw:
                        dr += 1
                    elif m.result == MatchResult.home_win:
                        if m.home_team_id == t1.id:
                            t1w += 1
                        else:
                            t2w += 1
                    elif m.result == MatchResult.away_win:
                        if m.away_team_id == t1.id:
                            t1w += 1
                        else:
                            t2w += 1

                existing_h2h = await db.execute(
                    select(HeadToHead).where(
                        and_(HeadToHead.team1_id == t1.id, HeadToHead.team2_id == t2.id)
                    )
                )
                h2h = existing_h2h.scalar_one_or_none()
                if h2h is None:
                    h2h = HeadToHead(team1_id=t1.id, team2_id=t2.id)
                    db.add(h2h)

                h2h.total_matches = len(mlist)
                h2h.team1_wins = t1w
                h2h.team2_wins = t2w
                h2h.draws = dr


async def import_real_data(db: AsyncSession, reset_existing: bool = False) -> dict:
    """Import real multi-sport data and recompute derived statistics."""
    if reset_existing:
        await db.execute(delete(Prediction))
        await db.execute(delete(AIModel))
        await db.execute(delete(HeadToHead))
        await db.execute(delete(TeamStatistics))
        await db.execute(delete(Player))
        await db.execute(delete(Match))
        await db.execute(delete(Season))
        await db.execute(delete(Team))
        await db.execute(delete(Sport))

    await _ensure_default_users(db)

    per_sport = []
    for config in SPORT_IMPORTS:
        summary = await _import_sport_dataset(db, config)
        per_sport.append(summary)
        print(
            f"[Import] {summary['sport']}: teams={summary['teams']} matches={summary['matches']} "
            f"new={summary['new_matches_added']} errors={len((summary['quality'] or {}).get('provider_errors') or [])}"
        )

    await _rebuild_stats_and_h2h(db)
    await db.commit()

    all_matches = (await db.execute(select(Match))).scalars().all()
    completed = [m for m in all_matches if m.status == MatchStatus.completed]
    scheduled = [m for m in all_matches if m.status == MatchStatus.scheduled]

    return {
        "sports": len((await db.execute(select(Sport))).scalars().all()),
        "teams": len((await db.execute(select(Team))).scalars().all()),
        "matches": len(all_matches),
        "completed_matches": len(completed),
        "scheduled_matches": len(scheduled),
        "new_matches_added": sum(item.get("new_matches_added", 0) for item in per_sport),
        "per_sport": per_sport,
    }


async def import_esports_data(db: AsyncSession) -> dict:
    """Import only esports matches from configured real providers."""
    esports_config = next((cfg for cfg in SPORT_IMPORTS if cfg.key == "esports"), None)
    if esports_config is None:
        return {"sport": "Кіберспорт", "error": "esports_config_missing"}

    summary = await _import_sport_dataset(db, esports_config)
    await _rebuild_stats_and_h2h(db)
    await db.commit()
    return summary
