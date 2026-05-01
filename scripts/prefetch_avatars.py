#!/usr/bin/env python3
"""
Bulk prefetch real player photos from Wikipedia/Wikidata into the Docker avatar cache.
Runs from the HOST machine (not Docker) — bypasses Docker's 403 block on Wikipedia.

Strategy: global semaphore limits concurrent HTTP requests (avoids Wikipedia 429),
sequential docker cp per player (cheap, parallel per worker).

Usage:
    python3 scripts/prefetch_avatars.py                   # all players
    python3 scripts/prefetch_avatars.py --team-id 66 154  # specific teams
    python3 scripts/prefetch_avatars.py --workers 4       # workers (default 3)
"""
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"

# Max concurrent HTTP requests across all workers (Wikipedia is sensitive to burst)
_http_sem = threading.Semaphore(2)
_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def get_players(team_ids: list[int] | None) -> list[tuple[int, str]]:
    if team_ids:
        ids_str = ",".join(str(i) for i in team_ids)
        where = f"WHERE p.team_id IN ({ids_str})"
    else:
        where = ""
    sql = f"SELECT p.id, p.name FROM players p {where} ORDER BY p.team_id, p.id;"
    result = subprocess.run(
        ["docker", "exec", "sports_predict_db", "psql", "-U", "postgres",
         "-d", "sports_predict", "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True, text=True,
    )
    players = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            try:
                players.append((int(parts[0]), parts[1]))
            except ValueError:
                pass
    return players


def get_cached_ids() -> set[int]:
    result = subprocess.run(
        ["docker", "exec", "sports_predict_backend", "sh", "-c",
         "ls /var/cache/sportpredict/avatars/ 2>/dev/null"],
        capture_output=True, text=True,
    )
    cached = set()
    for fname in result.stdout.strip().splitlines():
        if fname.startswith("p") and "." in fname:
            try:
                cached.add(int(fname[1:fname.rindex(".")]))
            except ValueError:
                pass
    return cached


def _fetch(url: str, timeout: int = 12, retries: int = 3) -> bytes | None:
    for attempt in range(retries):
        with _http_sem:
            try:
                req = Request(url, headers={"User-Agent": UA})
                with urlopen(req, timeout=timeout) as r:
                    data = r.read()
                time.sleep(0.3)  # polite delay after each request
                return data
            except Exception as e:
                if "429" in str(e):
                    wait = 8 * (attempt + 1)
                    time.sleep(wait)
                    continue
                return None
    return None


SPORT_KEYWORDS = (
    "football", "soccer", "basketball", "hockey", "tennis",
    "player", "athlete", "goalkeeper", "pitcher", "baseball",
    "rugby", "cricket", "swimmer", "cyclist", "golfer", "boxer",
    "sprinter", "midfielder", "defender", "forward", "striker",
)


def _wikipedia_photo_url(name: str) -> str | None:
    for suffix in [" footballer", " basketball player", " athlete", ""]:
        search_url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&list=search&srsearch={quote(name + suffix)}&srlimit=3&format=json"
        )
        data = _fetch(search_url)
        if not data:
            continue
        hits = json.loads(data).get("query", {}).get("search", [])
        for hit in hits[:3]:
            title = hit.get("title", "")
            summary_data = _fetch(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
            )
            if not summary_data:
                continue
            summary = json.loads(summary_data)
            desc = (summary.get("description") or "").lower()
            if not any(k in desc for k in SPORT_KEYWORDS):
                continue
            thumb = (summary.get("thumbnail") or {}).get("source")
            if thumb:
                return thumb
    return None


