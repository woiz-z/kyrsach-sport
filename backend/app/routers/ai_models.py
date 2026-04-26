from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from datetime import datetime, timezone
from app.database import get_db
from app.models.models import AIModel, Season, Match, MatchStatus
from app.schemas.schemas import AIModelResponse
from app.services.auth import get_current_user
from app.ai.predictor import (
    train_model as ml_train,
    get_available_models,
    rolling_backtest,
    run_ablation_study,
)
from app.ai.feature_extractor import extract_training_dataset, get_feature_names, get_feature_groups
from app.services.model_training import (
    model_sport_id,
    model_key,
    train_best_models_per_sport,
)

router = APIRouter(prefix="/api/ai-models", tags=["AI Models"])


async def _pick_best_season_id(db: AsyncSession) -> int:
    season_counts = await db.execute(
        select(Match.season_id, func.count(Match.id).label("cnt"))
        .where(Match.status == MatchStatus.completed)
        .group_by(Match.season_id)
        .order_by(func.count(Match.id).desc())
    )
    row = season_counts.first()
    if row:
        return int(row[0])

    season = await db.execute(select(Season.id).order_by(Season.id.desc()))
    season_id = season.scalars().first()
    if season_id is None:
        raise HTTPException(status_code=400, detail="Немає сезонів для тренування")
    return int(season_id)


async def _pick_best_season_id_for_sport(db: AsyncSession, sport_id: int | None) -> int:
    season_counts_query = (
        select(Match.season_id, func.count(Match.id).label("cnt"))
        .where(Match.status == MatchStatus.completed)
    )
    if sport_id:
        season_counts_query = season_counts_query.where(Match.sport_id == sport_id)

    season_counts = await db.execute(
        season_counts_query.group_by(Match.season_id).order_by(func.count(Match.id).desc())
    )
    row = season_counts.first()
    if row:
        return int(row[0])

    fallback = select(Season.id)
    if sport_id:
        fallback = fallback.where(Season.sport_id == sport_id)
    season = await db.execute(fallback.order_by(Season.id.desc()))
    season_id = season.scalars().first()
    if season_id is None:
        raise HTTPException(status_code=400, detail="Немає сезонів для тренування")
    return int(season_id)


async def _resolve_algorithm(db: AsyncSession, algorithm: str | None) -> str:
    if algorithm:
        return algorithm

    active = await db.execute(select(AIModel).where(AIModel.is_active == True).order_by(AIModel.trained_at.desc()))
    model = active.scalars().first()
    return model.algorithm if model else "gradient_boosting"


@router.get("/models", response_model=List[AIModelResponse])
async def list_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AIModel).order_by(AIModel.trained_at.desc()))
    return result.scalars().all()


