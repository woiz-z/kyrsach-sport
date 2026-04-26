from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from app.database import get_db
from app.models.models import Team, TeamStatistics, Player
from app.schemas.schemas import (
    TeamCreate, TeamResponse, TeamDetailResponse,
    TeamStatisticsResponse, TeamStatsWithTeam, PlayerResponse
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/teams", tags=["Teams"])


@router.get("/", response_model=List[TeamResponse])
async def list_teams(
    sport_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(Team)
    if sport_id:
        q = q.where(Team.sport_id == sport_id)
    result = await db.execute(q.order_by(Team.name))
    return result.scalars().all()


@router.get("/{team_id}", response_model=TeamDetailResponse)
async def get_team(team_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Team).options(selectinload(Team.sport)).where(Team.id == team_id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Команду не знайдено")
    return team


@router.get("/{team_id}/statistics", response_model=List[TeamStatisticsResponse])
async def get_team_stats(team_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TeamStatistics)
        .where(TeamStatistics.team_id == team_id)
        .order_by(TeamStatistics.season_id.desc())
    )
    return result.scalars().all()


@router.get("/{team_id}/players", response_model=List[PlayerResponse])
async def get_team_players(team_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Player).where(Player.team_id == team_id).order_by(Player.name)
    )
    return result.scalars().all()


@router.post("/", response_model=TeamResponse, status_code=201)
async def create_team(data: TeamCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    team = Team(**data.model_dump())
    db.add(team)
    await db.flush()
    await db.refresh(team)
    return team


@router.get("/standings/{season_id}", response_model=List[TeamStatsWithTeam])
async def get_standings(season_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TeamStatistics)
        .options(selectinload(TeamStatistics.team))
        .where(TeamStatistics.season_id == season_id)
        .order_by(TeamStatistics.points.desc(), (TeamStatistics.goals_for - TeamStatistics.goals_against).desc())
    )
    return result.scalars().all()
