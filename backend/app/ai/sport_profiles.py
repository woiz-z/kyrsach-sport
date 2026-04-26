"""Sport-specific prediction profiles and outcome behavior."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SportProfile:
    key: str
    display_name: str
    icon: str
    allows_draw: bool
    home_label: str
    away_label: str
    score_metric: str


SPORT_PROFILES: dict[str, SportProfile] = {
    "football": SportProfile(
        key="football",
        display_name="Футбол",
        icon="⚽",
        allows_draw=True,
        home_label="Перемога господарів",
        away_label="Перемога гостей",
        score_metric="голи",
    ),
    "basketball": SportProfile(
        key="basketball",
        display_name="Баскетбол",
        icon="🏀",
        allows_draw=False,
        home_label="Перемога господарів",
        away_label="Перемога гостей",
        score_metric="очки",
    ),
    "tennis": SportProfile(
        key="tennis",
        display_name="Теніс",
        icon="🎾",
        allows_draw=False,
        home_label="Перемога гравця 1",
        away_label="Перемога гравця 2",
        score_metric="гейми",
    ),
    "hockey": SportProfile(
        key="hockey",
        display_name="Хокей",
        icon="🏒",
        allows_draw=False,
        home_label="Перемога господарів",
        away_label="Перемога гостей",
        score_metric="шайби",
    ),
    "volleyball": SportProfile(
        key="volleyball",
        display_name="Волейбол",
        icon="🏐",
        allows_draw=False,
        home_label="Перемога господарів",
        away_label="Перемога гостей",
        score_metric="сети",
    ),
    "esports": SportProfile(
        key="esports",
        display_name="Кіберспорт",
        icon="🎮",
        allows_draw=False,
        home_label="Перемога команди 1",
        away_label="Перемога команди 2",
        score_metric="мапи",
    ),
}


SPORT_ALIASES = {
    "футбол": "football",
    "football": "football",
    "баскетбол": "basketball",
    "basketball": "basketball",
    "теніс": "tennis",
    "теннис": "tennis",
    "tennis": "tennis",
    "хокей": "hockey",
    "hockey": "hockey",
    "волейбол": "volleyball",
    "volleyball": "volleyball",
    "кіберспорт": "esports",
    "киберспорт": "esports",
    "esports": "esports",
}


def resolve_sport_key(raw_name: str | None) -> str:
    if not raw_name:
        return "football"
    key = SPORT_ALIASES.get(raw_name.strip().lower())
    return key or "football"


def get_sport_profile(raw_name: str | None) -> SportProfile:
    return SPORT_PROFILES[resolve_sport_key(raw_name)]
