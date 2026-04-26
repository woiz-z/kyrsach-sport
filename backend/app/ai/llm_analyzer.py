"""LLM-based match analysis using AsyncOpenAI-compatible providers."""
import asyncio
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
) -> str | None:
    """Generate a detailed Ukrainian-language match analysis using LLM."""
    settings = get_settings()
    
    # Debug: Check what we have
    has_groq = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip())
    has_openrouter = bool(settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip())
    
    print(f"[AI Analyzer] has_groq={has_groq}, has_openrouter={has_openrouter}", file=sys.stderr)

    # Try Groq first (most reliable), then OpenRouter as fallback
    if has_groq:
        api_key = settings.GROQ_API_KEY
        base_url = "https://api.groq.com/openai/v1"
        model = settings.GROQ_MODEL
        provider = "Groq"
    elif has_openrouter:
        api_key = settings.OPENROUTER_API_KEY
        base_url = settings.OPENROUTER_BASE_URL
        model = settings.OPENROUTER_MODEL
        provider = "OpenRouter"
    else:
        return None
    
    # Debug log
    print(f"[AI Analyzer] Using {provider} - Model: {model}", file=sys.stderr)

    profile = get_sport_profile(sport_name)

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

    prompt = f"""Ти — експерт-аналітик спортивних подій. Проаналізуй матч виду спорту "{profile.display_name}" та надай детальний прогноз українською мовою.

## Матч: {home_team} vs {away_team}

## Прогноз ML-моделі:
{outcomes_block}
- Впевненість моделі: {prediction.get('confidence', 0)*100:.1f}%

## Статистика {home_team} (господарі):
- Матчів зіграно: {home_stats.get('matches_played', 0)}
- Перемоги/Нічиї/Поразки: {home_stats.get('wins', 0)}/{home_stats.get('draws', 0)}/{home_stats.get('losses', 0)}
- Показник "{profile.score_metric}" забито/пропущено: {home_stats.get('goals_for', 0)}/{home_stats.get('goals_against', 0)}
- Очків: {home_stats.get('points', 0)}

## Статистика {away_team} (гості):
- Матчів зіграно: {away_stats.get('matches_played', 0)}
- Перемоги/Нічиї/Поразки: {away_stats.get('wins', 0)}/{away_stats.get('draws', 0)}/{away_stats.get('losses', 0)}
- Показник "{profile.score_metric}" забито/пропущено: {away_stats.get('goals_for', 0)}/{away_stats.get('goals_against', 0)}
- Очків: {away_stats.get('points', 0)}

## Очні зустрічі:
- Всього матчів: {h2h.get('total_matches', 0)}
- Перемог {home_team}: {h2h.get('team1_wins', 0)}
- Перемог {away_team}: {h2h.get('team2_wins', 0)}
{'- Нічиїх: ' + str(h2h.get('draws', 0)) if profile.allows_draw else '- Нічиї в цьому виді спорту не враховуються'}

Надай аналіз у такому форматі:
1. **Огляд матчу** — коротко про значимість матчу
2. **Аналіз сил** — порівняння команд
3. **Ключові фактори** — що вплине на результат
4. **Прогноз** — твоя експертна думка з обґрунтуванням
5. **Рахунок** — прогнозований рахунок матчу

Пиши професійно, але доступно. Обсяг: 150-250 слів."""

    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Ти — професійний спортивний аналітик. Відповідай виключно українською мовою."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1024,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[AI Analyzer] {provider} failed: {e}", file=sys.stderr)
        # If Groq failed and OpenRouter is available, try fallback
        if provider == "Groq" and has_openrouter:
            try:
                fallback_client = AsyncOpenAI(
                    api_key=settings.OPENROUTER_API_KEY,
                    base_url=settings.OPENROUTER_BASE_URL,
                )
                fallback_response = await fallback_client.chat.completions.create(
                    model=settings.OPENROUTER_MODEL,
                    messages=[
                        {"role": "system", "content": "Ти — професійний спортивний аналітик. Відповідай виключно українською мовою."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=1024,
                )
                return fallback_response.choices[0].message.content
            except Exception as e2:
                print(f"[AI Analyzer] OpenRouter fallback failed: {e2}", file=sys.stderr)
        return None
