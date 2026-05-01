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


async def run_data_refresh_loop(interval_seconds: int = 600):
    """Refresh recent match data from ESPN every ~10 minutes."""
    from app.services.mega_scraper import refresh_recent_data, enrich_pending_matches

    # Initial delay to let startup import finish first
    await asyncio.sleep(10)

    while True:
        try:
            async with async_session() as db:
                result = await refresh_recent_data(db)
                print(f"[BG-Refresh] new={result.get('new_matches_added', 0)} sports={result.get('sports_refreshed', 0)}")
        except Exception as exc:
            print(f"[BG-Refresh] Error: {exc}")

        try:
            async with async_session() as db:
                enriched = await enrich_pending_matches(db, limit=20)
                if enriched:
                    print(f"[BG-Enrich] Enriched {enriched} matches")
        except Exception as exc:
            print(f"[BG-Enrich] Error: {exc}")

        try:
            from app.services.esports_scraper import refresh_esports
            async with async_session() as db:
                result = await refresh_esports(db)
                print(f"[BG-Esports] new={result.get('new_matches', 0)} skipped={result.get('skipped', 0)}")
        except Exception as exc:
            print(f"[BG-Esports] Error: {exc}")

        await asyncio.sleep(interval_seconds)


async def run_news_refresh_loop(interval_seconds: int = 3600):
    """
    Refresh news for upcoming matches and leagues.
    Runs every hour; league news is refreshed every 4 hours.
    """
    from app.services.news_scraper import refresh_upcoming_matches_news, refresh_all_seasons_news

    # Initial delay — let the ESPN import finish first
    await asyncio.sleep(90)

    run_count = 0
    while True:
        try:
            async with async_session() as db:
                result = await refresh_upcoming_matches_news(db, days_ahead=7)
                print(f"[News] Match news: {result}")
        except Exception as exc:
            print(f"[News] Match news error: {exc}")

        # Refresh league/season news every 4 hours
        if run_count % 4 == 0:
            try:
                async with async_session() as db:
                    result = await refresh_all_seasons_news(db)
                    print(f"[News] Season news: {result}")
            except Exception as exc:
                print(f"[News] Season news error: {exc}")

        run_count += 1
        await asyncio.sleep(interval_seconds)

