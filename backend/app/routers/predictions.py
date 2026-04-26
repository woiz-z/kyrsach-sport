from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.models import (
    Prediction, Match, MatchStatus, MatchResult,
    TeamStatistics, HeadToHead, AIModel, User, Team
)
from app.schemas.schemas import PredictionRequest, PredictionResponse, PredictionDetailResponse, AIModelResponse
from app.services.auth import get_current_user
from app.ai.feature_extractor import extract_features_for_match, features_to_array, get_team_stats, get_h2h
from app.ai.predictor import predict as ml_predict
from app.ai.llm_analyzer import generate_match_analysis
from app.ai.sport_profiles import get_sport_profile
from app.services.model_training import model_sport_id as _model_sport_id

router = APIRouter(prefix="/api/predictions", tags=["Predictions"])


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

    # Extract features
    features = await extract_features_for_match(db, req.match_id)
    if not features:
        raise HTTPException(status_code=400, detail="Не вдалося витягнути ознаки для матчу")

    feature_array = features_to_array(features)

    # Pick an active model specific to this sport, fallback to latest for sport.
    active_models = (
        await db.execute(select(AIModel).where(AIModel.is_active == True).order_by(AIModel.trained_at.desc()))
    ).scalars().all()
    model_record = next((m for m in active_models if _model_sport_id(m) == match.sport_id), None)

    if model_record is None:
        all_models = (
            await db.execute(select(AIModel).order_by(AIModel.trained_at.desc()))
        ).scalars().all()
        model_record = next((m for m in all_models if _model_sport_id(m) == match.sport_id), None)

    algorithm = model_record.algorithm if model_record else "gradient_boosting"
    model_key = None
    if model_record and isinstance(model_record.parameters, dict):
        model_key = model_record.parameters.get("model_key")
    sport_profile = get_sport_profile(match.sport.name if match.sport else None)

    # ML prediction
    pred = ml_predict(
        feature_array,
        algorithm,
        allows_draw=sport_profile.allows_draw,
        model_key=model_key,
    )

    # Get team stats for LLM
    home_stats = await get_team_stats(db, match.home_team_id, match.season_id)
    away_stats = await get_team_stats(db, match.away_team_id, match.season_id)
    h2h = await get_h2h(db, match.home_team_id, match.away_team_id)

    # LLM analysis
    ai_analysis = await generate_match_analysis(
        home_team=match.home_team.name,
        away_team=match.away_team.name,
        prediction=pred,
        home_stats=home_stats,
        away_stats=away_stats,
        h2h=h2h,
        sport_name=match.sport.name if match.sport else None,
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
        model_name=model_record.name if model_record else pred["model_name"],
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


@router.get("/", response_model=List[PredictionDetailResponse])
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
