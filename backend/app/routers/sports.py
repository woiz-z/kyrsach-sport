from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app.models.models import Sport, Season
from app.schemas.schemas import SportCreate, SportResponse, SeasonResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/sports", tags=["Sports"])


@router.get("/", response_model=List[SportResponse])
async def list_sports(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Sport).order_by(Sport.name))
    return result.scalars().all()


@router.get("/seasons", response_model=List[SeasonResponse])
async def list_seasons(
    sport_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Season)
    if sport_id:
        query = query.where(Season.sport_id == sport_id)
    result = await db.execute(query.order_by(Season.start_date.desc()))
    return result.scalars().all()


@router.get("/{sport_id}", response_model=SportResponse)
async def get_sport(sport_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Sport).where(Sport.id == sport_id))
    sport = result.scalar_one_or_none()
    if not sport:
        raise HTTPException(status_code=404, detail="Вид спорту не знайдено")
    return sport


@router.post("/", response_model=SportResponse, status_code=201)
async def create_sport(data: SportCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    sport = Sport(**data.model_dump())
    db.add(sport)
    await db.flush()
    await db.refresh(sport)
    return sport
