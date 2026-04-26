from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.models import Match, MatchStatus, Team
from app.schemas.schemas import MatchCreate, MatchUpdate, MatchResponse, MatchDetailResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/matches", tags=["Matches"])


@router.get("/", response_model=List[MatchDetailResponse])
async def list_matches(
    sport_id: Optional[int] = Query(None),
    season_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    q = select(Match).options(
        selectinload(Match.home_team),
        selectinload(Match.away_team),
        selectinload(Match.sport),
        selectinload(Match.season),
    )
    if sport_id:
        q = q.where(Match.sport_id == sport_id)
    if season_id:
        q = q.where(Match.season_id == season_id)
    if status:
        try:
            status_enum = MatchStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Невідомий статус: {status}")
        q = q.where(Match.status == status_enum)
    if search:
        term = f"%{search}%"
        q = q.where(or_(
            Match.home_team.has(Team.name.ilike(term)),
            Match.away_team.has(Team.name.ilike(term)),
        ))
    q = q.order_by(Match.match_date.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/upcoming", response_model=List[MatchDetailResponse])
async def upcoming_matches(
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    q = (
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team), selectinload(Match.sport), selectinload(Match.season))
        .where(and_(Match.status == MatchStatus.scheduled, Match.match_date >= now))
        .order_by(Match.match_date.asc())
        .limit(limit)
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/results", response_model=List[MatchDetailResponse])
async def match_results(
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team), selectinload(Match.sport), selectinload(Match.season))
        .where(Match.status == MatchStatus.completed)
        .order_by(Match.match_date.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{match_id}", response_model=MatchDetailResponse)
async def get_match(match_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team), selectinload(Match.sport), selectinload(Match.season))
        .where(Match.id == match_id)
    )
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не знайдено")
    return match


@router.post("/", response_model=MatchResponse, status_code=201)
async def create_match(data: MatchCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    match = Match(**data.model_dump())
    db.add(match)
    await db.flush()
    await db.refresh(match)
    return match


@router.patch("/{match_id}", response_model=MatchResponse)
async def update_match(match_id: int, data: MatchUpdate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не знайдено")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(match, field, value)
    await db.flush()
    await db.refresh(match)
    return match
