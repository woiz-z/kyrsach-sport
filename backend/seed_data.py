"""CLI for initializing DB with real data only (no synthetic seeding)."""

import argparse
import asyncio

from app.database import async_session
from app.services.football_data_scraper import import_from_football_data
from app.services.real_data_importer import import_real_data


async def seed_real_data(source: str, reset: bool, min_season_code: int, max_links: int) -> None:
    async with async_session() as db:
        summary = {}

        if source in {"realdb", "both"}:
            summary["realdb"] = await import_real_data(db, reset_existing=reset)

        if source in {"openfootball", "both"}:
            summary["openfootball"] = await import_from_football_data(
                db,
                reset_existing=reset and source == "openfootball",
                min_season_code=min_season_code,
                max_links=max_links,
            )

    print("\nReal data import completed")
    for key, value in summary.items():
        print(f"[{key}] {value}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize database using only real sports data")
    parser.add_argument(
        "--source",
        choices=["realdb", "openfootball", "both"],
        default="both",
        help="Data source: TheSportsDB (realdb), openfootball, or both",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe existing imported data before loading real data",
    )
    parser.add_argument(
        "--min-season-code",
        type=int,
        default=2324,
        help="Minimum openfootball season code (e.g. 2324 = 2023/24)",
    )
    parser.add_argument(
        "--max-links",
        type=int,
        default=0,
        help="Limit openfootball source files (0 = no limit)",
    )
    args = parser.parse_args()

    asyncio.run(
        seed_real_data(
            source=args.source,
            reset=args.reset,
            min_season_code=args.min_season_code,
            max_links=args.max_links,
        )
    )
