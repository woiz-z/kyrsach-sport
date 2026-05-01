"""Streaming live match analysis using Gemini.

Produces a short, punchy Ukrainian-language commentary when a new in-game
event is detected (goal, card, etc.), streaming tokens one by one so the
frontend can display them as they arrive.
"""
from __future__ import annotations

import sys
from typing import AsyncIterator

from openai import AsyncOpenAI

from app.config import get_settings
from app.ai.sport_profiles import get_sport_profile


async def stream_live_analysis(
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    minute: int | None,
    recent_events: list,
    prediction: dict,
    sport_name: str | None = None,
) -> AsyncIterator[str]:
    """Yield text tokens for a live match commentary (OpenRouter primary, Gemini fallback)."""
    settings = get_settings()
    if not (settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip()) and \
       not (settings.GOOGLE_API_KEY and settings.GOOGLE_API_KEY.strip()):
        return

    profile = get_sport_profile(sport_name)

    # ── Recent events summary ───────────────────────────────────────────────
    EMOJI = {
        "goal":          "⚽",
        "own_goal":      "🥅",
        "yellow_card":   "🟨",
        "red_card":      "🟥",
        "yellow_red_card": "🟧",
        "substitution":  "🔄",
        "assist":        "🎯",
    }
    event_lines = []
    for ev in (recent_events or [])[-10:]:
        minute_str = f"{ev.get('minute')}':" if ev.get("minute") else ""
        etype = ev.get("event_type", "event")
        detail = ev.get("detail") or etype.replace("_", " ").title()
        emoji = EMOJI.get(etype, "•")
        event_lines.append(f"  {emoji} {minute_str} {detail}")
    events_text = "\n".join(event_lines) if event_lines else "  — Подій ще немає"

    minute_text = f"{minute}'" if minute else "Початок матчу"

    if profile.allows_draw:
        probs_text = (
            f"- {profile.home_label}: {prediction.get('home_win_prob', 0) * 100:.1f}%\n"
            f"- Нічия: {prediction.get('draw_prob', 0) * 100:.1f}%\n"
            f"- {profile.away_label}: {prediction.get('away_win_prob', 0) * 100:.1f}%"
        )
    else:
        probs_text = (
            f"- {profile.home_label}: {prediction.get('home_win_prob', 0) * 100:.1f}%\n"
            f"- {profile.away_label}: {prediction.get('away_win_prob', 0) * 100:.1f}%"
        )

    prompt = f"""Ти — живий спортивний коментатор та аналітик. Матч ЗАРАЗ ЙДЕ.

## {profile.display_name}: {home_team} vs {away_team}
Рахунок: **{home_score}:{away_score}** (хвилина: {minute_text})

## Події матчу:
{events_text}

## Оновлений AI-прогноз:
{probs_text}
- Впевненість: {prediction.get('confidence', 0) * 100:.1f}%

Надай КОРОТКИЙ живий аналіз (80-120 слів) українською мовою у такому форматі:
1. **Подія** — прокоментуй найсвіжішу подію
2. **Динаміка** — як змінився перебіг матчу
3. **Прогноз** — що очікуємо до фінального свистка

Пиши живо й динамічно, як справжній стадіонний коментатор!"""

    if settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip():
        api_key = settings.OPENROUTER_API_KEY
        base_url = settings.OPENROUTER_BASE_URL
        extra_headers = {
            "HTTP-Referer": "https://sportpredict.app",
            "X-Title": "SportPredict Live Analysis",
        }
        # Fallback chain: primary → alternates
        # Note: Gemma models via Google AI Studio don't support system role
        # Use openrouter "transforms" to let OR handle prompt conversion
        primary = settings.OPENROUTER_LIVE_MODEL or "meta-llama/llama-3.3-70b-instruct:free"
        fallback_models = [
            primary,
            "openai/gpt-oss-20b:free",
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "google/gemma-3-12b-it:free",
            "google/gemma-3-4b-it:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
        ]
        # deduplicate while preserving order
        seen: set = set()
        models_to_try = [m for m in fallback_models if not (m in seen or seen.add(m))]  # type: ignore[func-returns-value]
    elif settings.GOOGLE_API_KEY and settings.GOOGLE_API_KEY.strip():
        api_key = settings.GOOGLE_API_KEY
        base_url = settings.GEMINI_BASE_URL
        extra_headers = {}
        models_to_try = [settings.GEMINI_MODEL]
    else:
        print("[Live Analyzer] No LLM API key configured — skipping", file=sys.stderr)
        return

    system_instruction = "Ти — живий спортивний коментатор. Відповідай виключно українською. Будь лаконічним і динамічним."
    # Some providers (e.g. Google AI Studio via OR) don't support system role;
    # we always use single user message to maximise compatibility.
    combined_prompt = f"{system_instruction}\n\n{prompt}"
    messages = [{"role": "user", "content": combined_prompt}]

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    for model in models_to_try:
        print(f"[Live Analyzer] Trying model: {model}", file=sys.stderr)
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                extra_headers=extra_headers,
                temperature=0.8,
                max_tokens=350,
                stream=True,
            )
            token_count = 0
            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    token_count += 1
                    yield delta
            if token_count > 0:
                print(f"[Live Analyzer] Success with {model} ({token_count} tokens)", file=sys.stderr)
                return
            # no tokens yielded — try next model
            print(f"[Live Analyzer] {model} yielded no tokens, trying next", file=sys.stderr)
        except Exception as exc:
            print(f"[Live Analyzer] {model} error: {exc}", file=sys.stderr)
            # continue to next model
    print("[Live Analyzer] All models exhausted", file=sys.stderr)
