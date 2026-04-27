"""
Seed demo predictions for all users so the system looks actively used.
Run with: railway run python seed_predictions.py
"""

import asyncio
import random
from datetime import datetime, timedelta

from sqlalchemy import select, func

from app.database import async_session
from app.models.models import User, Match, Prediction, MatchResult, MatchStatus

MODELS = [
    "gradient_boosting_sport_1",
    "gradient_boosting_sport_2",
    "gradient_boosting_sport_3",
    "logistic_regression_sport_1",
    "logistic_regression_sport_2",
    "gradient_boosting_sport_19",
]

AI_ANALYSES = [
    "Команда-господар демонструє стабільну форму протягом останніх 5 матчів. "
    "Статистика очних зустрічей та домашній фактор дають перевагу господарям. "
    "ML-модель виявила ключові патерни атакуючої гри та оборонної стійкості.",

    "Аналіз останніх 10 матчів обох команд вказує на рівне протистояння. "
    "Гравці гостей знаходяться в хорошій формі, проте виїзна статистика дещо слабша. "
    "Confidence-рівень прогнозу вищий за середній для цього класу матчів.",

    "Нічийний результат підтверджується рівністю ключових показників. "
    "Обидві команди мають схожий рейтинг атаки (xG ≈ 1.2) та оборони. "
    "Модель з вірогідністю 61% очікує розподіл очок.",

    "Гості мають значну перевагу у серії очних зустрічей (5В-1Н-2П). "
    "Форма за останній місяць: господарі — 3 поразки підряд, гості — 4 перемоги. "
    "Gradient Boosting модель дала highest-confidence сигнал для перемоги гостей.",

    "Ключовий матч сезону з яскраво вираженим фаворитом. "
    "Статистика xPoints вказує на 73% ймовірність перемоги господарів. "
    "Модель враховувала травми складу та умови поля.",

    "Рівна за силою зустріч з непередбачуваним результатом. "
    "Feature importance показав, що вирішальним є фактор мотивації: одна з команд "
    "бореться за виживання у лізі, що підвищує точність прогнозу.",
]


async def seed() -> None:
    async with async_session() as db:
        # ── users ──────────────────────────────────────────
        users = (await db.execute(select(User))).scalars().all()
        print(f"[seed] {len(users)} users found")

        # ── completed matches with real (non-TBD) teams ────
        matches_q = (
            select(Match)
            .where(Match.status == MatchStatus.completed)
            .where(Match.result.isnot(None))
            .order_by(func.random())
            .limit(60)
        )
        matches = (await db.execute(matches_q)).scalars().all()
        print(f"[seed] {len(matches)} completed matches available")

        if not matches:
            print("[seed] No completed matches found — aborting")
            return

        created = 0
        for user in users:
            sample_size = min(30, len(matches))
            for match in random.sample(matches, sample_size):
                # skip if already exists
                existing = (
                    await db.execute(
                        select(Prediction).where(
                            Prediction.match_id == match.id,
                            Prediction.user_id == user.id,
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    continue

                # ── decide predicted result ────────────────
                # 72% accuracy (correct most of the time)
                if random.random() < 0.72:
                    pred_result = match.result
                else:
                    others = [r for r in MatchResult if r != match.result]
                    pred_result = random.choice(others)

                is_correct = pred_result == match.result

                # ── realistic probability distribution ─────
                outcomes = [MatchResult.home_win, MatchResult.draw, MatchResult.away_win]
                raw = [random.uniform(0.08, 0.25) for _ in outcomes]
                winner_idx = outcomes.index(pred_result)
                raw[winner_idx] += random.uniform(0.25, 0.50)
                total = sum(raw)
                home_p, draw_p, away_p = [r / total for r in raw]
                confidence = max(home_p, draw_p, away_p) * random.uniform(0.82, 1.0)

                # ── random date within last 90 days ────────
                days_ago = random.randint(1, 90)
                hours_ago = random.randint(0, 23)
                created_at = datetime.utcnow() - timedelta(days=days_ago, hours=hours_ago)

                include_analysis = random.random() > 0.35
                pred = Prediction(
                    match_id=match.id,
                    user_id=user.id,
                    predicted_result=pred_result,
                    home_win_prob=round(home_p, 4),
                    draw_prob=round(draw_p, 4),
                    away_win_prob=round(away_p, 4),
                    confidence=round(confidence, 4),
                    model_name=random.choice(MODELS),
                    ai_analysis=random.choice(AI_ANALYSES) if include_analysis else None,
                    created_at=created_at,
                    is_correct=is_correct,
                )
                db.add(pred)
                created += 1

            # flush per user to avoid huge transaction
            await db.flush()
            print(f"  ✓ user {user.username}: predictions queued")

        await db.commit()
        print(f"\n[seed] Done — {created} predictions created.")


if __name__ == "__main__":
    asyncio.run(seed())
