"""
Fast ESPN CDN photo prefetch - downloads player headshots from ESPN CDN directly.
Runs inside backend container:
  python /app/scripts/prefetch_espn_photos.py
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

import httpx
from sqlalchemy import text
from app.database import async_session

CACHE_DIR = Path(os.environ.get("AVATAR_CACHE_DIR", "/var/cache/sportpredict/avatars"))
UA = "SportPredictAI/1.0"
CONCURRENCY = 20  # parallel downloads


def already_cached(player_id: int) -> bool:
    for ext in ("jpg", "png"):
        if (CACHE_DIR / f"p{player_id}.{ext}").exists():
            return True
    return False


async def download_photo(client: httpx.AsyncClient, player_id: int, url: str, sem: asyncio.Semaphore) -> str:
    """Download photo and save to cache. Returns status string."""
    if already_cached(player_id):
        return "cached"

    async with sem:
        try:
            resp = await client.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.content
                if len(data) > 1000:
                    ext = "jpg" if data[:3] == b"\xff\xd8\xff" else "png"
                    dest = CACHE_DIR / f"p{player_id}.{ext}"
                    dest.write_bytes(data)
                    return "ok"
                return "small"
            elif resp.status_code == 404:
                return "404"
            else:
                return f"http_{resp.status_code}"
        except httpx.TimeoutException:
            return "timeout"
        except Exception as e:
            return f"err_{type(e).__name__}"


async def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_session() as db:
        rows = await db.execute(text("""
            SELECT p.id, p.photo_url, p.espn_id, sp.name as sport
            FROM players p
            JOIN teams t ON t.id = p.team_id
            JOIN sports sp ON sp.id = t.sport_id
            WHERE p.photo_url IS NOT NULL AND p.photo_url != ''
            ORDER BY p.id
        """))
        players = rows.fetchall()

    logger.info("Total players with photo_url: %d", len(players))
    to_download = [(pid, url) for pid, url, eid, sport in players if not already_cached(pid)]
    logger.info("Need to download: %d (already cached: %d)", len(to_download), len(players) - len(to_download))

    if not to_download:
        logger.info("All photos already cached!")
        return

    sem = asyncio.Semaphore(CONCURRENCY)
    ok = skip = fail = notfound = 0

    async with httpx.AsyncClient(headers={"User-Agent": UA}, follow_redirects=True) as client:
        tasks = [download_photo(client, pid, url, sem) for pid, url in to_download]
        total = len(tasks)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, (pid, url), result in zip(range(total), to_download, results):
            if isinstance(result, Exception):
                fail += 1
            elif result == "ok":
                ok += 1
            elif result == "404":
                notfound += 1
            elif result in ("cached",):
                skip += 1
            else:
                fail += 1

            if (i + 1) % 100 == 0 or (i + 1) == total:
                logger.info("Progress: %d/%d | ok=%d 404=%d fail=%d", i+1, total, ok, notfound, fail)

    logger.info("=== DONE: ok=%d, 404=%d, fail=%d ===", ok, notfound, fail)


if __name__ == "__main__":
    asyncio.run(main())
