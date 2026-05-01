"""Live match poller.

Runs every 15 seconds and:
1. Fetches ESPN summary for every match currently marked `in_progress`.
2. Detects score / event changes and updates the DB.
3. Publishes delta messages to the EventBus so SSE subscribers get them.
4. Scans today's ESPN scoreboard to catch matches that just kicked off
   (transitioning them from `scheduled` → `in_progress`).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.models import (
    Match,
    MatchEvent,
    MatchResult,
    MatchStatus,
    Prediction,
    TeamStatistics,
)
from app.services.event_bus import live_event_bus
from app.services.mega_scraper import (
    ESPN_BASE,
    _http_get_async,
    _normalize_scoreboard_events,
    _parse_events_from_summary,
    _safe_int,
    _safe_str,
)
from app.ai.sport_profiles import get_sport_profile

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 15  # seconds between polls


# ── Live probability calculation ────────────────────────────────────────────

def _calculate_live_probabilities(
    base_home: float,
    base_draw: float,
    base_away: float,
    home_score: int,
    away_score: int,
    minute: int,
    allows_draw: bool,
    red_home: int = 0,
    red_away: int = 0,
) -> dict:
    """Blend pre-match base probs with score-based probs weighted by elapsed time."""
    # Time progress 0 (kick-off) → 1 (90th min)
    t = min(minute / 90.0, 1.1) if minute else 0.0
    # Weight rises slowly at first, then quickly near end
    score_weight = t ** 1.5

    score_diff = home_score - away_score

    if score_diff > 0:
        margin = min(score_diff, 3)
        score_home = 0.88 - 0.04 * (margin - 1)
        score_draw = 0.08
        score_away = 0.04
    elif score_diff < 0:
        margin = min(abs(score_diff), 3)
        score_away = 0.88 - 0.04 * (margin - 1)
        score_draw = 0.08
        score_home = 0.04
    else:
        # Level — keep base proportions
        score_home = base_home
        score_draw = base_draw
        score_away = base_away

    home_p = (1 - score_weight) * base_home + score_weight * score_home
    draw_p = (1 - score_weight) * base_draw + score_weight * score_draw
    away_p = (1 - score_weight) * base_away + score_weight * score_away

    if not allows_draw:
        draw_p = 0.0

    # Red card penalty (man-down)
    if red_home > 0:
        home_p *= 0.75 ** red_home
    if red_away > 0:
        away_p *= 0.75 ** red_away

    # Normalise
    total = home_p + (draw_p if allows_draw else 0.0) + away_p
    if total > 0:
        home_p /= total
        if allows_draw:
            draw_p /= total
        away_p /= total

    if allows_draw and draw_p >= home_p and draw_p >= away_p:
        predicted = "draw"
        confidence = draw_p
    elif home_p >= away_p:
        predicted = "home_win"
        confidence = home_p
    else:
        predicted = "away_win"
        confidence = away_p

    return {
        "home_win_prob": round(home_p, 4),
        "draw_prob": round(draw_p if allows_draw else 0.0, 4),
        "away_win_prob": round(away_p, 4),
        "predicted_result": predicted,
        "confidence": round(confidence, 4),
    }


async def _get_base_probs(db, match: Match, allows_draw: bool) -> tuple[float, float, float]:
    """Return (home, draw, away) base pre-match probabilities."""
    # Prefer the latest stored prediction for this match
    r = await db.execute(
        select(Prediction)
        .where(Prediction.match_id == match.id)
        .order_by(Prediction.created_at.desc())
        .limit(1)
    )
    pred = r.scalar_one_or_none()
    if pred:
        return pred.home_win_prob, pred.draw_prob, pred.away_win_prob

    # Fallback: simple PPG-based calculation
    async def ppg(team_id: int) -> float:
        ts_r = await db.execute(
            select(TeamStatistics).where(
                and_(
                    TeamStatistics.team_id == team_id,
                    TeamStatistics.season_id == match.season_id,
                )
            )
        )
        ts = ts_r.scalar_one_or_none()
        if not ts or not ts.matches_played:
            return 1.0
        return (ts.points or 0) / ts.matches_played

    h = max(await ppg(match.home_team_id) * 1.15, 0.05)
    a = max(await ppg(match.away_team_id), 0.05)
    d = 0.25 if allows_draw else 0.0
    total = h + a + d
    return h / total, d / total, a / total


# ── Single-match update ──────────────────────────────────────────────────────

async def _poll_match(db, match: Match) -> None:
    """Fetch ESPN summary for one match, diff, update DB, publish to EventBus."""
    if not match.external_id:
        return

    espn_sport = match.season.espn_sport if match.season else None
    espn_league = match.season.espn_league if match.season else None
    if not espn_sport or not espn_league:
        return

    url = f"{ESPN_BASE}/{espn_sport}/{espn_league}/summary?event={match.external_id}"
    summary = await _http_get_async(url)
    if not summary:
        return

    # ── Parse score + status ──────────────────────────────────────────────
    header = summary.get("header") or {}
    competitions = header.get("competitions") or []
    if not competitions:
        return
    comp = competitions[0]

    home_score: Optional[int] = None
    away_score: Optional[int] = None
    for c in comp.get("competitors") or []:
        s = _safe_int(c.get("score"))
        ha = c.get("homeAway", "")
        if ha == "home":
            home_score = s
        elif ha == "away":
            away_score = s

    status_obj = comp.get("status") or {}
    status_type = status_obj.get("type") or {}
    is_completed = status_type.get("completed", False)
    status_state = status_type.get("state", "")

    # Parse current match minute from display clock ("45:00" → 45)
    display_clock: str = status_obj.get("displayClock") or ""
    minute: Optional[int] = None
    if display_clock:
        raw_m = display_clock.replace("'", "").split(":")[0].strip()
        minute = _safe_int(raw_m)

    # ── Parse events ───────────────────────────────────────────────────────
    new_events = _parse_events_from_summary(summary)

    # ── Detect changes ──────────────────────────────────────────────────────
    score_changed = (match.home_score != home_score) or (match.away_score != away_score)
    events_changed = len(new_events) != len(match.events or [])

    # Match just finished
    if (is_completed or status_state == "post") and match.status != MatchStatus.completed:
        match.status = MatchStatus.completed
        if home_score is not None and away_score is not None:
            if home_score > away_score:
                match.result = MatchResult.home_win
            elif away_score > home_score:
                match.result = MatchResult.away_win
            else:
                match.result = MatchResult.draw
        score_changed = True

    if not score_changed and not events_changed:
        return  # nothing new

    # ── Update DB ──────────────────────────────────────────────────────────
    if home_score is not None:
        match.home_score = home_score
    if away_score is not None:
        match.away_score = away_score

    if events_changed and new_events:
        await db.execute(delete(MatchEvent).where(MatchEvent.match_id == match.id))
        home_eid = match.home_team.espn_id if match.home_team else None
        away_eid = match.away_team.espn_id if match.away_team else None
        espn_to_team_id: dict = {}
        if home_eid:
            espn_to_team_id[home_eid] = match.home_team_id
        if away_eid:
            espn_to_team_id[away_eid] = match.away_team_id

        for ev in new_events:
            team_eid = ev.get("team_espn_id", "")
            db.add(MatchEvent(
                match_id=match.id,
                team_id=espn_to_team_id.get(team_eid),
                event_type=ev.get("event_type", "event"),
                minute=ev.get("minute"),
                detail=ev.get("detail"),
            ))

    # ── Count red cards for probability adjustment ─────────────────────────
    home_eid = match.home_team.espn_id if match.home_team else None
    away_eid = match.away_team.espn_id if match.away_team else None
    red_home = sum(
        1 for e in new_events
        if e.get("event_type") == "red_card" and e.get("team_espn_id") == home_eid
    )
    red_away = sum(
        1 for e in new_events
        if e.get("event_type") == "red_card" and e.get("team_espn_id") == away_eid
    )

    # ── Recalculate live probabilities ─────────────────────────────────────
    sport_name = match.sport.name if match.sport else None
    profile = get_sport_profile(sport_name)
    base_home, base_draw, base_away = await _get_base_probs(db, match, profile.allows_draw)
    probs = _calculate_live_probabilities(
        base_home, base_draw, base_away,
        home_score or 0, away_score or 0,
        minute or 0,
        profile.allows_draw,
        red_home, red_away,
    )

    # ── Publish to EventBus ────────────────────────────────────────────────
    await live_event_bus.publish(match.id, {
        "type": "event_update",
        "match_id": match.id,
        "home_team": match.home_team.name if match.home_team else "",
        "away_team": match.away_team.name if match.away_team else "",
        "home_score": home_score,
        "away_score": away_score,
        "minute": minute,
        "sport_name": sport_name,
        "all_events": [
            {
                "event_type": ev.get("event_type"),
                "minute": ev.get("minute"),
                "detail": ev.get("detail"),
                "is_home": ev.get("team_espn_id") == home_eid,
            }
            for ev in new_events
        ],
        "prediction": probs,
        "status": match.status.value,
    })

    logger.info(
        "[LivePoller] match=%d %s %d:%d %s (min %s) — published",
        match.id,
        match.external_id,
        home_score or 0,
        away_score or 0,
        probs["predicted_result"],
        minute,
    )


# ── Scoreboard scan for newly started matches ────────────────────────────────

async def _scan_for_new_live_matches(db) -> None:
    """Mark scheduled matches as in_progress (or completed) based on ESPN state."""
    import datetime
    now_utc = datetime.datetime.utcnow()
    # Check scoreboard for yesterday, today and tomorrow to handle timezone edge cases
    dates_to_check = [
        (now_utc - datetime.timedelta(days=1)).date().strftime("%Y%m%d"),
        now_utc.date().strftime("%Y%m%d"),
        (now_utc + datetime.timedelta(days=1)).date().strftime("%Y%m%d"),
    ]

    # Only consider scheduled matches within a reasonable window (past 24h – future 4h)
    window_start = now_utc - datetime.timedelta(hours=24)
    window_end = now_utc + datetime.timedelta(hours=4)

    r = await db.execute(
        select(Match)
        .options(selectinload(Match.season), selectinload(Match.home_team), selectinload(Match.away_team))
        .where(Match.status == MatchStatus.scheduled)
        .where(Match.external_id.isnot(None))
        .where(Match.match_date >= window_start)
        .where(Match.match_date <= window_end)
    )
    scheduled = r.scalars().all()

    pairs: set = set()
    ext_map: dict = {m.external_id: m for m in scheduled}
    for m in scheduled:
        if m.season and m.season.espn_sport and m.season.espn_league:
            pairs.add((m.season.espn_sport, m.season.espn_league))

    for espn_sport, espn_league in pairs:
        for date_str in dates_to_check:
            url = (
                f"{ESPN_BASE}/{espn_sport}/{espn_league}/scoreboard"
                f"?dates={date_str}&limit=100"
            )
            data = await _http_get_async(url)
            for ev in _normalize_scoreboard_events(espn_sport, (data or {}).get("events") or []):
                st = (ev.get("status") or {}).get("type") or {}
                state = st.get("state", "")
                is_completed = st.get("completed", False)
                eid = _safe_str(ev.get("id"))
                if not eid or eid not in ext_map:
                    continue
                match = ext_map[eid]
                if match.status != MatchStatus.scheduled:
                    continue

                if state == "in":
                    match.status = MatchStatus.in_progress
                    logger.info("[LivePoller] Match %d (%s) → in_progress", match.id, eid)
                elif state == "post" or is_completed:
                    # Match finished without being caught in-progress — resolve from scoreboard
                    match.status = MatchStatus.completed
                    comps = ev.get("competitions") or []
                    if comps:
                        comp = comps[0]
                        home_score: Optional[int] = None
                        away_score: Optional[int] = None
                        for c in comp.get("competitors") or []:
                            s = _safe_int(c.get("score"))
                            ha = c.get("homeAway", "")
                            if ha == "home":
                                home_score = s
                            elif ha == "away":
                                away_score = s
                        if home_score is not None:
                            match.home_score = home_score
                        if away_score is not None:
                            match.away_score = away_score
                        if home_score is not None and away_score is not None:
                            if home_score > away_score:
                                match.result = MatchResult.home_win
                            elif away_score > home_score:
                                match.result = MatchResult.away_win
                            else:
                                match.result = MatchResult.draw
                    logger.info(
                        "[LivePoller] Match %d (%s) → completed directly (was scheduled)",
                        match.id, eid,
                    )


# ── Main loop ────────────────────────────────────────────────────────────────

async def poll_once() -> None:
    async with async_session() as db:
        try:
            # 1. Update already-live matches
            r = await db.execute(
                select(Match)
                .options(
                    selectinload(Match.home_team),
                    selectinload(Match.away_team),
                    selectinload(Match.sport),
                    selectinload(Match.season),
                    selectinload(Match.events),
                )
                .where(Match.status == MatchStatus.in_progress)
                .where(Match.external_id.isnot(None))
            )
            live_matches = r.scalars().all()

            for match in live_matches:
                try:
                    await _poll_match(db, match)
                except Exception as exc:
                    logger.warning("[LivePoller] Error polling match %d: %s", match.id, exc)

            # 2. Detect newly started matches
            try:
                await _scan_for_new_live_matches(db)
            except Exception as exc:
                logger.warning("[LivePoller] Scan error: %s", exc)

            await db.commit()
        except Exception as exc:
            logger.error("[LivePoller] poll_once failed: %s", exc)
            try:
                await db.rollback()
            except Exception:
                pass


async def run_live_poller_loop() -> None:
    """Run forever, polling every _POLL_INTERVAL seconds. Start via asyncio.create_task."""
    logger.info("[LivePoller] Started (interval=%ds)", _POLL_INTERVAL)
    while True:
        await asyncio.sleep(_POLL_INTERVAL)
        await poll_once()
