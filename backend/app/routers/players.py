from datetime import date
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, Integer, or_
from sqlalchemy.orm import selectinload

from app.database import get_db, get_session_factory
from app.models.models import Player, Team, MatchLineup, MatchEvent, Match, Sport
from app.schemas.schemas import (
    PlayerDetailResponse,
    TeamBriefResponse,
    CareerStatsResponse,
    RecentMatchResponse,
)
from app.services.wiki_enricher import enrich_player

router = APIRouter(prefix="/api/players", tags=["players"])


def _calc_age(dob: date | None) -> int | None:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# ── Player list endpoint ─────────────────────────────────────────────────────
@router.get("/", response_model=List[dict])
async def list_players(
    sport_id: Optional[int] = Query(None),
    team_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """List players, optionally filtered by sport, team, or search string."""
    q = select(Player).options(selectinload(Player.team))

    if team_id:
        q = q.where(Player.team_id == team_id)
    elif sport_id:
        # Filter players whose team belongs to the given sport
        q = q.join(Team, Player.team_id == Team.id).where(Team.sport_id == sport_id)

    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.where(
            or_(Player.name.ilike(term), Player.nationality.ilike(term))
        )

    q = q.order_by(Player.name).limit(limit).offset(offset)
    result = await db.execute(q)
    players = result.scalars().all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "nationality": p.nationality,
            "position": p.position,
            "jersey_number": p.jersey_number,
            "photo_url": p.photo_url,
            "team": {"id": p.team.id, "name": p.team.name} if p.team else None,
        }
        for p in players
    ]


@router.get("/{player_id}", response_model=PlayerDetailResponse)
async def get_player_detail(
    player_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    session_factory=Depends(get_session_factory),
):
    # Fetch player + team eagerly
    result = await db.execute(
        select(Player)
        .options(selectinload(Player.team))
        .where(Player.id == player_id)
    )
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Career stats from lineups
    lineup_result = await db.execute(
        select(
            func.count(MatchLineup.id).label("appearances"),
            func.sum(func.cast(MatchLineup.is_starter, Integer)).label("starts"),
            func.coalesce(func.sum(MatchLineup.minutes_played), 0).label("minutes_played"),
        ).where(MatchLineup.player_id == player_id)
    )
    lu = lineup_result.one()

    # Events: goals, assists, cards
    event_result = await db.execute(
        select(MatchEvent.event_type, func.count(MatchEvent.id).label("cnt"))
        .where(MatchEvent.player_id == player_id)
        .group_by(MatchEvent.event_type)
    )
    event_counts: dict[str, int] = {row.event_type: row.cnt for row in event_result.all()}

    career = CareerStatsResponse(
        appearances=lu.appearances or 0,
        starts=int(lu.starts or 0),
        minutes_played=int(lu.minutes_played or 0),
        goals=event_counts.get("goal", 0),
        assists=event_counts.get("assist", 0),
        yellow_cards=event_counts.get("yellow_card", 0),
        red_cards=event_counts.get("red_card", 0),
    )

    # Prefer ESPN stats_json when it has more appearances than DB-computed stats
    # (DB only covers enriched matches, ESPN has full season data)
    if player.stats_json:
        sj = player.stats_json
        sj_appearances = int(sj.get("appearances", 0))
        if sj_appearances > career.appearances:
            career = CareerStatsResponse(
                appearances=sj_appearances,
                starts=int(sj.get("starts", 0)),
                minutes_played=int(sj.get("minutes_played", 0)),
                goals=int(sj.get("goals", 0)),
                assists=int(sj.get("assists", 0)),
                yellow_cards=int(sj.get("yellow_cards", 0)),
                red_cards=int(sj.get("red_cards", 0)),
            )

    # Recent 10 matches via lineups
    recent_lineups_result = await db.execute(
        select(MatchLineup)
        .options(
            selectinload(MatchLineup.match).selectinload(Match.home_team),
            selectinload(MatchLineup.match).selectinload(Match.away_team),
        )
        .where(MatchLineup.player_id == player_id)
        .order_by(MatchLineup.match_id.desc())
        .limit(10)
    )
    recent_lineups = recent_lineups_result.scalars().all()

    recent_matches: list[RecentMatchResponse] = []
    for lu_row in recent_lineups:
        m = lu_row.match
        # Count goals/assists in this specific match
        match_events_result = await db.execute(
            select(MatchEvent.event_type, func.count(MatchEvent.id).label("cnt"))
            .where(
                MatchEvent.player_id == player_id,
                MatchEvent.match_id == m.id,
            )
            .group_by(MatchEvent.event_type)
        )
        me_counts: dict[str, int] = {row.event_type: row.cnt for row in match_events_result.all()}

        recent_matches.append(RecentMatchResponse(
            match_id=m.id,
            match_date=m.match_date,
            home_team=m.home_team.name if m.home_team else "",
            away_team=m.away_team.name if m.away_team else "",
            home_score=m.home_score,
            away_score=m.away_score,
            is_starter=lu_row.is_starter,
            minutes_played=lu_row.minutes_played,
            goals_in_match=me_counts.get("goal", 0),
            assists_in_match=me_counts.get("assist", 0),
        ))

    team_brief: TeamBriefResponse | None = None
    if player.team:
        team_brief = TeamBriefResponse(
            id=player.team.id,
            name=player.team.name,
            logo_url=player.team.logo_url,
            sport_id=player.team.sport_id,
        )

    # Trigger Wikipedia enrichment in background if bio or photo is missing
    needs_enrich = not player.bio or not player.photo_url
    if needs_enrich:
        background_tasks.add_task(enrich_player, player_id, session_factory)

    return PlayerDetailResponse(
        id=player.id,
        name=player.name,
        position=player.position,
        date_of_birth=player.date_of_birth,
        nationality=player.nationality,
        photo_url=player.photo_url,
        height_cm=player.height_cm,
        weight_kg=player.weight_kg,
        jersey_number=player.jersey_number,
        espn_id=player.espn_id,
        age=_calc_age(player.date_of_birth),
        bio=player.bio,
        team=team_brief,
        career_stats=career,
        recent_matches=recent_matches,
    )
