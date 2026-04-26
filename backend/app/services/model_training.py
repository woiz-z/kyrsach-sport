from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.feature_extractor import extract_training_dataset
from app.ai.predictor import ALGORITHMS, train_model as ml_train
from app.models.models import AIModel, Sport


def model_sport_id(model: AIModel) -> int | None:
    params = model.parameters or {}
    dataset = params.get("dataset") if isinstance(params, dict) else {}
    if isinstance(dataset, dict):
        return dataset.get("sport_id")
    return None


def model_key(algorithm: str, sport_id: int) -> str:
    return f"{algorithm}_sport_{sport_id}"


def selection_score(metrics: dict) -> tuple[float, float, float]:
    return (
        float(metrics.get("val_f1") or 0.0),
        float(metrics.get("cv_accuracy") or 0.0),
        float(metrics.get("val_accuracy") or 0.0),
    )


async def pick_best_season_id_for_sport(db: AsyncSession, sport_id: int) -> int | None:
    from app.models.models import Match, MatchStatus, Season
    from sqlalchemy import func

    season_counts_query = (
        select(Match.season_id)
        .where(Match.status == MatchStatus.completed)
        .where(Match.sport_id == sport_id)
        .group_by(Match.season_id)
        .order_by(func.count(Match.id).desc())
    )
    season_counts = await db.execute(season_counts_query)
    row = season_counts.first()
    if row:
        return int(row[0])

    fallback = await db.execute(
        select(Season.id).where(Season.sport_id == sport_id).order_by(Season.id.desc())
    )
    season_id = fallback.scalars().first()
    if season_id is None:
        return None
    return int(season_id)


async def train_best_models_per_sport(
    db: AsyncSession,
    min_samples: int = 30,
    seed: int = 42,
    train_ratio: float = 0.8,
) -> dict:
    sports = (await db.execute(select(Sport).order_by(Sport.id.asc()))).scalars().all()
    results: List[Dict] = []

    for sport in sports:
        season_id = await pick_best_season_id_for_sport(db, sport.id)
        if season_id is None:
            results.append(
                {
                    "sport_id": sport.id,
                    "sport_name": sport.name,
                    "status": "skipped",
                    "reason": "Немає сезону для тренування",
                }
            )
            continue

        X, y, dataset_meta = await extract_training_dataset(db, season_id)
        if len(X) < min_samples:
            results.append(
                {
                    "sport_id": sport.id,
                    "sport_name": sport.name,
                    "status": "skipped",
                    "season_id": season_id,
                    "samples": len(X),
                    "reason": f"Недостатньо матчів (< {min_samples})",
                }
            )
            continue

        candidates: List[tuple[str, dict]] = []
        train_errors: List[Dict[str, str]] = []

        for algorithm in ALGORITHMS.keys():
            try:
                metrics = ml_train(
                    X,
                    y,
                    algorithm,
                    seed=seed,
                    train_ratio=train_ratio,
                    model_key=model_key(algorithm, sport.id),
                )
                candidates.append((algorithm, metrics))
            except Exception as exc:
                train_errors.append({"algorithm": algorithm, "error": str(exc)})

        if not candidates:
            results.append(
                {
                    "sport_id": sport.id,
                    "sport_name": sport.name,
                    "status": "failed",
                    "season_id": season_id,
                    "samples": len(X),
                    "errors": train_errors,
                }
            )
            continue

        best_algorithm, best_metrics = max(candidates, key=lambda item: selection_score(item[1]))

        prev_models = await db.execute(select(AIModel).where(AIModel.is_active == True))
        for m in prev_models.scalars().all():
            if model_sport_id(m) == sport.id:
                m.is_active = False

        ai_model = AIModel(
            name=f"{best_algorithm}_sport{sport.id}_v{datetime.utcnow().strftime('%Y%m%d%H%M')}",
            description=f"Best model for sport={sport.name} trained on {best_metrics['samples']} matches from season {season_id}",
            algorithm=best_algorithm,
            accuracy=best_metrics["accuracy"],
            precision_score=best_metrics["precision"],
            recall_score=best_metrics["recall"],
            f1=best_metrics["f1"],
            trained_at=best_metrics["trained_at"],
            is_active=True,
            parameters={
                "model_key": best_metrics["model_key"],
                "cv_accuracy": best_metrics["cv_accuracy"],
                "cv_std": best_metrics["cv_std"],
                "cv_folds": best_metrics["cv_folds"],
                "samples": best_metrics["samples"],
                "train_samples": best_metrics["train_samples"],
                "val_samples": best_metrics["val_samples"],
                "train_ratio": best_metrics["train_ratio"],
                "seed": best_metrics["seed"],
                "train_metrics": {
                    "accuracy": best_metrics["train_accuracy"],
                    "precision": best_metrics["train_precision"],
                    "recall": best_metrics["train_recall"],
                    "f1": best_metrics["train_f1"],
                },
                "validation_metrics": {
                    "accuracy": best_metrics["val_accuracy"],
                    "precision": best_metrics["val_precision"],
                    "recall": best_metrics["val_recall"],
                    "f1": best_metrics["val_f1"],
                },
                "dataset": {
                    "season_id": season_id,
                    "sport_id": sport.id,
                    "first_match_date": dataset_meta[0]["match_date"] if dataset_meta else None,
                    "last_match_date": dataset_meta[-1]["match_date"] if dataset_meta else None,
                },
            },
        )
        db.add(ai_model)
        await db.flush()

        results.append(
            {
                "sport_id": sport.id,
                "sport_name": sport.name,
                "status": "trained",
                "season_id": season_id,
                "samples": len(X),
                "best_algorithm": best_algorithm,
                "model_id": ai_model.id,
                "model_key": best_metrics["model_key"],
                "val_f1": best_metrics["val_f1"],
                "cv_accuracy": best_metrics["cv_accuracy"],
                "val_accuracy": best_metrics["val_accuracy"],
                "candidates": [
                    {
                        "algorithm": algo,
                        "val_f1": m["val_f1"],
                        "cv_accuracy": m["cv_accuracy"],
                        "val_accuracy": m["val_accuracy"],
                    }
                    for algo, m in candidates
                ],
                "errors": train_errors,
            }
        )

    await db.commit()

    return {
        "message": "Навчання завершено: по одній найкращій моделі на вид спорту",
        "sports_total": len(sports),
        "sports_trained": sum(1 for r in results if r.get("status") == "trained"),
        "sports_skipped": sum(1 for r in results if r.get("status") == "skipped"),
        "sports_failed": sum(1 for r in results if r.get("status") == "failed"),
        "results": results,
    }
