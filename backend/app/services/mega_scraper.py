"""
MegaScraper — comprehensive multi-sport data importer using ESPN public API.

Fetches without any API key:
  - Match schedules + live/final scores (scoreboard endpoint)
  - Full match details: lineups, player stats, in-game events, team stats (summary endpoint)
  - Player rosters per team (roster endpoint)

Covers: soccer (5 top leagues + UCL), basketball (NBA), hockey (NHL), tennis (ATP/WTA).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Set, Tuple
from urllib.error import HTTPError
from urllib.request import urlopen
import json
import time
import logging

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    HeadToHead, Match, MatchEvent, MatchLineup, MatchResult,
    MatchStatLine, MatchStatus, Player, Prediction, Season, Sport, Team,
    TeamStatistics, User, UserRole,
)
from app.services.auth import hash_password
from app.services.avatar_scraper import fetch_external_player_photo_url

logger = logging.getLogger(__name__)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_CORE = "https://sports.core.api.espn.com/v2/sports"
MAX_CONCURRENT = 6
_RATE_LOCK = asyncio.Lock()
_LAST_CALL_TS: float = 0.0
_MIN_INTERVAL = 0.25  # seconds between ESPN requests


# ── League configuration ────────────────────────────────────────────────────

@dataclass
class LeagueConfig:
    espn_sport: str
    espn_league: str
    sport_name: str
    league_name: str
    icon: str
    days_back: int = 60
    days_ahead: int = 30
    step_days: int = 7
    fetch_rosters: bool = True
    allows_draw: bool = True


LEAGUES: List[LeagueConfig] = [
    # ── Soccer ──────────────────────────────────────────────
    LeagueConfig("soccer", "eng.1",         "Футбол", "Premier League",       "⚽"),
    LeagueConfig("soccer", "esp.1",         "Футбол", "La Liga",              "⚽"),
    LeagueConfig("soccer", "ger.1",         "Футбол", "Bundesliga",           "⚽"),
    LeagueConfig("soccer", "ita.1",         "Футбол", "Serie A",              "⚽"),
    LeagueConfig("soccer", "fra.1",         "Футбол", "Ligue 1",              "⚽"),
    LeagueConfig("soccer", "uefa.champions","Футбол", "Champions League",     "⚽"),
    LeagueConfig("soccer", "ukr.1",         "Футбол", "УПЛ",                  "⚽"),
    # ── Basketball ──────────────────────────────────────────
    LeagueConfig("basketball", "nba",       "Баскетбол", "NBA",               "🏀", allows_draw=False),
    # ── Hockey ──────────────────────────────────────────────
    LeagueConfig("hockey", "nhl",           "Хокей", "NHL",                  "🏒", allows_draw=False),
    # ── Tennis ──────────────────────────────────────────────
    LeagueConfig("tennis", "atp",           "Теніс", "ATP Tour",             "🎾", days_ahead=14, allows_draw=False),
    LeagueConfig("tennis", "wta",           "Теніс", "WTA Tour",             "🎾", days_ahead=14, allows_draw=False),
]

# ── HTTP helpers ────────────────────────────────────────────────────────────

def _http_get(url: str, retries: int = 4, sleep_base: float = 1.0) -> dict:
    for attempt in range(retries):
        try:
            with urlopen(url, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8", errors="ignore"))
        except HTTPError as exc:
            if exc.code in (429, 503) and attempt < retries - 1:
                time.sleep(sleep_base * (2 ** attempt))
                continue
            if exc.code == 404:
                return {}
            raise
        except Exception:
            if attempt < retries - 1:
                time.sleep(sleep_base)
            else:
                raise
    return {}


async def _http_get_async(url: str) -> dict:
    global _LAST_CALL_TS
    async with _RATE_LOCK:
        wait = _MIN_INTERVAL - (time.time() - _LAST_CALL_TS)
        if wait > 0:
            await asyncio.sleep(wait)
        _LAST_CALL_TS = time.time()
    try:
        return await asyncio.to_thread(_http_get, url)
    except Exception as exc:
        logger.debug("ESPN fetch failed %s: %s", url, exc)
        return {}


# ── Parsing helpers ─────────────────────────────────────────────────────────

def _safe_str(v, fallback: str = "") -> str:
    if v is None:
        return fallback
    if isinstance(v, str):
        return v.strip() or fallback
    return str(v).strip() or fallback


def _safe_int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _parse_espn_dt(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _tennis_competitor_name(competitor: dict) -> str:
    roster = competitor.get("roster") or {}
    roster_name = _safe_str(roster.get("displayName"))
    if roster_name:
        return roster_name

    athletes = roster.get("athletes") or []
    athlete_names = [
        _safe_str(a.get("displayName") or a.get("fullName"))
        for a in athletes
        if _safe_str(a.get("displayName") or a.get("fullName"))
    ]
    if athlete_names:
        return " / ".join(athlete_names)

    athlete = competitor.get("athlete") or {}
    team = competitor.get("team") or {}
    return _safe_str(
        athlete.get("displayName")
        or athlete.get("fullName")
        or team.get("displayName")
        or team.get("name")
    )


def _tennis_competitor_score(competitor: dict) -> Optional[int]:
    values = [
        _safe_int((line or {}).get("value"))
        for line in (competitor.get("linescores") or [])
    ]
    parsed = [value for value in values if value is not None]
    return sum(parsed) if parsed else None


def _normalize_scoreboard_events(espn_sport: str, events: List[dict]) -> List[dict]:
    """Normalize ESPN scoreboard payloads to event objects consumable by the importer.

    Tennis scoreboards expose live matches inside groupings[].competitions[] instead of
    top-level events. Flatten them into the standard event/competition shape used by the
    rest of the import pipeline.
    """
    if espn_sport != "tennis":
        normalized: List[dict] = []
        seen_ids: set = set()
        for ev in events:
            eid = _safe_str(ev.get("id"))
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                normalized.append(ev)
        return normalized

    normalized: List[dict] = []
    seen_ids: set = set()

    for ev in events:
        for grouping in (ev.get("groupings") or []):
            for comp in (grouping.get("competitions") or []):
                comp_id = _safe_str(comp.get("id"))
                if not comp_id or comp_id in seen_ids:
                    continue

                competitors = comp.get("competitors") or []
                if len(competitors) < 2:
                    continue

                mapped_competitors = []
                for index, competitor in enumerate(competitors[:2]):
                    name = _tennis_competitor_name(competitor)
                    if not name:
                        continue

                    mapped_competitors.append({
                        "homeAway": competitor.get("homeAway") or ("home" if index == 0 else "away"),
                        "score": _tennis_competitor_score(competitor),
                        "team": {
                            "id": _safe_str(competitor.get("id")),
                            "displayName": name,
                            "name": name,
                        },
                    })

                if len(mapped_competitors) < 2:
                    continue

                normalized.append({
                    "id": comp_id,
                    "date": comp.get("date") or ev.get("date"),
                    "status": comp.get("status") or {},
                    "competitions": [{
                        "date": comp.get("date") or ev.get("date"),
                        "status": comp.get("status") or {},
                        "venue": comp.get("venue") or ev.get("venue") or {},
                        "competitors": mapped_competitors,
                    }],
                })
                seen_ids.add(comp_id)

    return normalized


def _season_code(dt: datetime) -> str:
    if dt.month >= 7:
        return f"{dt.year}-{dt.year + 1}"
    return f"{dt.year - 1}-{dt.year}"


def _parse_stat_val(raw_val: str) -> float | int | None:
    try:
        f = float(raw_val.replace("%", "").replace(",", ".").strip())
        return int(f) if f == int(f) else f
    except (ValueError, TypeError):
        return None


def _extract_athlete_photo_url(athlete: dict, espn_sport: Optional[str] = None) -> Optional[str]:
    """Return the best available photo URL from ESPN athlete payload."""
    if not athlete:
        return None

    headshot = athlete.get("headshot") or {}
    direct = _safe_str(headshot.get("href"))
    if direct:
        return direct

    for item in (athlete.get("headshots") or []):
        href = _safe_str((item or {}).get("href"))
        if href:
            return href

    image = athlete.get("image") or {}
    image_href = _safe_str(image.get("href"))
    if image_href:
        return image_href

    for item in (athlete.get("images") or []):
        href = _safe_str((item or {}).get("href"))
        if href:
            return href

    athlete_id = _safe_str(athlete.get("id"))
    if not athlete_id:
        return None

    # ESPN roster payload often omits direct headshot URL, but CDN follows a stable pattern.
    sport_cdn = {
        "soccer": "soccer",
        "basketball": "nba",
        "hockey": "nhl",
        "tennis": "tennis",
    }.get((espn_sport or "").lower(), "soccer")

    return f"https://a.espncdn.com/i/headshots/{sport_cdn}/players/full/{athlete_id}.png"


# ── ESPN stat-name → our model key mapping ──────────────────────────────────

_STAT_NAME_MAP = {
    # soccer
    "possessionPct":      "possession",
    "possession":         "possession",
    "shots":              "shots",
    "shotsOnTarget":      "shots_on_target",
    "blockedShots":       "blocked_shots",
    "corners":            "corners",
    "fouls":              "fouls",
    "yellowCards":        "yellow_cards",
    "redCards":           "red_cards",
    "offsides":           "offsides",
    "saves":              "saves",
    "goalKicks":          "goal_kicks",
    "passAccuracy":       "pass_accuracy",
    "totalPasses":        "total_passes",
    "accuratePasses":     "accurate_passes",
    "tackles":            "tackles",
    "clearances":         "clearances",
    "interceptions":      "interceptions",
    # basketball
    "points":             "points",
    "rebounds":           "rebounds",
    "assists":            "assists",
    "steals":             "steals",
    "blocks":             "blocks",
    "turnovers":          "turnovers",
    "fieldGoalPct":       "fg_pct",
    "threePointPct":      "three_pct",
    "freeThrowPct":       "ft_pct",
    "fieldGoalsMade":     "fg_made",
    "fieldGoalsAttempted":"fg_attempts",
    "threePointMade":     "three_made",
    "threePointAttempted":"three_attempts",
    "freeThrowsMade":     "ft_made",
    "freeThrowsAttempted":"ft_attempts",
    "offensiveRebounds":  "off_rebounds",
    "defensiveRebounds":  "def_rebounds",
    # hockey
    "shotsPeriod":        "shots",
    "powerPlayGoals":     "pp_goals",
    "powerPlayOpportunities": "pp_opp",
    "faceOffWinPercentage": "faceoff_pct",
    "penaltyMinutes":     "penalty_minutes",
    "hits":               "hits",
    "giveaways":          "giveaways",
    "takeaways":          "takeaways",
}

_EVENT_TYPE_MAP = {
    "1":  "goal",
    "2":  "yellow_card",
    "3":  "red_card",
    "4":  "substitution",
    "5":  "assist",
    "13": "yellow_red_card",
    "14": "own_goal",
    # non-numeric ESPN type.text fallbacks handled in parser
}


# ── DB helpers ──────────────────────────────────────────────────────────────

async def _ensure_users(db: AsyncSession) -> None:
    if (await db.execute(select(User.id))).scalars().first():
        return
    db.add_all([
        User(username="admin",   email="admin@sportpredict.ua",   password_hash=hash_password("admin123"),   role=UserRole.admin),
        User(username="analyst", email="analyst@sportpredict.ua", password_hash=hash_password("analyst123"), role=UserRole.analyst),
        User(username="user",    email="user@sportpredict.ua",    password_hash=hash_password("user123"),    role=UserRole.user),
    ])


async def _ensure_sport(db: AsyncSession, cfg: LeagueConfig) -> Sport:
    r = await db.execute(select(Sport).where(Sport.name == cfg.sport_name))
    sport = r.scalar_one_or_none()
    if sport:
        sport.icon = sport.icon or cfg.icon
        return sport
    sport = Sport(name=cfg.sport_name, description=f"{cfg.sport_name} — professional sport", icon=cfg.icon)
    db.add(sport)
    await db.flush()
    return sport


async def _ensure_season(
    db: AsyncSession,
    sport_id: int,
    league_name: str,
    season_code: str,
    espn_sport: Optional[str] = None,
    espn_league: Optional[str] = None,
) -> Season:
    display = f"{league_name} {season_code.replace('-', '/')}"
    r = await db.execute(select(Season).where(and_(Season.sport_id == sport_id, Season.name == display)))
    s = r.scalar_one_or_none()
    if s:
        return s
    try:
        y1, y2 = season_code.split("-")
        start_date, end_date = date(int(y1), 7, 1), date(int(y2), 6, 30)
    except Exception:
        yr = int(season_code) if season_code.isdigit() else datetime.utcnow().year
        start_date, end_date = date(yr, 1, 1), date(yr, 12, 31)
    s = Season(
        sport_id=sport_id, name=display, start_date=start_date, end_date=end_date,
        espn_sport=espn_sport, espn_league=espn_league,
    )
    db.add(s)
    await db.flush()
    return s


async def _ensure_team(
    db: AsyncSession,
    sport_id: int,
    cache: Dict[str, Team],
    name: str,
    espn_team: Optional[dict] = None,
) -> Team:
    key = name.strip()
    if key in cache:
        return cache[key]
    r = await db.execute(select(Team).where(and_(Team.sport_id == sport_id, Team.name == key)))
    team = r.scalar_one_or_none()
    if not team:
        team = Team(sport_id=sport_id, name=key, country="", city="", logo_url="")
        db.add(team)
        await db.flush()
    # Enrich metadata from ESPN payload if available
    if espn_team:
        team.logo_url = team.logo_url or _safe_str(espn_team.get("logo") or (espn_team.get("logos") or [{}])[0].get("href", ""))
        # Store ESPN team ID for news API calls
        espn_tid = _safe_str(espn_team.get("id"))
        if espn_tid and not team.espn_id:
            team.espn_id = espn_tid
        loc = espn_team.get("location") or ""
        if loc and not team.city:
            team.city = loc
    cache[key] = team
    return team


async def _ensure_player(
    db: AsyncSession,
    team_id: int,
    cache: Dict[Tuple[int, str], Player],
    name: str,
    position: Optional[str] = None,
    jersey: Optional[int] = None,
    photo_url: Optional[str] = None,
) -> Player:
    key = (team_id, name.strip())
    if key in cache:
        player = cache[key]
        # Update photo if we now have one and the player doesn't yet
        if photo_url and not player.photo_url:
            player.photo_url = photo_url
        return player
    r = await db.execute(select(Player).where(and_(Player.team_id == team_id, Player.name == name.strip())))
    player = r.scalar_one_or_none()
    if not player:
        player = Player(team_id=team_id, name=name.strip(), position=position, photo_url=photo_url)
        db.add(player)
        await db.flush()
    else:
        if position and not player.position:
            player.position = position
        if photo_url and not player.photo_url:
            player.photo_url = photo_url
    cache[key] = player
    return player


# ── Scoreboard fetching ─────────────────────────────────────────────────────

def _build_scoreboard_urls(cfg: LeagueConfig) -> List[str]:
    urls = []
    step = max(1, cfg.step_days)
    start = datetime.utcnow().date() - timedelta(days=cfg.days_back)
    end   = datetime.utcnow().date() + timedelta(days=cfg.days_ahead)
    day = start
    while day <= end:
        # ESPN accepts YYYYMMDD (single day) or YYYYMMDD-YYYYMMDD (range).
        # Use 7-day windows to reduce request count.
        week_end = min(day + timedelta(days=step - 1), end)
        date_param = f"{day.strftime('%Y%m%d')}-{week_end.strftime('%Y%m%d')}"
        urls.append(
            f"{ESPN_BASE}/{cfg.espn_sport}/{cfg.espn_league}/scoreboard"
            f"?dates={date_param}&limit=200"
        )
        day = week_end + timedelta(days=1)
    return urls


async def _fetch_scoreboard_events(cfg: LeagueConfig) -> List[dict]:
    """Return list of raw ESPN event dicts for this league (all date range)."""
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def fetch_one(url: str) -> List[dict]:
        async with sem:
            data = await _http_get_async(url)
        return data.get("events") or []

    urls = _build_scoreboard_urls(cfg)
    results = await asyncio.gather(*(fetch_one(u) for u in urls), return_exceptions=True)
    raw_events: List[dict] = []
    for batch in results:
        if isinstance(batch, Exception):
            continue
        raw_events.extend(batch)
    return _normalize_scoreboard_events(cfg.espn_sport, raw_events)


# ── Summary fetching (lineup + events + stats) ──────────────────────────────

async def _fetch_summary(cfg: LeagueConfig, event_id: str) -> dict:
    url = f"{ESPN_BASE}/{cfg.espn_sport}/{cfg.espn_league}/summary?event={event_id}"
    return await _http_get_async(url)


def _parse_team_stats_from_boxscore(boxscore_teams: List[dict]) -> Dict[str, dict]:
    """Return {espn_team_id: {stat_key: value}} from boxscore.teams."""
    result: Dict[str, dict] = {}
    for bt in boxscore_teams:
        team_id = _safe_str((bt.get("team") or {}).get("id"))
        if not team_id:
            continue
        stats: dict = {}
        for stat in (bt.get("statistics") or []):
            raw_name = _safe_str(stat.get("name"))
            raw_val  = _safe_str(stat.get("displayValue"))
            mapped = _STAT_NAME_MAP.get(raw_name, raw_name)
            val = _parse_stat_val(raw_val)
            if val is not None:
                stats[mapped] = val
        result[team_id] = stats
    return result


def _parse_lineups_from_boxscore(boxscore_players: List[dict]) -> Dict[str, List[dict]]:
    """Return {espn_team_id: [{name, position, jersey, starter, minutes}]}."""
    result: Dict[str, List[dict]] = {}
    for bp in boxscore_players:
        team_id = _safe_str((bp.get("team") or {}).get("id"))
        if not team_id:
            continue
        players_list: List[dict] = []
        for stat_group in (bp.get("statistics") or []):
            for ath in (stat_group.get("athletes") or []):
                athlete = ath.get("athlete") or {}
                name = _safe_str(athlete.get("displayName"))
                if not name:
                    continue
                pos = _safe_str((athlete.get("position") or {}).get("abbreviation"))
                jersey = _safe_int(athlete.get("jersey"))
                starter = bool(ath.get("starter"))

                # Try to find "minutes" in stats list; position varies by sport
                stats_arr = ath.get("stats") or []
                minutes = None
                if stats_arr:
                    # First element is often minutes in soccer
                    minutes = _safe_int(stats_arr[0])

                # Headshot photo from ESPN
                photo_url = _extract_athlete_photo_url(athlete)

                players_list.append({
                    "name": name,
                    "position": pos or None,
                    "jersey": jersey,
                    "starter": starter,
                    "minutes": minutes,
                    "photo_url": photo_url,
                })
        result[team_id] = players_list
    return result


def _parse_events_from_summary(summary: dict) -> List[dict]:
    """Extract goal/card/sub events from ESPN summary in a sport-agnostic way."""
    events: List[dict] = []

    # -- Try competition.details (works when ESPN type IDs are numeric)
    for comp in ((summary.get("header") or {}).get("competitions") or []):
        for detail in (comp.get("details") or []):
            ev_type_raw = _safe_str((detail.get("type") or {}).get("id"))
            ev_type_text = _safe_str((detail.get("type") or {}).get("text")).lower()
            clock_val = _safe_str((detail.get("clock") or {}).get("displayValue"))
            team_id = _safe_str((detail.get("team") or {}).get("id"))
            athletes = detail.get("athletesInvolved") or []
            player_name = _safe_str(athletes[0].get("displayName")) if athletes else ""

            ev_type = _EVENT_TYPE_MAP.get(ev_type_raw)
            if not ev_type:
                if "goal" in ev_type_text:
                    ev_type = "goal"
                elif "yellow" in ev_type_text and "red" not in ev_type_text:
                    ev_type = "yellow_card"
                elif "red" in ev_type_text:
                    ev_type = "red_card"
                elif "sub" in ev_type_text:
                    ev_type = "substitution"
                else:
                    continue  # skip non-mappable events

            # parse minute from clock "23'" or "23:45"
            minute = None
            if clock_val:
                raw_m = clock_val.replace("'", "").split(":")[0].strip()
                minute = _safe_int(raw_m)

            desc = _safe_str(detail.get("text")) or f"{ev_type.replace('_', ' ').title()}"
            if player_name:
                desc = f"{player_name} — {desc}" if desc and player_name not in desc else player_name

            events.append({
                "event_type": ev_type,
                "minute": minute,
                "detail": desc,
                "team_espn_id": team_id,
                "player_name": player_name,
            })

    # -- Soccer: parse keyEvents when details didn't yield player-linked events
    _KEY_EVENT_SKIP = frozenset({
        "Kickoff", "Halftime", "Start 2nd Half", "Start Extra Time",
        "End Regular Time", "End of Game", "Full Time", "Substitution",
    })
    _KEY_GOAL_TYPES = frozenset({
        "Goal", "Goal - Header", "Goal - Foot", "Goal - Volley",
        "Penalty - Scored", "Own Goal",
    })
    if not any(ev.get("player_name") for ev in events):
        for ke in (summary.get("keyEvents") or []):
            type_text = _safe_str((ke.get("type") or {}).get("text") or "")
            if type_text in _KEY_EVENT_SKIP:
                continue
            team_id = _safe_str((ke.get("team") or {}).get("id"))
            participants = ke.get("participants") or []
            player_name = ""
            if participants:
                ath = (participants[0].get("athlete") or {})
                player_name = _safe_str(ath.get("displayName"))
            clock_val = _safe_str((ke.get("clock") or {}).get("displayValue"))
            minute = None
            if clock_val:
                raw_m = clock_val.replace("'", "").split(":")[0].strip()
                minute = _safe_int(raw_m)
            if type_text in _KEY_GOAL_TYPES:
                ev_type = "goal"
            elif "Yellow Card" in type_text:
                ev_type = "yellow_card"
            elif "Red Card" in type_text or "Red card" in type_text:
                ev_type = "red_card"
            else:
                continue  # skip non-essential events
            desc = _safe_str(ke.get("text")) or type_text
            events.append({
                "event_type": ev_type,
                "minute": minute,
                "detail": desc,
                "team_espn_id": team_id,
                "player_name": player_name,
            })

    # -- Fallback: scoringPlays (some sports)
    if not events:
        for sp in (summary.get("scoringPlays") or []):
            minute = None
            clock_raw = _safe_str((sp.get("clock") or {}).get("displayValue"))
            if clock_raw:
                raw_m = clock_raw.replace("'", "").split(":")[0].strip()
                minute = _safe_int(raw_m)
            team_id = _safe_str((sp.get("team") or {}).get("id"))
            text = _safe_str(sp.get("text"))
            if text:
                events.append({
                    "event_type": "goal",
                    "minute": minute,
                    "detail": text,
                    "team_espn_id": team_id,
                    "player_name": "",
                })

    return events


def _parse_lineups_from_rosters(rosters: List[dict]) -> Dict[str, List[dict]]:
    """Return {espn_team_id: [{name, position, jersey, starter, minutes, photo_url}]} from soccer rosters."""
    result: Dict[str, List[dict]] = {}
    for roster_entry in rosters:
        team_id = _safe_str((roster_entry.get("team") or {}).get("id"))
        if not team_id:
            continue
        players_list: List[dict] = []
        for entry in (roster_entry.get("roster") or []):
            athlete = entry.get("athlete") or {}
            name = _safe_str(athlete.get("displayName"))
            if not name:
                continue
            pos_raw = entry.get("position") or athlete.get("position") or {}
            pos = _safe_str(pos_raw.get("abbreviation") or pos_raw.get("name"))
            jersey = _safe_int(entry.get("jersey")) or _safe_int(athlete.get("jersey"))
            starter = bool(entry.get("starter"))
            photo_url = _extract_athlete_photo_url(athlete)
            players_list.append({
                "name": name,
                "position": pos or None,
                "jersey": jersey,
                "starter": starter,
                "minutes": None,
                "photo_url": photo_url,
            })
        if players_list:
            result[team_id] = players_list
    return result


# ── Roster fetching ─────────────────────────────────────────────────────────

async def _fetch_and_store_roster(
    db: AsyncSession,
    cfg: LeagueConfig,
    espn_team_id: str,
    db_team: Team,
    player_cache: Dict[Tuple[int, str], Player],
) -> None:
    url = f"{ESPN_BASE}/{cfg.espn_sport}/{cfg.espn_league}/teams/{espn_team_id}/roster"
    data = await _http_get_async(url)
    athletes = data.get("athletes") or []
    if not athletes and "items" in data:
        athletes = data.get("items") or []

    # Handle grouped structure (basketball returns position groups)
    flat_athletes: List[dict] = []
    for item in athletes:
        if "items" in item:
            flat_athletes.extend(item["items"])
        elif "athlete" in item or "displayName" in item or "fullName" in item:
            flat_athletes.append(item)
        else:
            flat_athletes.append(item)

    for ath in flat_athletes:
        # ESPN roster items can have athlete nested or flat
        if "athlete" in ath:
            ath = ath["athlete"]
        name = _safe_str(ath.get("displayName") or ath.get("fullName"))
        if not name:
            continue
        pos = _safe_str((ath.get("position") or {}).get("abbreviation"))
        dob_raw = _safe_str(ath.get("dateOfBirth"))
        nationality = _safe_str((ath.get("citizenship") or ath.get("nationality") or ""))
        photo_url = _extract_athlete_photo_url(ath, espn_sport=cfg.espn_sport)
        if not photo_url:
            photo_url = await fetch_external_player_photo_url(
                player_name=name,
                team_name=db_team.name,
                sport_hint=cfg.espn_sport,
            )

        key = (db_team.id, name)
        if key not in player_cache:
            r = await db.execute(select(Player).where(and_(Player.team_id == db_team.id, Player.name == name)))
            player = r.scalar_one_or_none()
            if not player:
                player = Player(team_id=db_team.id, name=name, position=pos or None, photo_url=photo_url)
                try:
                    if dob_raw:
                        from datetime import date as _date
                        player.date_of_birth = datetime.strptime(dob_raw[:10], "%Y-%m-%d").date()
                except Exception:
                    pass
                if nationality:
                    player.nationality = nationality
                db.add(player)
                await db.flush()
            else:
                if pos and not player.position:
                    player.position = pos
                if nationality and not player.nationality:
                    player.nationality = nationality
                if photo_url and not player.photo_url:
                    player.photo_url = photo_url
            player_cache[key] = player


async def _backfill_missing_team_rosters(
    db: AsyncSession,
    cfg: LeagueConfig,
    teams: List[Team],
    player_cache: Dict[Tuple[int, str], Player],
) -> int:
    """Fetch rosters for teams with missing roster data or missing player photos."""
    if not cfg.fetch_rosters:
        return 0

    teams_backfilled = 0
    for team in teams:
        if not team.espn_id:
            continue

        needs_roster_repair = (
            await db.execute(
                select(Player.id)
                .where(
                    and_(
                        Player.team_id == team.id,
                        or_(Player.photo_url.is_(None), Player.photo_url == ""),
                    )
                )
                .limit(1)
            )
        ).scalar_one_or_none()

        has_players = (
            await db.execute(select(Player.id).where(Player.team_id == team.id).limit(1))
        ).scalar_one_or_none()
        if has_players is not None and needs_roster_repair is None:
            continue

        try:
            await _fetch_and_store_roster(db, cfg, team.espn_id, team, player_cache)
        except Exception as exc:
            logger.debug("Roster backfill failed for team %s (%s): %s", team.name, team.espn_id, exc)
            continue

        has_players_after = (
            await db.execute(select(Player.id).where(Player.team_id == team.id).limit(1))
        ).scalar_one_or_none()
        if has_players_after is not None:
            teams_backfilled += 1

    return teams_backfilled


# ── Main match upsert ────────────────────────────────────────────────────────

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
    external_id: Optional[str],
) -> Tuple[Match, bool]:
    """Return (match, is_new). Never downgrades a completed match."""
    # Try to find by external_id first (most reliable)
    match = None
    if external_id:
        r = await db.execute(select(Match).where(Match.external_id == external_id))
        match = r.scalar_one_or_none()

    # Fallback: match by teams + datetime
    if match is None:
        r = await db.execute(
            select(Match).where(
                and_(
                    Match.season_id == season_id,
                    Match.home_team_id == home_team_id,
                    Match.away_team_id == away_team_id,
                    Match.match_date == dt,
                )
            )
        )
        match = r.scalar_one_or_none()

    if match:
        # Never overwrite real data with empty data
        if match.status == MatchStatus.completed and status != MatchStatus.completed:
            return match, False
        match.status = status
        match.home_score = home_score
        match.away_score = away_score
        match.result = result
        match.venue = venue or match.venue
        if external_id:
            match.external_id = external_id
        return match, False

    match = Match(
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
        external_id=external_id,
        enriched=False,
    )
    db.add(match)
    await db.flush()
    return match, True


# ── Store enrichment data ────────────────────────────────────────────────────

async def _store_match_enrichment(
    db: AsyncSession,
    match: Match,
    cfg: LeagueConfig,
    home_team: Team,
    away_team: Team,
    home_espn_id: str,
    away_espn_id: str,
    player_cache: Dict[Tuple[int, str], Player],
    summary: dict,
) -> None:
    """Store lineups, events, team stats from ESPN summary into the DB."""
    boxscore = summary.get("boxscore") or {}
    bp = boxscore.get("players") or []
    bt = boxscore.get("teams") or []

    # ── Team stats ──────────────────────────────────────────
    team_stats_map = _parse_team_stats_from_boxscore(bt)

    # Delete old stat lines for this match (re-import)
    await db.execute(delete(MatchStatLine).where(MatchStatLine.match_id == match.id))

    for espn_id, db_team, is_home in (
        (home_espn_id, home_team, True),
        (away_espn_id, away_team, False),
    ):
        stats = team_stats_map.get(espn_id, {})
        if stats:
            db.add(MatchStatLine(match_id=match.id, is_home=is_home, stats=stats))

    # ── Lineups ─────────────────────────────────────────────
    lineup_map = _parse_lineups_from_boxscore(bp)
    # Soccer stores lineups in top-level 'rosters', not boxscore.players
    if not lineup_map:
        rosters = summary.get("rosters") or []
        if rosters:
            lineup_map = _parse_lineups_from_rosters(rosters)

    await db.execute(delete(MatchLineup).where(MatchLineup.match_id == match.id))

    for espn_id, db_team, is_home in (
        (home_espn_id, home_team, True),
        (away_espn_id, away_team, False),
    ):
        players_data = lineup_map.get(espn_id, [])
        for pd in players_data:
            player = await _ensure_player(
                db, db_team.id, player_cache,
                pd["name"], pd.get("position"), pd.get("jersey"), pd.get("photo_url")
            )
            db.add(MatchLineup(
                match_id=match.id,
                team_id=db_team.id,
                player_id=player.id,
                is_starter=pd.get("starter", True),
                position=pd.get("position"),
                jersey_number=pd.get("jersey"),
                minutes_played=pd.get("minutes"),
            ))

    # ── Match Events ────────────────────────────────────────
    raw_events = _parse_events_from_summary(summary)

    await db.execute(delete(MatchEvent).where(MatchEvent.match_id == match.id))

    # Build espn_id → DB team mapping for event team lookup
    espn_to_db: Dict[str, Team] = {home_espn_id: home_team, away_espn_id: away_team}

    for ev in raw_events:
        team_espn = ev.get("team_espn_id", "")
        db_team_for_ev = espn_to_db.get(team_espn)
        player_for_ev = None
        pname = ev.get("player_name", "")
        if pname and db_team_for_ev:
            player_for_ev = await _ensure_player(db, db_team_for_ev.id, player_cache, pname)
        db.add(MatchEvent(
            match_id=match.id,
            team_id=db_team_for_ev.id if db_team_for_ev else None,
            player_id=player_for_ev.id if player_for_ev else None,
            event_type=ev.get("event_type", "event"),
            minute=ev.get("minute"),
            detail=ev.get("detail"),
        ))

    match.enriched = True


# ── Process one ESPN event ───────────────────────────────────────────────────

async def _process_event(
    db: AsyncSession,
    cfg: LeagueConfig,
    ev: dict,
    sport: Sport,
    team_cache: Dict[str, Team],
    player_cache: Dict[Tuple[int, str], Player],
    fetch_details: bool = True,
    fetched_roster_team_ids: Optional[Set[int]] = None,
) -> bool:
    """Parse one ESPN scoreboard event, upsert match, optionally fetch summary."""
    competition_list = ev.get("competitions") or []
    if not competition_list:
        return False
    comp = competition_list[0]

    dt_raw = comp.get("date") or ev.get("date") or ""
    dt = _parse_espn_dt(dt_raw)
    if not dt:
        return False

    competitors = comp.get("competitors") or []
    if len(competitors) < 2:
        return False

    home_comp = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
    away_comp = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

    home_espn = home_comp.get("team") or {}
    away_espn = away_comp.get("team") or {}
    home_name = _safe_str(home_espn.get("displayName") or home_espn.get("name"))
    away_name = _safe_str(away_espn.get("displayName") or away_espn.get("name"))
    if not home_name or not away_name:
        return False

    home_espn_id = _safe_str(home_espn.get("id"))
    away_espn_id = _safe_str(away_espn.get("id"))

    home_team = await _ensure_team(db, sport.id, team_cache, home_name, home_espn)
    away_team = await _ensure_team(db, sport.id, team_cache, away_name, away_espn)

    if cfg.fetch_rosters:
        if fetched_roster_team_ids is None:
            fetched_roster_team_ids = set()
        for team_espn_id, db_team in ((home_espn_id, home_team), (away_espn_id, away_team)):
            if not team_espn_id or db_team.id in fetched_roster_team_ids:
                continue
            try:
                await _fetch_and_store_roster(db, cfg, team_espn_id, db_team, player_cache)
                fetched_roster_team_ids.add(db_team.id)
            except Exception as exc:
                logger.debug("Roster fetch failed for team %s: %s", team_espn_id, exc)

    venue = _safe_str((comp.get("venue") or {}).get("fullName"))
    external_id = _safe_str(ev.get("id"))

    # Status + scores
    status_info = (comp.get("status") or {}).get("type") or {}
    completed = bool(status_info.get("completed"))
    state = _safe_str(status_info.get("state"))
    home_score_raw = home_comp.get("score")
    away_score_raw = away_comp.get("score")
    home_score = _safe_int(home_score_raw) if home_score_raw not in (None, "") else None
    away_score = _safe_int(away_score_raw) if away_score_raw not in (None, "") else None

    if completed and home_score is not None and away_score is not None:
        status = MatchStatus.completed
        if home_score > away_score:
            result = MatchResult.home_win
        elif away_score > home_score:
            result = MatchResult.away_win
        else:
            result = MatchResult.draw
    elif state == "in":
        status = MatchStatus.in_progress
        result = None
    else:
        status = MatchStatus.scheduled
        result = None
        home_score = None
        away_score = None

    season_code = _season_code(dt)
    season = await _ensure_season(
        db, sport.id, cfg.league_name, season_code,
        espn_sport=cfg.espn_sport, espn_league=cfg.espn_league,
    )

    match, is_new = await _upsert_match(
        db, sport.id, season.id,
        home_team.id, away_team.id,
        dt, venue, status, home_score, away_score, result, external_id or None,
    )

    # Fetch rich summary for completed or upcoming-within-14-days matches
    should_enrich = (
        fetch_details
        and external_id
        and (
            status == MatchStatus.completed
            or (dt.date() <= datetime.utcnow().date() + timedelta(days=14))
        )
        and not match.enriched
    )

    if should_enrich:
        try:
            summary = await _fetch_summary(cfg, external_id)
            if summary:
                await _store_match_enrichment(
                    db, match, cfg,
                    home_team, away_team,
                    home_espn_id, away_espn_id,
                    player_cache, summary,
                )
        except Exception as exc:
            logger.debug("Enrichment failed for %s: %s", external_id, exc)

    return is_new


# ── Stats rebuild ─────────────────────────────────────────────────────────────

async def _rebuild_stats_and_h2h(db: AsyncSession, sport_ids: Optional[List[int]] = None) -> None:
    """Recompute TeamStatistics and HeadToHead from completed matches."""
    # Scope deletes
    if sport_ids:
        sport_team_q = select(Team.id).where(Team.sport_id.in_(sport_ids))
        await db.execute(delete(TeamStatistics).where(TeamStatistics.team_id.in_(sport_team_q)))
        await db.execute(
            delete(HeadToHead).where(
                HeadToHead.team1_id.in_(sport_team_q) | HeadToHead.team2_id.in_(sport_team_q)
            )
        )
        season_q = await db.execute(select(Season).where(Season.sport_id.in_(sport_ids)))
        seasons = season_q.scalars().all()
        team_q = await db.execute(select(Team).where(Team.sport_id.in_(sport_ids)))
        teams = team_q.scalars().all()
    else:
        await db.execute(delete(TeamStatistics))
        await db.execute(delete(HeadToHead))
        seasons = (await db.execute(select(Season))).scalars().all()
        teams = (await db.execute(select(Team))).scalars().all()

    team_map: Dict[int, Team] = {t.id: t for t in teams}

    for season in seasons:
        sport_teams = [t for t in teams if t.sport_id == season.sport_id]
        for team in sport_teams:
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
                hg, ag = m.home_score or 0, m.away_score or 0
                gf += hg if is_home else ag
                ga += ag if is_home else hg
                if m.result == MatchResult.draw:
                    d += 1; form.append("D")
                elif (m.result == MatchResult.home_win and is_home) or (m.result == MatchResult.away_win and not is_home):
                    w += 1; form.append("W")
                else:
                    l += 1; form.append("L")

            existing = (await db.execute(
                select(TeamStatistics).where(and_(TeamStatistics.team_id == team.id, TeamStatistics.season_id == season.id))
            )).scalar_one_or_none()
            if existing is None:
                existing = TeamStatistics(team_id=team.id, season_id=season.id)
                db.add(existing)
            existing.matches_played = len(mlist)
            existing.wins, existing.draws, existing.losses = w, d, l
            existing.goals_for, existing.goals_against = gf, ga
            existing.points = w * 3 + d
            existing.form_last5 = form[-5:]

    # H2H
    unique_sports = set(t.sport_id for t in teams)
    for sport_id in unique_sports:
        sport_teams = [t for t in teams if t.sport_id == sport_id]
        for i in range(len(sport_teams)):
            for j in range(i + 1, len(sport_teams)):
                t1, t2 = sport_teams[i], sport_teams[j]
                q = await db.execute(
                    select(Match).where(
                        and_(
                            Match.status == MatchStatus.completed,
                            ((Match.home_team_id == t1.id) & (Match.away_team_id == t2.id))
                            | ((Match.home_team_id == t2.id) & (Match.away_team_id == t1.id)),
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
                        (t1w if m.home_team_id == t1.id else t2w).__add__(1)  # see below
                        if m.home_team_id == t1.id: t1w += 1
                        else: t2w += 1
                    else:
                        if m.away_team_id == t1.id: t1w += 1
                        else: t2w += 1

                existing_h2h = (await db.execute(
                    select(HeadToHead).where(and_(HeadToHead.team1_id == t1.id, HeadToHead.team2_id == t2.id))
                )).scalar_one_or_none()
                if existing_h2h is None:
                    existing_h2h = HeadToHead(team1_id=t1.id, team2_id=t2.id)
                    db.add(existing_h2h)
                existing_h2h.total_matches = len(mlist)
                existing_h2h.team1_wins = t1w
                existing_h2h.team2_wins = t2w
                existing_h2h.draws = dr


# ── Public import API ────────────────────────────────────────────────────────

async def import_all_sports(db: AsyncSession, reset_existing: bool = False) -> dict:
    """
    Full import: fetch all configured leagues, store matches + enrichment, rebuild stats.
    This is the startup import (runs once when DB is empty).
    """
    if reset_existing:
        for tbl in (Prediction, MatchEvent, MatchLineup, MatchStatLine,
                    HeadToHead, TeamStatistics, Player, Match, Season, Team, Sport):
            await db.execute(delete(tbl))

    await _ensure_users(db)

    total_new = 0
    sport_ids_imported: List[int] = []

    for cfg in LEAGUES:
        sport = await _ensure_sport(db, cfg)
        if sport.id not in sport_ids_imported:
            sport_ids_imported.append(sport.id)

        team_cache: Dict[str, Team] = {}
        player_cache: Dict[Tuple[int, str], Player] = {}
        fetched_roster_team_ids: Set[int] = set()

        logger.info("[MegaScraper] Fetching %s %s …", cfg.sport_name, cfg.league_name)
        try:
            events = await _fetch_scoreboard_events(cfg)
        except Exception as exc:
            logger.warning("[MegaScraper] Scoreboard failed for %s: %s", cfg.league_name, exc)
            continue

        # Fetch rosters once per team (deduplicated by team cache)
        # We do it during event processing when we first see each team.

        new_count = 0
        for ev in events:
            try:
                is_new = await _process_event(
                    db,
                    cfg,
                    ev,
                    sport,
                    team_cache,
                    player_cache,
                    fetch_details=True,
                    fetched_roster_team_ids=fetched_roster_team_ids,
                )
                if is_new:
                    new_count += 1
                # Flush periodically to avoid huge transactions
                if new_count % 50 == 0 and new_count > 0:
                    await db.flush()
            except Exception as exc:
                logger.debug("[MegaScraper] Event error: %s", exc)

        rosters_backfilled = await _backfill_missing_team_rosters(
            db,
            cfg,
            list(team_cache.values()),
            player_cache,
        )

        total_new += new_count
        logger.info(
            "[MegaScraper] %s %s: %d new matches, %d roster backfills",
            cfg.sport_name,
            cfg.league_name,
            new_count,
            rosters_backfilled,
        )

    # Commit matches before stats rebuild
    await db.commit()

    try:
        await _rebuild_stats_and_h2h(db, sport_ids=sport_ids_imported)
        await db.commit()
    except Exception as exc:
        logger.error("[MegaScraper] Stats rebuild failed: %s", exc)
        await db.rollback()

    all_matches = (await db.execute(select(Match))).scalars().all()
    return {
        "sports": len((await db.execute(select(Sport))).scalars().all()),
        "teams": len((await db.execute(select(Team))).scalars().all()),
        "players": len((await db.execute(select(Player))).scalars().all()),
        "matches": len(all_matches),
        "completed_matches": sum(1 for m in all_matches if m.status == MatchStatus.completed),
        "scheduled_matches": sum(1 for m in all_matches if m.status == MatchStatus.scheduled),
        "new_matches_added": total_new,
    }


async def refresh_recent_data(db: AsyncSession) -> dict:
    """
    Lightweight refresh: only fetch last 14 days + next 7 days.
    Used by the background loop every ~10 minutes.
    """
    total_new = 0
    sport_ids: List[int] = []

    for cfg in LEAGUES:
        # Narrow window for refresh
        mini_cfg = LeagueConfig(
            espn_sport=cfg.espn_sport,
            espn_league=cfg.espn_league,
            sport_name=cfg.sport_name,
            league_name=cfg.league_name,
            icon=cfg.icon,
            days_back=14,
            days_ahead=7,
            step_days=7,
            fetch_rosters=False,
            allows_draw=cfg.allows_draw,
        )

        sport = await _ensure_sport(db, cfg)
        if sport.id not in sport_ids:
            sport_ids.append(sport.id)

        team_cache: Dict[str, Team] = {}
        player_cache: Dict[Tuple[int, str], Player] = {}
        fetched_roster_team_ids: Set[int] = set()

        try:
            events = await _fetch_scoreboard_events(mini_cfg)
        except Exception as exc:
            logger.debug("[MegaScraper-Refresh] %s failed: %s", cfg.league_name, exc)
            continue

        for ev in events:
            try:
                is_new = await _process_event(
                    db,
                    mini_cfg,
                    ev,
                    sport,
                    team_cache,
                    player_cache,
                    fetch_details=True,
                    fetched_roster_team_ids=fetched_roster_team_ids,
                )
                if is_new:
                    total_new += 1
            except Exception as exc:
                logger.debug("[MegaScraper-Refresh] Event error: %s", exc)

        await _backfill_missing_team_rosters(
            db,
            cfg,
            list(team_cache.values()),
            player_cache,
        )

    await db.commit()

    if sport_ids:
        try:
            await _rebuild_stats_and_h2h(db, sport_ids=sport_ids)
            await db.commit()
        except Exception as exc:
            logger.debug("[MegaScraper-Refresh] Stats rebuild error: %s", exc)
            await db.rollback()

    return {"new_matches_added": total_new, "sports_refreshed": len(sport_ids)}


async def enrich_pending_matches(db: AsyncSession, limit: int = 20) -> int:
    """
    Fetch summaries for recently completed matches that haven't been enriched yet.
    Called from background loop.
    """
    cutoff = datetime.utcnow() - timedelta(days=30)
    r = await db.execute(
        select(Match)
        .where(
            and_(
                Match.enriched == False,
                Match.external_id.isnot(None),
                Match.match_date >= cutoff,
            )
        )
        .limit(limit)
    )
    matches = r.scalars().all()

    if not matches:
        return 0

    # Build a sport→league cfg map
    sport_ids = list({m.sport_id for m in matches})
    sports = (await db.execute(select(Sport).where(Sport.id.in_(sport_ids)))).scalars().all()
    sport_name_map = {s.id: s.name for s in sports}

    # Map sport_name → LeagueConfig (pick first matching)
    cfg_map: Dict[int, LeagueConfig] = {}
    for m in matches:
        if m.sport_id in cfg_map:
            continue
        sname = sport_name_map.get(m.sport_id, "")
        for cfg in LEAGUES:
            if cfg.sport_name == sname:
                cfg_map[m.sport_id] = cfg
                break

    enriched = 0
    player_cache: Dict[Tuple[int, str], Player] = {}

    for match in matches:
        cfg = cfg_map.get(match.sport_id)
        if not cfg:
            continue
        try:
            summary = await _fetch_summary(cfg, match.external_id)
            if not summary:
                continue

            home_team = (await db.execute(select(Team).where(Team.id == match.home_team_id))).scalar_one_or_none()
            away_team = (await db.execute(select(Team).where(Team.id == match.away_team_id))).scalar_one_or_none()
            if not home_team or not away_team:
                continue

            # Try to get ESPN IDs from match competitors in summary
            header_comps = ((summary.get("header") or {}).get("competitions") or [{}])[0]
            competitors = header_comps.get("competitors") or []
            home_espn_id = away_espn_id = ""
            for comp in competitors:
                cname = _safe_str((comp.get("team") or {}).get("displayName"))
                cid   = _safe_str((comp.get("team") or {}).get("id"))
                if cname == home_team.name:
                    home_espn_id = cid
                elif cname == away_team.name:
                    away_espn_id = cid

            await _store_match_enrichment(
                db, match, cfg,
                home_team, away_team,
                home_espn_id, away_espn_id,
                player_cache, summary,
            )
            enriched += 1
        except Exception as exc:
            logger.debug("[MegaScraper-Enrich] Match %d failed: %s", match.id, exc)

    if enriched:
        await db.commit()

    return enriched
