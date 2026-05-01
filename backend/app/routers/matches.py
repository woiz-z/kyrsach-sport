from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, date, timedelta
from app.database import get_db
from app.models.models import Match, MatchStatus, MatchStatLine, MatchLineup, MatchEvent, Team, Player
from app.schemas.schemas import MatchCreate, MatchUpdate, MatchResponse, MatchDetailResponse, MatchRichDetail, MatchLineupEntry, MatchEventEntry
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/matches", tags=["Matches"])


@router.get("/", response_model=List[MatchDetailResponse])
async def list_matches(
    sport_id: Optional[int] = Query(None),
    season_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
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
    status_enum = None
    if status:
        try:
            status_enum = MatchStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Невідомий статус: {status}")
        q = q.where(Match.status == status_enum)
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d")
            q = q.where(Match.match_date >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            q = q.where(Match.match_date < dt_to)
        except ValueError:
            pass
    if search:
        term = f"%{search}%"
        q = q.where(or_(
            Match.home_team.has(Team.name.ilike(term)),
            Match.away_team.has(Team.name.ilike(term)),
        ))
    # Sort: scheduled/in_progress → ASC (soonest first); completed → DESC (newest first)
    if status_enum == MatchStatus.completed:
        q = q.order_by(Match.match_date.desc())
    else:
        q = q.order_by(Match.match_date.asc())
    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/upcoming", response_model=List[MatchDetailResponse])
async def upcoming_matches(
    limit: int = Query(10, le=50),
    sport_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    filters = [Match.status == MatchStatus.scheduled, Match.match_date >= now]
    if sport_id:
        filters.append(Match.sport_id == sport_id)
    q = (
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team), selectinload(Match.sport), selectinload(Match.season))
        .where(and_(*filters))
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


@router.get("/{match_id}", response_model=MatchRichDetail)
async def get_match(match_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team), selectinload(Match.sport), selectinload(Match.season))
        .where(Match.id == match_id)
    )
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не знайдено")

    # Load lineups
    lineup_q = await db.execute(
        select(MatchLineup).options(selectinload(MatchLineup.player))
        .where(MatchLineup.match_id == match_id)
        .order_by(MatchLineup.is_starter.desc(), MatchLineup.jersey_number)
    )
    lineups = lineup_q.scalars().all()

    home_lineup = []
    away_lineup = []
    for ln in lineups:
        entry = MatchLineupEntry(
            player_id=ln.player_id,
            player_name=ln.player.name if ln.player else f"Player {ln.player_id}",
            team_id=ln.team_id,
            is_starter=ln.is_starter,
            position=ln.position,
            jersey_number=ln.jersey_number,
            minutes_played=ln.minutes_played,
            photo_url=ln.player.photo_url if ln.player else None,
        )
        if ln.team_id == match.home_team_id:
            home_lineup.append(entry)
        else:
            away_lineup.append(entry)

    # Load events
    events_q = await db.execute(
        select(MatchEvent)
        .where(MatchEvent.match_id == match_id)
        .order_by(MatchEvent.minute)
    )
    raw_events = events_q.scalars().all()
    events = [
        MatchEventEntry(
            id=ev.id,
            event_type=ev.event_type,
            minute=ev.minute,
            detail=ev.detail,
            team_id=ev.team_id,
            player_id=ev.player_id,
        )
        for ev in raw_events
    ]

    # Load stats
    stats_q = await db.execute(
        select(MatchStatLine).where(MatchStatLine.match_id == match_id)
    )
    stat_lines = stats_q.scalars().all()
    home_stats = next((sl.stats for sl in stat_lines if sl.is_home), None)
    away_stats = next((sl.stats for sl in stat_lines if not sl.is_home), None)

    # Build rich response manually (avoid ORM re-serialization issues)
    return MatchRichDetail(
        id=match.id,
        sport_id=match.sport_id,
        season_id=match.season_id,
        home_team_id=match.home_team_id,
        away_team_id=match.away_team_id,
        match_date=match.match_date,
        venue=match.venue,
        status=match.status.value,
        home_score=match.home_score,
        away_score=match.away_score,
        result=match.result.value if match.result else None,
        external_id=match.external_id,
        enriched=match.enriched,
        home_team=match.home_team,
        away_team=match.away_team,
        sport=match.sport,
        season=match.season,
        home_lineup=home_lineup,
        away_lineup=away_lineup,
        events=events,
        home_stats=home_stats,
        away_stats=away_stats,
    )


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
