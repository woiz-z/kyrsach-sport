"""LLM-based match analysis — OpenRouter (primary) or Google Gemini (fallback)."""
import sys
from openai import AsyncOpenAI
from app.config import get_settings
from app.ai.sport_profiles import get_sport_profile


async def generate_match_analysis(
    home_team: str,
    away_team: str,
    prediction: dict,
    home_stats: dict,
    away_stats: dict,
    h2h: dict,
    sport_name: str | None = None,
    lineups: dict | None = None,
    match_events: list | None = None,
) -> str | None:
    """Generate a detailed Ukrainian-language match analysis using OpenRouter (or Gemini fallback)."""
    settings = get_settings()

    # Choose provider: OpenRouter (primary) or Gemini (fallback)
    if settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip():
        api_key = settings.OPENROUTER_API_KEY
        base_url = settings.OPENROUTER_BASE_URL
        model = settings.OPENROUTER_MODEL
        extra_headers = {
            "HTTP-Referer": "https://sportpredict.app",
            "X-Title": "SportPredict AI Analysis",
        }
        print(f"[AI Analyzer] OpenRouter — {model}", file=sys.stderr)
    elif settings.GOOGLE_API_KEY and settings.GOOGLE_API_KEY.strip():
        api_key = settings.GOOGLE_API_KEY
        base_url = settings.GEMINI_BASE_URL
        model = settings.GEMINI_MODEL
        extra_headers = {}
        print(f"[AI Analyzer] Gemini fallback — {model}", file=sys.stderr)
    else:
        print("[AI Analyzer] No LLM API key configured — skipping analysis", file=sys.stderr)
        return None

    profile = get_sport_profile(sport_name)

    # Calculate derived stats for richer analysis
    home_mp = home_stats.get("matches_played") or 0
    away_mp = away_stats.get("matches_played") or 0
    home_ppg = round((home_stats.get("points") or 0) / max(home_mp, 1), 2)
    away_ppg = round((away_stats.get("points") or 0) / max(away_mp, 1), 2)
    home_gf_pg = round((home_stats.get("goals_for") or 0) / max(home_mp, 1), 2)
    away_gf_pg = round((away_stats.get("goals_for") or 0) / max(away_mp, 1), 2)
    home_ga_pg = round((home_stats.get("goals_against") or 0) / max(home_mp, 1), 2)
    away_ga_pg = round((away_stats.get("goals_against") or 0) / max(away_mp, 1), 2)
    home_win_pct = round((home_stats.get("wins") or 0) / max(home_mp, 1) * 100, 1)
    away_win_pct = round((away_stats.get("wins") or 0) / max(away_mp, 1) * 100, 1)

    if profile.allows_draw:
        outcomes_block = (
            f"- {profile.home_label}: {prediction.get('home_win_prob', 0)*100:.1f}%\n"
            f"- Нічия: {prediction.get('draw_prob', 0)*100:.1f}%\n"
            f"- {profile.away_label}: {prediction.get('away_win_prob', 0)*100:.1f}%"
        )
    else:
        outcomes_block = (
            f"- {profile.home_label}: {prediction.get('home_win_prob', 0)*100:.1f}%\n"
            f"- {profile.away_label}: {prediction.get('away_win_prob', 0)*100:.1f}%"
        )

    # Build lineup section
    lineup_section = ""
    home_key_players = []
    away_key_players = []
    if lineups:
        home_starters = [p for p in (lineups.get("home") or []) if p.get("is_starter")]
        away_starters = [p for p in (lineups.get("away") or []) if p.get("is_starter")]
        if home_starters:
            home_key_players = [p["player_name"] for p in home_starters[:11]]
            lineup_section += f"\n\n## Стартовий склад {home_team} ({len(home_starters)} гравців):\n" + ", ".join(home_key_players)
        if away_starters:
            away_key_players = [p["player_name"] for p in away_starters[:11]]
            lineup_section += f"\n\n## Стартовий склад {away_team} ({len(away_starters)} гравців):\n" + ", ".join(away_key_players)

    # Build events section (for completed/live matches)
    events_section = ""
    if match_events:
        goal_events = [e for e in match_events if e.get("event_type") in ("goal", "own_goal")]
        card_events = [e for e in match_events if e.get("event_type") in ("yellow_card", "red_card")]
        if goal_events:
            goals_list = [
                f"  {e['minute']}' {e.get('detail', 'гол')}" if e.get("minute") else f"  {e.get('detail', 'гол')}"
                for e in goal_events
            ]
            events_section += "\n\n## Голи матчу:\n" + "\n".join(goals_list)
        if card_events:
            cards_list = [
                f"  {e['minute']}' {e['event_type'].replace('_', ' ')} — {e.get('detail', '')}"
                for e in card_events if e.get("minute")
            ]
            if cards_list:
                events_section += "\n\n## Картки:\n" + "\n".join(cards_list)

    prompt = f"""Ти — провідний спортивний аналітик. Проаналізуй матч виду спорту "{profile.display_name}" та надай розгорнутий, глибокий прогноз українською мовою.

## Матч: {home_team} vs {away_team}

## Ймовірності результату (розраховані на основі статистики):
{outcomes_block}
- Впевненість моделі: {prediction.get('confidence', 0)*100:.1f}%

## Статистика сезону — {home_team} (господарі):
- Матчів: {home_mp} | Перемоги: {home_stats.get('wins', 0)} | Нічиї: {home_stats.get('draws', 0)} | Поразки: {home_stats.get('losses', 0)}
- Очки: {home_stats.get('points', 0)} | Очків за матч: {home_ppg}
- Відсоток перемог: {home_win_pct}%
- {profile.score_metric} забито: {home_stats.get('goals_for', 0)} (в середньому {home_gf_pg} за матч)
- {profile.score_metric} пропущено: {home_stats.get('goals_against', 0)} (в середньому {home_ga_pg} за матч)
- Різниця: {(home_stats.get('goals_for') or 0) - (home_stats.get('goals_against') or 0):+d}

## Статистика сезону — {away_team} (гості):
- Матчів: {away_mp} | Перемоги: {away_stats.get('wins', 0)} | Нічиї: {away_stats.get('draws', 0)} | Поразки: {away_stats.get('losses', 0)}
- Очки: {away_stats.get('points', 0)} | Очків за матч: {away_ppg}
- Відсоток перемог: {away_win_pct}%
- {profile.score_metric} забито: {away_stats.get('goals_for', 0)} (в середньому {away_gf_pg} за матч)
- {profile.score_metric} пропущено: {away_stats.get('goals_against', 0)} (в середньому {away_ga_pg} за матч)
- Різниця: {(away_stats.get('goals_for') or 0) - (away_stats.get('goals_against') or 0):+d}

## Історія очних зустрічей:
- Всього матчів між командами: {h2h.get('total_matches', 0)}
- Перемог {home_team}: {h2h.get('team1_wins', 0)}
- Перемог {away_team}: {h2h.get('team2_wins', 0)}
{'- Нічиїх: ' + str(h2h.get('draws', 0)) if profile.allows_draw else ''}{lineup_section}{events_section}

Надай детальний аналіз у такому форматі:

### 🏟️ Огляд матчу
Коротко про значимість цього матчу, місце у турнірній таблиці, ставки для обох команд.

### 📊 Порівняння команд
Детальне порівняння поточної форми, атакуючих та оборонних показників. {'Аналіз заявлених складів та їх сильних сторін.' if lineup_section else 'Аналіз ключових статистичних показників.'}

### 🔑 Ключові фактори
3-4 конкретних фактори, які найбільше вплинуть на результат (домашня перевага, форма, атака vs оборона, очні зустрічі тощо).

### 🤖 Прогноз AI
Чітка рекомендація з детальним обґрунтуванням. Поясни, чому саме ця команда має перевагу або чому очікується рівна боротьба.

### ⚽ Прогнозований результат
Конкретний рахунок та варіант результату (наприклад: "Перемога {home_team} 2:1").

Пиши аналітично, конкретно та впевнено. Загальний обсяг: 350-500 слів. Виключно українською мовою."""

    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=extra_headers if extra_headers else None,
        )
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ти — провідний спортивний аналітик із 15-річним досвідом. "
                        "Твої аналізи відрізняються глибиною, конкретністю та обґрунтованістю. "
                        "Відповідай ВИКЛЮЧНО українською мовою. "
                        "Завжди давай конкретний прогноз, не уникай однозначних висновків."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.72,
            max_tokens=1500,
        )
        text = response.choices[0].message.content or ""
        # Strip markdown bold markers — frontend renders plain text
        text = text.replace("**", "").replace("__", "")
        return text
    except Exception as e:
        print(f"[AI Analyzer] {model} error: {e}", file=sys.stderr)
        return None
