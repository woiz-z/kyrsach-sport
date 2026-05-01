"""
AI Analyst router — read-only status and performance stats.

Single LLM provider: Google Gemini (gemini-2.0-flash, free tier).
Frontend shows: connection status, global accuracy, per-sport stats, recent analyses.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
import os

from app.database import get_db
from app.models.models import Match, MatchStatus, Prediction, Sport

router = APIRouter(prefix="/api/ai-models", tags=["AI Models"])


@router.get("/status")
async def ai_status(db: AsyncSession = Depends(get_db)):
    """Return AI engine status: LLM provider connection + prediction stats."""
    google_api_key = os.environ.get("GOOGLE_API_KEY", "")
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    llm_connected = bool(google_api_key and google_api_key.strip())
    llm_provider = "Google Gemini" if llm_connected else "Не підключено (потрібен GOOGLE_API_KEY)"
    llm_model = gemini_model if llm_connected else "—"

    total_predictions_q = await db.execute(select(func.count(Prediction.id)))
    total_predictions = total_predictions_q.scalar_one() or 0

    completed_matches_q = await db.execute(
        select(func.count(Match.id)).where(Match.status == MatchStatus.completed)
    )
    completed_matches = completed_matches_q.scalar_one() or 0

    sports_covered_q = await db.execute(
        select(func.count(func.distinct(Match.sport_id)))
        .where(Match.status == MatchStatus.completed)
    )
    sports_covered = sports_covered_q.scalar_one() or 0

    return {
        "llm": {
            "connected": llm_connected,
            "provider": llm_provider,
            "model": llm_model,
        },
        "stats": {
            "total_predictions": total_predictions,
            "completed_matches": completed_matches,
            "sports_covered": sports_covered,
        },
    }


@router.get("/performance")
async def ai_performance(db: AsyncSession = Depends(get_db)):
    """Return per-sport prediction stats."""
    sports_q = await db.execute(select(Sport))
    sports = sports_q.scalars().all()

    result = []
    for sport in sports:
        completed_q = await db.execute(
            select(func.count(Match.id))
            .where(and_(Match.sport_id == sport.id, Match.status == MatchStatus.completed))
        )
        completed = completed_q.scalar_one() or 0

        predictions_q = await db.execute(
            select(func.count(Prediction.id))
            .join(Match, Prediction.match_id == Match.id)
            .where(Match.sport_id == sport.id)
        )
        predictions = predictions_q.scalar_one() or 0

        result.append({
            "sport_id": sport.id,
            "sport_name": sport.name,
            "sport_icon": sport.icon,
            "completed_matches": completed,
            "predictions_made": predictions,
        })

    return result


@router.get("/recent-analyses")
async def recent_analyses(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Return the most recent AI predictions with match context."""
    preds_q = await db.execute(
        select(Prediction)
        .options(
            selectinload(Prediction.match).selectinload(Match.home_team),
            selectinload(Prediction.match).selectinload(Match.away_team),
            selectinload(Prediction.match).selectinload(Match.sport),
        )
        .order_by(Prediction.created_at.desc())
        .limit(limit)
    )
    preds = preds_q.scalars().all()

    return [
        {
            "id": p.id,
            "match_id": p.match_id,
            "match_date": p.match.match_date.isoformat() if p.match else None,
            "home_team": p.match.home_team.name if p.match and p.match.home_team else None,
            "away_team": p.match.away_team.name if p.match and p.match.away_team else None,
            "sport": p.match.sport.name if p.match and p.match.sport else None,
            "sport_icon": p.match.sport.icon if p.match and p.match.sport else None,
            "predicted_result": p.predicted_result,
            "has_analysis": bool(p.ai_analysis),
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in preds
    ]
