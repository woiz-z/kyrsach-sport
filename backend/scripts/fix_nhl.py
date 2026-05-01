import asyncio
import asyncpg
import httpx

async def main():
    conn = await asyncpg.connect(
        host='db', port=5432,
        user='postgres', password='postgres', database='sports_predict'
    )
    
    teams = await conn.fetch("""
        SELECT DISTINCT t.id, t.name, t.espn_id FROM teams t
        JOIN players p ON p.team_id = t.id
        WHERE t.sport_id = (SELECT id FROM sports WHERE name='Хокей')
        AND p.espn_id IS NULL
    """)
    
    missing = {}
    rows = await conn.fetch("""
        SELECT p.id, p.name, p.team_id FROM players p
        JOIN teams t ON t.id = p.team_id
        WHERE t.sport_id = (SELECT id FROM sports WHERE name='Хокей')
        AND p.espn_id IS NULL
    """)
    for row in rows:
        missing[(row['name'].lower(), row['team_id'])] = row['id']
    
    updated = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for team in teams:
            url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams/{team['espn_id']}/roster"
            try:
                r = await client.get(url)
                data = r.json()
                raw = data.get('athletes', [])
                if raw and isinstance(raw[0], dict) and 'items' in raw[0]:
                    flat = []
                    for g in raw: flat.extend(g.get('items', []))
                    raw = flat
                for a in raw:
                    name = a.get('displayName', '')
                    espn_id = str(a.get('id', ''))
                    photo = f"https://a.espncdn.com/i/headshots/nhl/players/full/{espn_id}.png" if espn_id else None
                    key = (name.lower(), team['id'])
                    if key in missing:
                        pid = missing[key]
                        await conn.execute("""
                            UPDATE players SET espn_id=$1, photo_url=COALESCE(NULLIF(photo_url,''), $2)
                            WHERE id=$3
                        """, espn_id, photo, pid)
                        updated += 1
                        print(f"  Fixed: {name} (ID {pid}) -> ESPN {espn_id}")
            except Exception as e:
                print(f"  Error for {team['name']}: {e}")
    
    print(f"\nTotal updated: {updated}")
    remaining = await conn.fetchval("SELECT COUNT(*) FROM players WHERE espn_id IS NULL AND team_id IN (SELECT id FROM teams WHERE sport_id = (SELECT id FROM sports WHERE name='Хокей'))")
    print(f"Still missing hockey: {remaining}")
    await conn.close()

asyncio.run(main())
