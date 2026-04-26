from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.models import Match, Prediction, Team, Sport, MatchStatus
from app.schemas.schemas import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    total_matches = (await db.execute(select(func.count()).select_from(Match))).scalar() or 0
    completed = (await db.execute(
        select(func.count()).select_from(Match).where(Match.status == MatchStatus.completed)
    )).scalar() or 0
    upcoming = (await db.execute(
        select(func.count()).select_from(Match).where(Match.status == MatchStatus.scheduled)
    )).scalar() or 0
    total_preds = (await db.execute(select(func.count()).select_from(Prediction))).scalar() or 0
    correct_preds = (await db.execute(
        select(func.count()).select_from(Prediction).where(Prediction.is_correct == True)
    )).scalar() or 0
    resolved_preds = (await db.execute(
        select(func.count()).select_from(Prediction).where(Prediction.is_correct.isnot(None))
    )).scalar() or 0
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
