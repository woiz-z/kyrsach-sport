"""Bootstrap default sport records for multi-sport experience."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Sport

DEFAULT_SPORTS = [
    {"name": "Футбол", "description": "Асоціативний футбол", "icon": "⚽"},
    {"name": "Баскетбол", "description": "Класичний командний баскетбол", "icon": "🏀"},
    {"name": "Теніс", "description": "Одиночний та парний теніс", "icon": "🎾"},
    {"name": "Хокей", "description": "Хокей на льоду", "icon": "🏒"},
    {"name": "Волейбол", "description": "Класичний волейбол", "icon": "🏐"},
    {"name": "Кіберспорт", "description": "Змагальні кіберспортивні дисципліни", "icon": "🎮"},
]


async def ensure_default_sports(db: AsyncSession) -> None:
    existing = await db.execute(select(Sport))
    existing_names = {s.name for s in existing.scalars().all()}

    for payload in DEFAULT_SPORTS:
        if payload["name"] in existing_names:
            continue
        db.add(Sport(**payload))
