from __future__ import annotations

import asyncio
import json
import logging
from functools import lru_cache
from typing import Optional
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_USER_AGENT = "SportPredictAI/1.0"
_SEARCH_LIMIT = 5
_SPORT_KEYWORDS = {
    "soccer": ("football", "soccer"),
    "basketball": ("basketball", "nba"),
    "hockey": ("ice hockey", "hockey", "nhl"),
    "tennis": ("tennis",),
}


def _http_get_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": _USER_AGENT})
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _score_candidate(candidate: dict, team_name: str, sport_hint: str) -> int:
    score = 0
    label = (candidate.get("label") or "").lower()
    description = (candidate.get("description") or "").lower()

    if label:
        score += 2

    if team_name:
        lowered_team = team_name.lower()
        if lowered_team in description:
            score += 4

    for keyword in _SPORT_KEYWORDS.get((sport_hint or "").lower(), ()): 
        if keyword in description:
            score += 3

    return score


def _extract_commons_image_filename(entity_id: str) -> Optional[str]:
    data = _http_get_json(
        f"https://www.wikidata.org/wiki/Special:EntityData/{quote(entity_id)}.json"
    )
    entity = (data.get("entities") or {}).get(entity_id) or {}
    claims = entity.get("claims") or {}
    image_claims = claims.get("P18") or []
    if not image_claims:
        return None

    try:
        return image_claims[0]["mainsnak"]["datavalue"]["value"]
    except (KeyError, IndexError, TypeError):
        return None


@lru_cache(maxsize=2048)
def _lookup_player_avatar_sync(player_name: str, team_name: str, sport_hint: str) -> Optional[str]:
    if not player_name:
        return None

    queries = [f"{player_name} {team_name}".strip()]
    if team_name:
        queries.append(player_name)

    for query in queries:
        url = (
            "https://www.wikidata.org/w/api.php"
            f"?action=wbsearchentities&search={quote(query)}&language=en&format=json&limit={_SEARCH_LIMIT}"
        )

        try:
            search_data = _http_get_json(url)
        except Exception as exc:
            logger.debug("Wikidata avatar search failed for %s: %s", player_name, exc)
            continue

        candidates = sorted(
            search_data.get("search") or [],
            key=lambda item: _score_candidate(item, team_name, sport_hint),
            reverse=True,
        )
        for candidate in candidates:
            entity_id = candidate.get("id")
            if not entity_id:
                continue

            try:
                image_name = _extract_commons_image_filename(entity_id)
            except Exception as exc:
                logger.debug("Wikidata entity lookup failed for %s (%s): %s", player_name, entity_id, exc)
                continue

            if image_name:
                return f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{quote(image_name)}?width=512"

    return None


async def fetch_external_player_photo_url(
    player_name: str,
    team_name: str = "",
    sport_hint: str = "",
) -> Optional[str]:
    return await asyncio.to_thread(_lookup_player_avatar_sync, player_name, team_name, sport_hint)