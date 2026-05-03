from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.models import (
    Prediction, Match, MatchStatus, MatchResult,
    TeamStatistics, HeadToHead, User, Team,
    MatchLineup, MatchEvent,
)
from app.schemas.schemas import PredictionRequest, PredictionResponse, PredictionDetailResponse
from app.services.auth import get_current_user
from app.ai.llm_analyzer import generate_match_analysis
from app.ai.sport_profiles import get_sport_profile

router = APIRouter(prefix="/api/predictions", tags=["Predictions"])


async def _get_team_stats(db: AsyncSession, team_id: int, season_id: int) -> dict:
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


async def _get_h2h(db: AsyncSession, team1_id: int, team2_id: int) -> dict:
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


def _calculate_probabilities(home_stats: dict, away_stats: dict, allows_draw: bool) -> dict:
    """Stats-based probability estimation with home advantage."""
    home_mp = home_stats.get("matches_played") or 0
    away_mp = away_stats.get("matches_played") or 0

    home_ppg = (home_stats.get("points") or 0) / max(home_mp, 1)
    away_ppg = (away_stats.get("points") or 0) / max(away_mp, 1)

    # Home advantage factor
    home_strength = max(home_ppg * 1.15, 0.05)
    away_strength = max(away_ppg, 0.05)

    if allows_draw:
        draw_weight = 0.25
        total = home_strength + away_strength + draw_weight
        home_prob = home_strength / total
        away_prob = away_strength / total
        draw_prob = draw_weight / total
    else:
        total = home_strength + away_strength
        home_prob = home_strength / total
        away_prob = away_strength / total
        draw_prob = 0.0

    if home_prob >= away_prob and home_prob >= draw_prob:
        result = "home_win"
        confidence = home_prob
    elif away_prob >= home_prob and away_prob >= draw_prob:
        result = "away_win"
        confidence = away_prob
    else:
        result = "draw"
        confidence = draw_prob

    return {
        "predicted_result": result,
        "home_win_prob": round(home_prob, 4),
        "draw_prob": round(draw_prob, 4),
        "away_win_prob": round(away_prob, 4),
        "confidence": round(confidence, 4),
        "model_name": "SportPredict Analytics",
    }


@router.post("/predict", response_model=PredictionResponse)
async def create_prediction(
    req: PredictionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get match
    result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team), selectinload(Match.sport))
        .where(Match.id == req.match_id)
    )
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не знайдено")

    sport_profile = get_sport_profile(match.sport.name if match.sport else None)

    # Get team stats and H2H
    home_stats = await _get_team_stats(db, match.home_team_id, match.season_id)
    away_stats = await _get_team_stats(db, match.away_team_id, match.season_id)
    h2h = await _get_h2h(db, match.home_team_id, match.away_team_id)

    # Stats-based probability calculation
    pred = _calculate_probabilities(home_stats, away_stats, sport_profile.allows_draw)

    # Load lineups for richer analysis
    lineup_q = await db.execute(
        select(MatchLineup)
        .options(selectinload(MatchLineup.player))
        .where(MatchLineup.match_id == req.match_id)
    )
    lineups_db = lineup_q.scalars().all()
    lineups = None
    if lineups_db:
        lineups = {
            "home": [
                {"player_name": ln.player.name if ln.player else "", "is_starter": ln.is_starter, "position": ln.position}
                for ln in lineups_db if ln.team_id == match.home_team_id
            ],
            "away": [
                {"player_name": ln.player.name if ln.player else "", "is_starter": ln.is_starter, "position": ln.position}
                for ln in lineups_db if ln.team_id == match.away_team_id
            ],
        }

    # Load events
    events_q = await db.execute(
        select(MatchEvent)
        .where(MatchEvent.match_id == req.match_id)
        .order_by(MatchEvent.minute)
    )
    events_db = events_q.scalars().all()
    match_events = [
        {"event_type": e.event_type, "minute": e.minute, "detail": e.detail}
        for e in events_db
    ] if events_db else None

    # LLM analysis
    ai_analysis = await generate_match_analysis(
        home_team=match.home_team.name,
        away_team=match.away_team.name,
        prediction=pred,
        home_stats=home_stats,
        away_stats=away_stats,
        h2h=h2h,
        sport_name=match.sport.name if match.sport else None,
        lineups=lineups,
        match_events=match_events,
    )

    # Save prediction
    prediction = Prediction(
        match_id=req.match_id,
        user_id=current_user.id,
        predicted_result=pred["predicted_result"],
        home_win_prob=pred["home_win_prob"],
        draw_prob=pred["draw_prob"],
        away_win_prob=pred["away_win_prob"],
        is_correct=(pred["predicted_result"] == match.result) if (match.status == MatchStatus.completed and match.result is not None) else None,
        confidence=pred["confidence"],
        model_name=pred["model_name"],
        ai_analysis=ai_analysis,
    )
    db.add(prediction)
    await db.flush()
    await db.refresh(prediction)
    prediction.sport_name = match.sport.name if match.sport else None
    prediction.sport_icon = sport_profile.icon
    prediction.outcome_labels = {
        "home_win": sport_profile.home_label,
        "away_win": sport_profile.away_label,
        "draw": "Нічия",
    }
    return prediction


