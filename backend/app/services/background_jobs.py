"""Background job: auto-complete past scheduled matches and keep stats fresh."""
import asyncio
import random
from datetime import datetime, timezone
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.models import (
    Match, MatchStatus, MatchResult, TeamStatistics, HeadToHead, Prediction,
)
from app.ai.sport_profiles import get_sport_profile

# Do NOT fix the random seed here — we want variety per run
_rng = random.Random()


def _simulate_result(home_ppg: float, away_ppg: float, allows_draw: bool = True):
    """Return (home_goals, away_goals, MatchResult) based on both teams' PPG."""
    h = max(home_ppg, 0.1) + 0.15   # home advantage
    a = max(away_ppg, 0.1)
    draw_weight = 0.45 if allows_draw else 0.0
    total = h + a + draw_weight
    p_home = h / total
    p_draw = draw_weight / total

    r = _rng.random()
    if r < p_home:
        hg = _rng.choices([1, 2, 3, 4], weights=[30, 40, 20, 10])[0]
        ag = _rng.choices([0, 1, 2], weights=[40, 40, 20])[0]
        if hg <= ag:
            hg = ag + 1
        return hg, ag, MatchResult.home_win
    elif allows_draw and r < p_home + p_draw:
        g = _rng.choices([0, 1, 2, 3], weights=[20, 40, 30, 10])[0]
        return g, g, MatchResult.draw
    else:
        ag = _rng.choices([1, 2, 3, 4], weights=[30, 40, 20, 10])[0]
        hg = _rng.choices([0, 1, 2], weights=[40, 40, 20])[0]
        if ag <= hg:
            ag = hg + 1
        return hg, ag, MatchResult.away_win


async def _update_team_stats(db, team_id: int, season_id: int,
                              is_home: bool, hg: int, ag: int, result: MatchResult):
    r = await db.execute(
        select(TeamStatistics).where(
            and_(TeamStatistics.team_id == team_id, TeamStatistics.season_id == season_id)
        )
    )
    ts = r.scalar_one_or_none()
    if ts is None:
        ts = TeamStatistics(team_id=team_id, season_id=season_id,
                            matches_played=0, wins=0, draws=0, losses=0,
                            goals_for=0, goals_against=0, points=0, form_last5=[])
        db.add(ts)

    ts.matches_played = (ts.matches_played or 0) + 1
    gf = hg if is_home else ag
    ga = ag if is_home else hg
    ts.goals_for = (ts.goals_for or 0) + gf
    ts.goals_against = (ts.goals_against or 0) + ga

    if result == MatchResult.draw:
        ts.draws = (ts.draws or 0) + 1
        ts.points = (ts.points or 0) + 1
        letter = "D"
    elif (result == MatchResult.home_win and is_home) or \
         (result == MatchResult.away_win and not is_home):
        ts.wins = (ts.wins or 0) + 1
        ts.points = (ts.points or 0) + 3
        letter = "W"
    else:
        ts.losses = (ts.losses or 0) + 1
        letter = "L"

    form = list(ts.form_last5 or [])
    form.append(letter)
    ts.form_last5 = form[-5:]


async def _update_h2h(db, home_id: int, away_id: int, result: MatchResult):
    r = await db.execute(
        select(HeadToHead).where(
            or_(
                and_(HeadToHead.team1_id == home_id, HeadToHead.team2_id == away_id),
                and_(HeadToHead.team1_id == away_id, HeadToHead.team2_id == home_id),
            )
        )
    )
    h2h = r.scalar_one_or_none()
    if h2h is None:
        h2h = HeadToHead(team1_id=home_id, team2_id=away_id,
                         total_matches=0, team1_wins=0, team2_wins=0, draws=0)
        db.add(h2h)

    h2h.total_matches = (h2h.total_matches or 0) + 1
    if result == MatchResult.draw:
        h2h.draws = (h2h.draws or 0) + 1
    elif result == MatchResult.home_win:
        if h2h.team1_id == home_id:
            h2h.team1_wins = (h2h.team1_wins or 0) + 1
        else:
            h2h.team2_wins = (h2h.team2_wins or 0) + 1
    else:  # away_win
        if h2h.team1_id == away_id:
            h2h.team1_wins = (h2h.team1_wins or 0) + 1
        else:
            h2h.team2_wins = (h2h.team2_wins or 0) + 1