@router.post("/train")
async def train(
    payload: dict | None = Body(None),
    season_id: int | None = Query(None),
    sport_id: int | None = Query(None),
    algorithm: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    if payload:
        season_id = payload.get("season_id", season_id)
        sport_id = payload.get("sport_id", sport_id)
        algorithm = payload.get("algorithm", algorithm)

    algorithm = algorithm or "gradient_boosting"
    if season_id is None:
        season_id = await _pick_best_season_id_for_sport(db, sport_id)

    # Verify season exists
    season = await db.execute(select(Season).where(Season.id == season_id))
    season_obj = season.scalar_one_or_none()
    if not season_obj:
        raise HTTPException(status_code=404, detail="Сезон не знайдено")
    if sport_id and season_obj.sport_id != sport_id:
        raise HTTPException(status_code=400, detail="Сезон не належить до обраного виду спорту")

    # Extract training data with metadata for reproducible experiment tracking.
    X, y, dataset_meta = await extract_training_dataset(db, season_id)
    if len(X) < 10:
        raise HTTPException(status_code=400,
                            detail=f"Недостатньо завершених матчів для тренування ({len(X)} з 10 необхідних)")

    seed = 42
    train_ratio = 0.8
    resolved_sport_id = int(season_obj.sport_id)
    resolved_model_key = model_key(algorithm, resolved_sport_id)

    # Train model
    try:
        metrics = ml_train(
            X,
            y,
            algorithm,
            seed=seed,
            train_ratio=train_ratio,
            model_key=resolved_model_key,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка тренування: {str(e)}")

    # Keep exactly one active model per sport.
    prev_models = await db.execute(select(AIModel).where(AIModel.is_active == True))
    for m in prev_models.scalars().all():
        if model_sport_id(m) == resolved_sport_id:
            m.is_active = False

    # Save model record
    ai_model = AIModel(
        name=f"{algorithm}_v{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
        description=f"Trained on {metrics['samples']} matches from season {season_id} (sport_id={season_obj.sport_id})",
        algorithm=algorithm,
        accuracy=metrics["accuracy"],
        precision_score=metrics["precision"],
        recall_score=metrics["recall"],
        f1=metrics["f1"],
        trained_at=metrics["trained_at"],
        is_active=True,
        parameters={
            "model_key": metrics["model_key"],
            "cv_accuracy": metrics["cv_accuracy"],
            "cv_std": metrics["cv_std"],
            "cv_folds": metrics["cv_folds"],
            "samples": metrics["samples"],
            "train_samples": metrics["train_samples"],
            "val_samples": metrics["val_samples"],
            "train_ratio": metrics["train_ratio"],
            "seed": metrics["seed"],
            "train_metrics": {
                "accuracy": metrics["train_accuracy"],
                "precision": metrics["train_precision"],
                "recall": metrics["train_recall"],
                "f1": metrics["train_f1"],
            },
            "validation_metrics": {
                "accuracy": metrics["val_accuracy"],
                "precision": metrics["val_precision"],
                "recall": metrics["val_recall"],
                "f1": metrics["val_f1"],
            },
            "dataset": {
                "season_id": season_id,
                "sport_id": resolved_sport_id,
                "first_match_date": dataset_meta[0]["match_date"] if dataset_meta else None,
                "last_match_date": dataset_meta[-1]["match_date"] if dataset_meta else None,
            },
        },
    )
    db.add(ai_model)
    await db.flush()
    await db.refresh(ai_model)

    return {
        "message": "Модель успішно натреновано",
        "model": {
            "id": ai_model.id,
            "name": ai_model.name,
            "accuracy": ai_model.accuracy,
            "f1": ai_model.f1,
            "cv_accuracy": metrics["cv_accuracy"],
            "val_accuracy": metrics["val_accuracy"],
            "val_f1": metrics["val_f1"],
            "sport_id": resolved_sport_id,
            "model_key": metrics["model_key"],
        },
    }


@router.post("/train-best-per-sport")
async def train_best_per_sport(
    min_samples: int = Query(30, ge=10, le=5000),
    seed: int = Query(42, ge=1, le=1_000_000),
    train_ratio: float = Query(0.8, ge=0.6, le=0.95),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    return await train_best_models_per_sport(
        db,
        min_samples=min_samples,
        seed=seed,
        train_ratio=train_ratio,
    )


@router.get("/available-algorithms")
async def available_algorithms():
    return get_available_models()


@router.patch("/models/{model_id}/activate")
async def activate_model(model_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(AIModel).where(AIModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Модель не знайдено")

    target_sport_id = model_sport_id(model)
    # Deactivate other active models for the same sport.
    all_models = await db.execute(select(AIModel).where(AIModel.is_active == True))
    for m in all_models.scalars().all():
        if model_sport_id(m) == target_sport_id:
            m.is_active = False

    model.is_active = True
    await db.flush()
    return {"message": f"Модель {model.name} активовано"}


@router.get("/diagnostics/backtest")
async def diagnostics_backtest(
    season_id: int | None = Query(None),
    sport_id: int | None = Query(None),
    algorithm: str | None = Query(None),
    min_train_size: int = Query(20, ge=10, le=500),
    test_size: int = Query(5, ge=1, le=50),
    seed: int = Query(42, ge=1, le=1_000_000),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    if season_id is None:
        season_id = await _pick_best_season_id_for_sport(db, sport_id)

    season = await db.execute(select(Season).where(Season.id == season_id))
    season_obj = season.scalar_one_or_none()
    if not season_obj:
        raise HTTPException(status_code=404, detail="Сезон не знайдено")

    algorithm_name = await _resolve_algorithm(db, algorithm)
    X, y, dataset_meta = await extract_training_dataset(db, season_id)
    if len(X) < 10:
        raise HTTPException(status_code=400, detail="Недостатньо матчів для backtest")

    try:
        result = rolling_backtest(
            X=X,
            y=y,
            algorithm=algorithm_name,
            seed=seed,
            min_train_size=min_train_size,
            test_size=test_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "season": {
            "id": season_obj.id,
            "name": season_obj.name,
        },
        "algorithm": algorithm_name,
        "dataset": {
            "samples": len(X),
            "first_match_date": dataset_meta[0]["match_date"] if dataset_meta else None,
            "last_match_date": dataset_meta[-1]["match_date"] if dataset_meta else None,
        },
        "backtest": result,
    }


@router.get("/diagnostics/ablation")
async def diagnostics_ablation(
    season_id: int | None = Query(None),
    sport_id: int | None = Query(None),
    algorithm: str | None = Query(None),
    train_ratio: float = Query(0.8, ge=0.6, le=0.95),
    seed: int = Query(42, ge=1, le=1_000_000),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    if season_id is None:
        season_id = await _pick_best_season_id_for_sport(db, sport_id)

    season = await db.execute(select(Season).where(Season.id == season_id))
    season_obj = season.scalar_one_or_none()
    if not season_obj:
        raise HTTPException(status_code=404, detail="Сезон не знайдено")

    algorithm_name = await _resolve_algorithm(db, algorithm)
    X, y, dataset_meta = await extract_training_dataset(db, season_id)
    if len(X) < 10:
        raise HTTPException(status_code=400, detail="Недостатньо матчів для абляції")

    try:
        result = run_ablation_study(
            X=X,
            y=y,
            feature_names=get_feature_names(),
            feature_groups=get_feature_groups(),
            algorithm=algorithm_name,
            seed=seed,
            train_ratio=train_ratio,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "season": {
            "id": season_obj.id,
            "name": season_obj.name,
        },
        "algorithm": algorithm_name,
        "dataset": {
            "samples": len(X),
            "first_match_date": dataset_meta[0]["match_date"] if dataset_meta else None,
            "last_match_date": dataset_meta[-1]["match_date"] if dataset_meta else None,
        },
        "ablation": result,
    }
