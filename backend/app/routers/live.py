"""Live match endpoints.

GET /api/live/matches          — list all in_progress matches
GET /api/live/{match_id}/stream — SSE stream: event_update + ai_token events
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import Match, MatchStatus
from app.schemas.schemas import MatchDetailResponse
from app.services.event_bus import live_event_bus
from app.services.live_poller import _calculate_live_probabilities, _get_base_probs
from app.ai.live_analyzer import stream_live_analysis
from app.ai.sport_profiles import get_sport_profile

router = APIRouter(prefix="/api/live", tags=["Live"])
logger = logging.getLogger(__name__)


# ── List live matches ────────────────────────────────────────────────────────

@router.get("/matches", response_model=List[MatchDetailResponse])
async def list_live_matches(
    sport_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return every match currently in_progress."""
    query = (
        select(Match)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.sport),
            selectinload(Match.season),
        )
        .where(Match.status == MatchStatus.in_progress)
    )
    if sport_id is not None:
        query = query.where(Match.sport_id == sport_id)

    r = await db.execute(
        query.order_by(Match.match_date.asc())
    )
    return r.scalars().all()


# ── SSE stream generator ─────────────────────────────────────────────────────

async def _stream_generator(match_id: int, db: AsyncSession):
    """
    Async generator yielding SSE-formatted strings.

    Events emitted:
      snapshot      — initial full state (sent once on connect)
      event_update  — new score / event detected by the poller
      ai_token      — one text token from Gemini live analysis
      ai_done       — Gemini stream finished
      ping          — keep-alive (every ~25 s of silence)
    """
    # ── Load initial state ─────────────────────────────────────────────────
    r = await db.execute(
        select(Match)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.sport),
            selectinload(Match.season),
            selectinload(Match.events),
        )
        .where(Match.id == match_id)
    )
    match = r.scalar_one_or_none()
    if not match:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Матч не знайдено'})}\n\n"
        return

    sport_name = match.sport.name if match.sport else None
    profile = get_sport_profile(sport_name)
    base_home, base_draw, base_away = await _get_base_probs(db, match, profile.allows_draw)

    home_score = match.home_score or 0
    away_score = match.away_score or 0
    latest_minute = max((e.minute or 0 for e in match.events), default=0)

    initial_probs = _calculate_live_probabilities(
        base_home, base_draw, base_away,
        home_score, away_score, latest_minute,
        profile.allows_draw,
    )

    all_events = [
        {
            "event_type": e.event_type,
            "minute": e.minute,
            "detail": e.detail,
            "is_home": e.team_id == match.home_team_id,
        }
        for e in sorted(match.events, key=lambda e: e.minute or 0)
    ]

    # ── Send snapshot ──────────────────────────────────────────────────────
    yield "data: " + json.dumps({
        "type": "snapshot",
        "match_id": match_id,
        "home_team": match.home_team.name if match.home_team else "",
        "away_team": match.away_team.name if match.away_team else "",
        "home_score": home_score,
        "away_score": away_score,
        "minute": latest_minute,
        "status": match.status.value,
        "all_events": all_events,
        "prediction": initial_probs,
        "sport_name": sport_name,
        "sport_icon": match.sport.icon if match.sport else "",
        "allows_draw": profile.allows_draw,
        "outcome_labels": {
            "home_win": profile.home_label,
            "away_win": profile.away_label,
            "draw": "Нічия",
        },
    }) + "\n\n"

    # If not live, we're done
    if match.status != MatchStatus.in_progress:
        return

    # ── Subscribe + combined queue ─────────────────────────────────────────
    bus_queue: asyncio.Queue = live_event_bus.subscribe(match_id)
    combined_q: asyncio.Queue = asyncio.Queue(maxsize=200)
    ai_tasks: list[asyncio.Task] = []

    # Seed the queue with the initial state so AI fires immediately on connect
    _initial_event = {
        "type": "event_update",
        "home_team": match.home_team.name if match.home_team else "",
        "away_team": match.away_team.name if match.away_team else "",
        "home_score": home_score,
        "away_score": away_score,
        "minute": latest_minute,
        "sport_name": sport_name,
        "all_events": all_events,
        "prediction": initial_probs,
        "status": match.status.value,
    }

    async def _relay():
        while True:
            try:
                msg = await asyncio.wait_for(bus_queue.get(), timeout=25.0)
                await combined_q.put(msg)
            except asyncio.TimeoutError:
                await combined_q.put({"type": "ping"})
            except asyncio.CancelledError:
                break

    async def _stream_ai(event_data: dict) -> None:
        try:
            async for token in stream_live_analysis(
                home_team=event_data.get("home_team", ""),
                away_team=event_data.get("away_team", ""),
                home_score=event_data.get("home_score", 0),
                away_score=event_data.get("away_score", 0),
                minute=event_data.get("minute"),
                recent_events=event_data.get("all_events", []),
                prediction=event_data.get("prediction", {}),
                sport_name=event_data.get("sport_name"),
            ):
                await combined_q.put({"type": "ai_token", "token": token})
        except Exception as exc:
            logger.warning("[Live SSE] AI stream error: %s", exc)
        finally:
            await combined_q.put({"type": "ai_done"})

    relay_task = asyncio.create_task(_relay())

    # Kick off initial AI analysis immediately (no need to wait for an event)
    t0 = asyncio.create_task(_stream_ai(_initial_event))
    ai_tasks.append(t0)

    try:
        while True:
            try:
                msg = await asyncio.wait_for(combined_q.get(), timeout=60.0)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                continue

            msg_type = msg.get("type")

            if msg_type == "ping":
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"

            elif msg_type == "event_update":
                yield "data: " + json.dumps(msg) + "\n\n"
                # Kick off AI analysis in background (non-blocking)
                t = asyncio.create_task(_stream_ai(msg))
                ai_tasks.append(t)
                # Trim completed tasks list
                ai_tasks[:] = [t for t in ai_tasks if not t.done()]

            elif msg_type in ("ai_token", "ai_done"):
                yield "data: " + json.dumps(msg) + "\n\n"

            # Stop streaming when match is complete
            if msg_type == "event_update" and msg.get("status") == "completed":
                yield f"data: {json.dumps({'type': 'match_ended'})}\n\n"
                break

    except (GeneratorExit, asyncio.CancelledError):
        pass
    finally:
        relay_task.cancel()
        for t in ai_tasks:
            t.cancel()
        live_event_bus.unsubscribe(match_id, bus_queue)


# ── SSE endpoint ─────────────────────────────────────────────────────────────

@router.get("/{match_id}/stream")
async def live_match_stream(match_id: int, db: AsyncSession = Depends(get_db)):
    """
    SSE stream for a live match.
    Connect with EventSource('/api/live/{id}/stream').
    No auth required — match data is public.
    """
    return StreamingResponse(
        _stream_generator(match_id, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
