import asyncio
import asyncpg
import httpx

async def main():
    conn = await asyncpg.connect(
        host='db', port=5432,
        user='postgres', password='postgres', database='sports_predict'
    )
    
    # Get all NBA teams
    teams = await conn.fetch("SELECT id, name, espn_id FROM teams WHERE sport_id = (SELECT id FROM sports WHERE name='Баскетбол')")
    
    # Build espn_id -> player_id lookup for players missing nationality
    rows = await conn.fetch("""
        SELECT p.id, p.espn_id FROM players p
        JOIN teams t ON t.id = p.team_id
        WHERE t.sport_id = (SELECT id FROM sports WHERE name='Баскетбол')
        AND (p.nationality IS NULL OR p.nationality = '') AND p.espn_id IS NOT NULL
    """)
    espn_to_pid = {r['espn_id']: r['id'] for r in rows}
    
    updated = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for team in teams:
            url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team['espn_id']}/roster"
            try:
                r = await client.get(url)
                data = r.json()
                raw = data.get('athletes', [])
                if raw and isinstance(raw[0], dict) and 'items' in raw[0]:
                    flat = []
                    for g in raw: flat.extend(g.get('items', []))
                    raw = flat
                for a in raw:
                    espn_id = str(a.get('id', ''))
                    if espn_id not in espn_to_pid:
                        continue
                    pid = espn_to_pid[espn_id]
                    # Get nationality from birthPlace.country
                    bp = a.get('birthPlace', {}) or {}
                    country = bp.get('country') or a.get('citizenship')
                    if country:
                        await conn.execute(
                            "UPDATE players SET nationality=$1 WHERE id=$2 AND (nationality IS NULL OR nationality='')",
                            country, pid
                        )
                        updated += 1
            except Exception as e:
                print(f"Error {team['name']}: {e}")
    
    # Same for NHL
    teams_nhl = await conn.fetch("SELECT id, name, espn_id FROM teams WHERE sport_id = (SELECT id FROM sports WHERE name='Хокей')")
    rows_nhl = await conn.fetch("""
        SELECT p.id, p.espn_id FROM players p
        JOIN teams t ON t.id = p.team_id
        WHERE t.sport_id = (SELECT id FROM sports WHERE name='Хокей')
        AND (p.nationality IS NULL OR p.nationality = '') AND p.espn_id IS NOT NULL
    """)
    espn_to_pid_nhl = {r['espn_id']: r['id'] for r in rows_nhl}
    
    async with httpx.AsyncClient(timeout=10) as client:
        for team in teams_nhl:
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
                    espn_id = str(a.get('id', ''))
                    if espn_id not in espn_to_pid_nhl:
                        continue
                    pid = espn_to_pid_nhl[espn_id]
                    bp = a.get('birthPlace', {}) or {}
                    country = bp.get('country') or a.get('citizenship')
                    if country:
                        await conn.execute(
                            "UPDATE players SET nationality=$1 WHERE id=$2 AND (nationality IS NULL OR nationality='')",
                            country, pid
                        )
                        updated += 1
            except Exception as e:
                print(f"Error {team['name']}: {e}")
    
    print(f"Nationalities updated: {updated}")
    
    # Final summary
    for sport in ['Баскетбол', 'Футбол', 'Хокей']:
        row = await conn.fetchrow(f"""
            SELECT COUNT(*) as total, 
                   COUNT(espn_id) as espn, 
                   COUNT(NULLIF(photo_url,'')) as photo,
                   COUNT(nationality) as nat,
                   COUNT(date_of_birth) as dob,
                   COUNT(height_cm) as height
            FROM players p JOIN teams t ON t.id = p.team_id
            JOIN sports sp ON sp.id = t.sport_id WHERE sp.name=$1
        """, sport)
        print(f"{sport}: {dict(row)}")
    
    await conn.close()

asyncio.run(main())
