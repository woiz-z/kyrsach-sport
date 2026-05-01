import asyncio
import asyncpg
import httpx
import urllib.parse

async def main():
    conn = await asyncpg.connect(
        host='db', port=5432,
        user='postgres', password='postgres', database='sports_predict'
    )
    
    missing_rows = await conn.fetch("""
        SELECT p.id, p.name FROM players p
        JOIN teams t ON t.id = p.team_id
        WHERE t.sport_id = (SELECT id FROM sports WHERE name='Хокей')
        AND p.espn_id IS NULL
    """)
    
    updated = 0
    not_found = []
    async with httpx.AsyncClient(timeout=10) as client:
        for row in missing_rows:
            name = row['name']
            pid = row['id']
            query = urllib.parse.quote(name)
            url = f"https://site.api.espn.com/apis/common/v3/search?query={query}&sport=hockey&lang=en&region=us&type=player&limit=3"
            try:
                r = await client.get(url)
                data = r.json()
                items = data.get('items', [])
                if items:
                    a = items[0]
                    espn_id = str(a.get('id', ''))
                    display = a.get('displayName', '')
                    photo = f"https://a.espncdn.com/i/headshots/nhl/players/full/{espn_id}.png"
                    await conn.execute("""
                        UPDATE players SET espn_id=$1, photo_url=COALESCE(NULLIF(photo_url,''), $2)
                        WHERE id=$3
                    """, espn_id, photo, pid)
                    updated += 1
                    print(f"  Fixed: {name} -> {display} (ESPN {espn_id})")
                else:
                    not_found.append(name)
            except Exception as e:
                print(f"  Error for {name}: {e}")
                not_found.append(name)
    
    print(f"\nTotal updated: {updated}")
    if not_found:
        print(f"Not found ({len(not_found)}): {not_found[:10]}")
    remaining = await conn.fetchval("SELECT COUNT(*) FROM players WHERE espn_id IS NULL AND team_id IN (SELECT id FROM teams WHERE sport_id = (SELECT id FROM sports WHERE name='Хокей'))")
    print(f"Still missing hockey: {remaining}")
    await conn.close()

asyncio.run(main())
