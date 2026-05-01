from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from app.database import get_db
from app.models.models import Match, Prediction, Team, Sport, MatchStatus
from app.schemas.schemas import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(
    sport_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    def _sport_filter(q, model=Match):
        if sport_id:
            return q.where(model.sport_id == sport_id)
        return q

    total_matches = (await db.execute(_sport_filter(select(func.count()).select_from(Match)))).scalar() or 0
    completed = (await db.execute(
        _sport_filter(select(func.count()).select_from(Match).where(Match.status == MatchStatus.completed))
    )).scalar() or 0
    upcoming = (await db.execute(
        _sport_filter(select(func.count()).select_from(Match).where(Match.status == MatchStatus.scheduled))
    )).scalar() or 0

    def _pred_filter(q):
        if sport_id:
            return q.where(Prediction.match.has(Match.sport_id == sport_id))
        return q

    total_preds = (await db.execute(_pred_filter(select(func.count()).select_from(Prediction)))).scalar() or 0
    correct_preds = (await db.execute(
        _pred_filter(select(func.count()).select_from(Prediction).where(Prediction.is_correct == True))
    )).scalar() or 0
    resolved_preds = (await db.execute(
        _pred_filter(select(func.count()).select_from(Prediction).where(Prediction.is_correct.isnot(None)))
    )).scalar() or 0

    if sport_id:
        # Count teams that have at least one match in this sport
        total_teams = (await db.execute(
            select(func.count(func.distinct(Match.home_team_id))).where(Match.sport_id == sport_id)
        )).scalar() or 0
    else:
        total_teams = (await db.execute(select(func.count()).select_from(Team))).scalar() or 0
    total_sports = (await db.execute(select(func.count()).select_from(Sport))).scalar() or 0

    accuracy = (correct_preds / resolved_preds * 100) if resolved_preds > 0 else 0.0

    return DashboardStats(
        total_matches=total_matches,
        completed_matches=completed,
        upcoming_matches=upcoming,
        total_predictions=total_preds,
        correct_predictions=correct_preds,
        accuracy_percent=round(accuracy, 1),
        total_teams=total_teams,
        total_sports=total_sports,
    )
