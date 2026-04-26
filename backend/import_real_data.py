"""CLI: import real UPL data into DB (optionally wiping existing data)."""
import argparse
import asyncio

from app.database import async_session
from app.services.real_data_importer import import_real_data


async def main(reset: bool):
    async with async_session() as db:
        result = await import_real_data(db, reset_existing=reset)
    print("\n✅ Real data import completed")
    for k, v in result.items():
        print(f"   {k}: {v}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Wipe existing sports data before import")
    args = parser.parse_args()
    asyncio.run(main(args.reset))