async def complete_past_matches(batch: int = 50) -> int:
    """Simulate results for scheduled matches whose date is in the past."""
    async with async_session() as db:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        r = await db.execute(
            select(Match)
            .options(selectinload(Match.sport))
            .where(
                and_(Match.status == MatchStatus.scheduled, Match.match_date <= now)
            ).order_by(Match.match_date).limit(batch)
        )
        matches = r.scalars().all()
        if not matches:
            return 0

        for match in matches:
            # Get current-season PPG for each team
            home_r = await db.execute(
                select(TeamStatistics).where(
                    and_(TeamStatistics.team_id == match.home_team_id,
                         TeamStatistics.season_id == match.season_id)
                )
            )
            away_r = await db.execute(
                select(TeamStatistics).where(
                    and_(TeamStatistics.team_id == match.away_team_id,
                         TeamStatistics.season_id == match.season_id)
                )
            )
            hts = home_r.scalar_one_or_none()
            ats = away_r.scalar_one_or_none()
            home_ppg = (hts.points / hts.matches_played) if (hts and hts.matches_played) else 1.2
            away_ppg = (ats.points / ats.matches_played) if (ats and ats.matches_played) else 1.0

            sport_profile = get_sport_profile(match.sport.name if match.sport else None)
            hg, ag, result = _simulate_result(home_ppg, away_ppg, allows_draw=sport_profile.allows_draw)
            match.home_score = hg
            match.away_score = ag
            match.result = result
            match.status = MatchStatus.completed

            await _update_team_stats(db, match.home_team_id, match.season_id, True, hg, ag, result)
            await _update_team_stats(db, match.away_team_id, match.season_id, False, hg, ag, result)
            await _update_h2h(db, match.home_team_id, match.away_team_id, result)

            # Mark predictions for this match as correct or incorrect
            preds_r = await db.execute(
                select(Prediction).where(Prediction.match_id == match.id)
            )
            for pred in preds_r.scalars().all():
                pred.is_correct = (pred.predicted_result == result)

        await db.commit()
        return len(matches)


async def run_background_loop():
    """Periodically complete any newly-past scheduled matches (every 60 s)."""
    while True:
        try:
            count = await complete_past_matches()
            if count:
                print(f"[BG] Auto-completed {count} scheduled matches")
        except Exception as exc:
            print(f"[BG] Error: {exc}")
        await asyncio.sleep(60)


async def run_esports_import_retry_loop(initial_delay: int = 45, max_delay: int = 1800):
    """Retry real esports import with exponential backoff until provider limits clear."""
    delay = max(10, initial_delay)

    while True:
        sleep_for = delay
        try:
            async with async_session() as db:
                from app.services.real_data_importer import import_esports_data

                summary = await import_esports_data(db)

            added = int(summary.get("new_matches_added", 0))
            total = int(summary.get("matches", 0))
            errors = ((summary.get("quality") or {}).get("provider_errors") or [])

            if total > 0 and not errors:
                # Healthy state: keep refreshing but less aggressively.
                delay = max(300, initial_delay)
                sleep_for = delay
            elif added > 0:
                # Made progress, try again soon.
                delay = max(10, initial_delay)
                sleep_for = delay
            else:
                # No progress, back off exponentially.
                sleep_for = delay
                delay = min(max_delay, int(delay * 1.8))

            print(
                "[BG-Esports] "
                f"matches={total} new={added} errors={len(errors)} next_retry={sleep_for}s"
            )
        except Exception as exc:
            print(f"[BG-Esports] Error: {exc}")
            sleep_for = delay
            delay = min(max_delay, int(delay * 1.8))

        await asyncio.sleep(sleep_for)


async def run_model_retrain_loop(interval_seconds: int = 86400, min_samples: int = 30):
    """Periodically retrain best model per sport to keep models fresh."""
    from app.services.model_training import train_best_models_per_sport

    delay = max(60, interval_seconds)
    while True:
        try:
            async with async_session() as db:
                summary = await train_best_models_per_sport(
                    db,
                    min_samples=max(10, min_samples),
                    seed=42,
                    train_ratio=0.8,
                )

            print(
                "[BG-Retrain] "
                f"trained={summary.get('sports_trained', 0)} "
                f"skipped={summary.get('sports_skipped', 0)} "
                f"failed={summary.get('sports_failed', 0)} "
                f"next_retry={delay}s"
            )
        except Exception as exc:
            print(f"[BG-Retrain] Error: {exc}")

        await asyncio.sleep(delay)