@router.get("/my", response_model=List[PredictionDetailResponse])
async def my_predictions(
    sport_id: int | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Prediction)
        .options(
            selectinload(Prediction.match).selectinload(Match.home_team),
            selectinload(Prediction.match).selectinload(Match.away_team),
            selectinload(Prediction.match).selectinload(Match.sport),
            selectinload(Prediction.match).selectinload(Match.season),
        )
        .where(Prediction.user_id == current_user.id)
    )
    if sport_id:
        query = query.where(Prediction.match.has(Match.sport_id == sport_id))

    result = await db.execute(
        query.order_by(Prediction.created_at.desc()).offset(offset).limit(limit)
    )
    items = result.scalars().all()
    for pred in items:
        profile = get_sport_profile(pred.match.sport.name if pred.match and pred.match.sport else None)
        pred.sport_name = pred.match.sport.name if pred.match and pred.match.sport else None
        pred.sport_icon = profile.icon
        pred.outcome_labels = {
            "home_win": profile.home_label,
            "away_win": profile.away_label,
            "draw": "Нічия",
        }
    return items


@router.get("/", response_model=List[PredictionDetailResponse])
async def all_predictions(
    sport_id: int | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Prediction)
        .options(
            selectinload(Prediction.match).selectinload(Match.home_team),
            selectinload(Prediction.match).selectinload(Match.away_team),
            selectinload(Prediction.match).selectinload(Match.sport),
            selectinload(Prediction.match).selectinload(Match.season),
        )
    )
    if sport_id:
        query = query.where(Prediction.match.has(Match.sport_id == sport_id))

    result = await db.execute(
        query.order_by(Prediction.created_at.desc()).offset(offset).limit(limit)
    )
    items = result.scalars().all()
    for pred in items:
        profile = get_sport_profile(pred.match.sport.name if pred.match and pred.match.sport else None)
        pred.sport_name = pred.match.sport.name if pred.match and pred.match.sport else None
        pred.sport_icon = profile.icon
        pred.outcome_labels = {
            "home_win": profile.home_label,
            "away_win": profile.away_label,
            "draw": "Нічия",
        }
    return items


@router.get("/{prediction_id}", response_model=PredictionDetailResponse)
async def get_prediction(prediction_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Prediction)
        .options(
            selectinload(Prediction.match).selectinload(Match.home_team),
            selectinload(Prediction.match).selectinload(Match.away_team),
            selectinload(Prediction.match).selectinload(Match.sport),
            selectinload(Prediction.match).selectinload(Match.season),
        )
        .where(Prediction.id == prediction_id)
    )
    pred = result.scalar_one_or_none()
    if not pred:
        raise HTTPException(status_code=404, detail="Прогноз не знайдено")
    profile = get_sport_profile(pred.match.sport.name if pred.match and pred.match.sport else None)
    pred.sport_name = pred.match.sport.name if pred.match and pred.match.sport else None
    pred.sport_icon = profile.icon
    pred.outcome_labels = {
        "home_win": profile.home_label,
        "away_win": profile.away_label,
        "draw": "Нічия",
    }
    return pred


@router.get("/match/{match_id}", response_model=List[PredictionResponse])
async def get_match_predictions(match_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Prediction)
        .options(selectinload(Prediction.match).selectinload(Match.sport))
        .where(Prediction.match_id == match_id)
        .order_by(Prediction.created_at.desc())
    )
    items = result.scalars().all()
    for pred in items:
        profile = get_sport_profile(pred.match.sport.name if pred.match and pred.match.sport else None)
        pred.sport_name = pred.match.sport.name if pred.match and pred.match.sport else None
        pred.sport_icon = profile.icon
        pred.outcome_labels = {
            "home_win": profile.home_label,
            "away_win": profile.away_label,
            "draw": "Нічия",
        }
    return items