def _wikidata_photo_url(name: str) -> str | None:
    for query in [name + " footballer", name + " athlete", name]:
        url = (
            "https://www.wikidata.org/w/api.php"
            f"?action=wbsearchentities&search={quote(query)}&language=en&format=json&limit=3"
        )
        data = _fetch(url, timeout=15)
        if not data:
            continue
        for candidate in json.loads(data).get("search", []):
            eid = candidate.get("id")
            desc = (candidate.get("description") or "").lower()
            if not any(k in desc for k in SPORT_KEYWORDS):
                continue
            entity_data = _fetch(
                f"https://www.wikidata.org/wiki/Special:EntityData/{quote(eid)}.json",
                timeout=15,
            )
            if not entity_data:
                continue
            entity = json.loads(entity_data).get("entities", {}).get(eid, {})
            p18 = (entity.get("claims") or {}).get("P18", [])
            if p18:
                fname = p18[0]["mainsnak"]["datavalue"]["value"]
                return (
                    "https://commons.wikimedia.org/wiki/Special:Redirect/file/"
                    f"{quote(fname)}?width=512"
                )
    return None


def copy_to_container(local_path: Path) -> None:
    dest = f"sports_predict_backend:/var/cache/sportpredict/avatars/{local_path.name}"
    subprocess.check_call(["docker", "cp", str(local_path), dest],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


CACHE_DIR = Path("/tmp/avatar_prefetch")


def process_player(pid: int, name: str) -> str:
    img_url = _wikipedia_photo_url(name)
    source = "Wiki"
    if not img_url:
        img_url = _wikidata_photo_url(name)
        source = "Wikidata"
    if not img_url:
        return f"MISS  {name} (id={pid})"

    img_bytes = _fetch(img_url, timeout=15)
    if not img_bytes or len(img_bytes) < 1000:
        return f"FAIL  {name} (id={pid})"

    ext = "jpg" if img_bytes[:3] == b"\xff\xd8\xff" else "png"
    out = CACHE_DIR / f"p{pid}.{ext}"
    out.write_bytes(img_bytes)
    try:
        copy_to_container(out)
    except Exception as e:
        return f"COPY_ERR  {name} (id={pid}): {e}"

    return f"OK [{source}] {name} (id={pid}) — {len(img_bytes)//1024}KB"


def main():
    args = sys.argv[1:]
    team_ids = None
    workers = 3

    if "--team-id" in args:
        idx = args.index("--team-id")
        team_ids = []
        for a in args[idx + 1:]:
            if a.startswith("--"):
                break
            try:
                team_ids.append(int(a))
            except ValueError:
                pass

    if "--workers" in args:
        idx = args.index("--workers")
        if idx + 1 < len(args):
            try:
                workers = int(args[idx + 1])
            except ValueError:
                pass

    players = get_players(team_ids)
    if not players:
        print("No players found.")
        sys.exit(1)

    cached_ids = get_cached_ids()
    player_ids = {p[0] for p in players}
    already = len(cached_ids & player_ids)
    to_fetch = [(pid, name) for pid, name in players if pid not in cached_ids]

    label = f"team(s) {team_ids}" if team_ids else "all teams"
    print(f"Players: {len(players)} | Cached: {already} | To fetch: {len(to_fetch)} | Workers: {workers} | HTTP concurrency: 2")
    print(f"Scope: {label}")
    print("─" * 60)

    if not to_fetch:
        print("All players already cached!")
        return

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    done = 0
    found = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_player, pid, name): (pid, name)
                   for pid, name in to_fetch}
        for future in as_completed(futures):
            result = future.result()
            done += 1
            if result.startswith("OK"):
                found += 1
            log(f"[{done}/{len(to_fetch)}] {result}")
            if done % 50 == 0:
                elapsed = time.time() - start
                rate = done / elapsed
                remaining = (len(to_fetch) - done) / rate if rate > 0 else 0
                log(f"  ── {found} photos fetched | {done/elapsed:.2f}/s | ~{remaining/60:.1f} min left")

    elapsed = time.time() - start
    print("─" * 60)
    print(f"Done in {elapsed/60:.1f} min. {found}/{len(to_fetch)} photos fetched.")


if __name__ == "__main__":
    main()
