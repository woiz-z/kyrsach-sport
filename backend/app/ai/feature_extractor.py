"""Feature extraction from database for ML model training and prediction."""
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
from app.models.models import Match, TeamStatistics, HeadToHead, MatchStatus, MatchResult
from app.ai.sport_profiles import get_sport_profile


FEATURE_NAMES = [
    "home_points", "away_points", "points_diff",
    "home_wins", "away_wins",
    "home_goals_for", "home_goals_against",
    "away_goals_for", "away_goals_against",
    "home_goal_diff", "away_goal_diff",
    "home_matches_played", "away_matches_played",
    "home_ppg", "away_ppg",
    "h2h_home_wins", "h2h_away_wins", "h2h_draws", "h2h_total",
    "home_form_points", "away_form_points",
    "home_home_win_rate", "away_away_win_rate",
]


async def extract_features_for_match(db: AsyncSession, match_id: int) -> dict:
    """Extract all relevant features for a match prediction."""
    result = await db.execute(select(Match).options(selectinload(Match.sport)).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        return {}

    sport_profile = get_sport_profile(match.sport.name if match.sport else None)

    home_id = match.home_team_id
    away_id = match.away_team_id
    season_id = match.season_id

    # Team statistics
    home_stats = await get_team_stats(db, home_id, season_id)
    away_stats = await get_team_stats(db, away_id, season_id)

    # Head to head
    h2h = await get_h2h(db, home_id, away_id)

    # Recent form (last 5 matches)
    home_form = await _get_recent_form(db, home_id, match.match_date, allows_draw=sport_profile.allows_draw)
    away_form = await _get_recent_form(db, away_id, match.match_date, allows_draw=sport_profile.allows_draw)

    # Home advantage stats
    home_home_wr = await _get_home_win_rate(db, home_id, season_id)
    away_away_wr = await _get_away_win_rate(db, away_id, season_id)

    features = {
        "home_points": home_stats.get("points", 0),
        "away_points": away_stats.get("points", 0),
        "points_diff": home_stats.get("points", 0) - away_stats.get("points", 0),
        "home_wins": home_stats.get("wins", 0),
        "away_wins": away_stats.get("wins", 0),
        "home_goals_for": home_stats.get("goals_for", 0),
        "home_goals_against": home_stats.get("goals_against", 0),
        "away_goals_for": away_stats.get("goals_for", 0),
        "away_goals_against": away_stats.get("goals_against", 0),
        "home_goal_diff": home_stats.get("goals_for", 0) - home_stats.get("goals_against", 0),
        "away_goal_diff": away_stats.get("goals_for", 0) - away_stats.get("goals_against", 0),
        "home_matches_played": home_stats.get("matches_played", 1),
        "away_matches_played": away_stats.get("matches_played", 1),
        "home_ppg": home_stats.get("points", 0) / max(home_stats.get("matches_played", 1), 1),
        "away_ppg": away_stats.get("points", 0) / max(away_stats.get("matches_played", 1), 1),
        "h2h_home_wins": h2h.get("team1_wins", 0),
        "h2h_away_wins": h2h.get("team2_wins", 0),
        "h2h_draws": h2h.get("draws", 0) if sport_profile.allows_draw else 0,
        "h2h_total": h2h.get("total_matches", 0),
        "home_form_points": home_form,
        "away_form_points": away_form,
        "home_home_win_rate": home_home_wr,
        "away_away_win_rate": away_away_wr,
    }
    return features


def features_to_array(features: dict) -> np.ndarray:
    """Convert features dict to numpy array for model input."""
    return np.array([[features.get(name, 0.0) for name in FEATURE_NAMES]], dtype=float)


def get_feature_names() -> list:
    """Return sorted feature names for consistent ordering."""
    return FEATURE_NAMES[:]


def get_feature_groups() -> dict:
    """Return semantically grouped features for ablation testing."""
    groups = {
        "team_strength": [
            "home_points", "away_points", "points_diff",
            "home_wins", "away_wins",
            "home_ppg", "away_ppg",
        ],
        "goals_profile": [
            "home_goals_for", "home_goals_against",
            "away_goals_for", "away_goals_against",
            "home_goal_diff", "away_goal_diff",
        ],
        "sample_size": [
            "home_matches_played", "away_matches_played",
        ],
        "head_to_head": [
            "h2h_home_wins", "h2h_away_wins", "h2h_draws", "h2h_total",
        ],
        "recent_form": [
            "home_form_points", "away_form_points",
        ],
        "venue_effect": [
            "home_home_win_rate", "away_away_win_rate",
        ],
    }

    # Keep feature ordering deterministic and aligned with get_feature_names.
    feature_set = set(get_feature_names())
    return {k: [f for f in v if f in feature_set] for k, v in groups.items()}


async def extract_training_dataset(db: AsyncSession, season_id: int):
    """Extract features/labels plus match metadata for reproducible experiments."""
    result = await db.execute(
        select(Match).where(
            and_(Match.season_id == season_id, Match.status == MatchStatus.completed)
        ).order_by(Match.match_date)
    )
    matches = result.scalars().all()

    X, y, meta = [], [], []
    label_map = {"home_win": 0, "draw": 1, "away_win": 2}

    for match in matches:
        feats = await extract_features_for_match(db, match.id)
        if feats and match.result:
            arr = features_to_array(feats)[0]
            X.append(arr)
            y.append(label_map[match.result.value])
            meta.append({
                "match_id": match.id,
                "match_date": match.match_date.isoformat() if match.match_date else None,
                "result": match.result.value,
                "season_id": match.season_id,
            })

    return (
        np.array(X) if X else np.empty((0, 23)),
        np.array(y) if y else np.empty(0),
        meta,
    )


async def get_team_stats(db: AsyncSession, team_id: int, season_id: int) -> dict:
    result = await db.execute(
        select(TeamStatistics).where(
            and_(TeamStatistics.team_id == team_id, TeamStatistics.season_id == season_id)
        )
    )
    stats = result.scalar_one_or_none()
    if not stats:
        return {"points": 0, "wins": 0, "draws": 0, "losses": 0,
                "goals_for": 0, "goals_against": 0, "matches_played": 0}
    return {
        "points": stats.points, "wins": stats.wins, "draws": stats.draws,
        "losses": stats.losses, "goals_for": stats.goals_for,
        "goals_against": stats.goals_against, "matches_played": stats.matches_played,
    }


async def get_h2h(db: AsyncSession, team1_id: int, team2_id: int) -> dict:
    result = await db.execute(
        select(HeadToHead).where(
            or_(
                and_(HeadToHead.team1_id == team1_id, HeadToHead.team2_id == team2_id),
                and_(HeadToHead.team1_id == team2_id, HeadToHead.team2_id == team1_id),
            )
        )
    )
    h2h = result.scalar_one_or_none()
    if not h2h:
        return {"team1_wins": 0, "team2_wins": 0, "draws": 0, "total_matches": 0}
    if h2h.team1_id == team1_id:
        return {"team1_wins": h2h.team1_wins, "team2_wins": h2h.team2_wins,
                "draws": h2h.draws, "total_matches": h2h.total_matches}
    return {"team1_wins": h2h.team2_wins, "team2_wins": h2h.team1_wins,
            "draws": h2h.draws, "total_matches": h2h.total_matches}


async def _get_recent_form(db: AsyncSession, team_id: int, before_date, allows_draw: bool = True) -> float:
    """Points from last 5 matches (W=3, D=1, L=0) → returns average ppg."""
    result = await db.execute(
        select(Match).where(
            and_(
                or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
                Match.status == MatchStatus.completed,
                Match.match_date < before_date,
            )
        ).order_by(Match.match_date.desc()).limit(5)
    )
    matches = result.scalars().all()
    if not matches:
        return 1.0

    total = 0
    for m in matches:
        if m.result is None:
            continue
        is_home = m.home_team_id == team_id
        if allows_draw and m.result.value == "draw":
            total += 1
        elif (m.result.value == "home_win" and is_home) or (m.result.value == "away_win" and not is_home):
            total += 3
    return total / len(matches)


async def _get_home_win_rate(db: AsyncSession, team_id: int, season_id: int) -> float:
    home_matches = await db.execute(
        select(func.count()).select_from(Match).where(
            and_(Match.home_team_id == team_id, Match.season_id == season_id, Match.status == MatchStatus.completed)
        )
    )
    total = home_matches.scalar() or 0
    if total == 0:
        return 0.5
    home_wins = await db.execute(
        select(func.count()).select_from(Match).where(
            and_(Match.home_team_id == team_id, Match.season_id == season_id,
                 Match.result == MatchResult.home_win)
        )
    )
    wins = home_wins.scalar() or 0
    return wins / total


async def _get_away_win_rate(db: AsyncSession, team_id: int, season_id: int) -> float:
    away_matches = await db.execute(
        select(func.count()).select_from(Match).where(
            and_(Match.away_team_id == team_id, Match.season_id == season_id, Match.status == MatchStatus.completed)
        )
    )
    total = away_matches.scalar() or 0
    if total == 0:
        return 0.3
    away_wins = await db.execute(
        select(func.count()).select_from(Match).where(
            and_(Match.away_team_id == team_id, Match.season_id == season_id,
                 Match.result == MatchResult.away_win)
        )
    )
    wins = away_wins.scalar() or 0
    return wins / total
