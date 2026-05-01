from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from app.database import get_db
from app.models.models import Team, TeamStatistics, Player, Match
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
    # Dynamically compute standings from completed matches
    matches_result = await db.execute(
        select(Match)
        .where(
            and_(Match.season_id == season_id, Match.status == "completed")
        )
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
    )
    matches = matches_result.scalars().all()

    stats: dict[int, dict] = {}

    def _ensure(team: Team):
        if team.id not in stats:
            stats[team.id] = {
                "team_id": team.id,
                "season_id": season_id,
                "team": team,
                "matches_played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "goals_for": 0,
                "goals_against": 0,
                "points": 0,
                "form": [],
            }

    for m in matches:
        if m.home_score is None or m.away_score is None:
            continue
        hs, as_ = m.home_score, m.away_score
        _ensure(m.home_team)
        _ensure(m.away_team)

        h = stats[m.home_team_id]
        a = stats[m.away_team_id]

        h["matches_played"] += 1
        a["matches_played"] += 1
        h["goals_for"] += hs
        h["goals_against"] += as_
        a["goals_for"] += as_
        a["goals_against"] += hs

        if hs > as_:
            h["wins"] += 1; h["points"] += 3; h["form"].append("W")
            a["losses"] += 1; a["form"].append("L")
        elif hs < as_:
            a["wins"] += 1; a["points"] += 3; a["form"].append("W")
            h["losses"] += 1; h["form"].append("L")
        else:
            h["draws"] += 1; h["points"] += 1; h["form"].append("D")
            a["draws"] += 1; a["points"] += 1; a["form"].append("D")

    # Build response objects (reuse TeamStatsWithTeam schema structure)
    rows = []
    for s in stats.values():
        gd = s["goals_for"] - s["goals_against"]
        rows.append(TeamStatistics(
            id=0,
            team_id=s["team_id"],
            season_id=season_id,
            matches_played=s["matches_played"],
            wins=s["wins"],
            draws=s["draws"],
            losses=s["losses"],
            goals_for=s["goals_for"],
            goals_against=s["goals_against"],
            points=s["points"],
            team=s["team"],
            form_last5=s["form"][-5:],
        ))

    rows.sort(key=lambda r: (-r.points, -(r.goals_for - r.goals_against), -(r.goals_for or 0)))
    return rows
