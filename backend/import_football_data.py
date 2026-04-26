"""CLI to import football-data.co.uk datasets into project DB."""
import argparse
import asyncio

from app.database import async_session
from app.services.football_data_scraper import import_from_football_data


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--no-reset", action="store_true", help="Do not wipe existing sports data")
    p.add_argument("--min-season", type=int, default=2324, help="Min season code, e.g. 2324")
    p.add_argument("--max-links", type=int, default=0, help="Limit number of CSV links (0 = all)")
    p.add_argument("--leagues", type=str, default="", help="Comma-separated league codes, e.g. E0,SP1,D1")
    return p.parse_args()


async def main():
    args = parse_args()
    leagues = [x.strip().upper() for x in args.leagues.split(",") if x.strip()]

    async with async_session() as db:
        result = await import_from_football_data(
            db,
            reset_existing=not args.no_reset,
            min_season_code=args.min_season,
            max_links=args.max_links,
            league_codes=leagues or None,
        )

    print("\n✅ football-data import completed")
    print(f"   links_found: {result.links_found}")
    print(f"   links_used: {result.links_used}")
    print(f"   teams: {result.teams}")
    print(f"   seasons: {result.seasons}")
    print(f"   matches_total: {result.matches_total}")
    print(f"   matches_completed: {result.matches_completed}")
    print(f"   matches_scheduled: {result.matches_scheduled}")
    print(f"   new_matches_added: {result.new_matches_added}")


if __name__ == "__main__":
    asyncio.run(main())
