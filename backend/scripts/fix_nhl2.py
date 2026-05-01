import asyncio
import asyncpg
import httpx

# These are players not found by name match - try ESPN search API
MANUAL = [
    # (player_db_id, name_to_search, team_espn_id, sport)
]

# Team ESPN IDs from DB
TEAMS = {
    'Carolina Hurricanes': 7,
    'Anaheim Ducks': 25,
    'Calgary Flames': 3,
    'Detroit Red Wings': 5,
    'Florida Panthers': 26,
    'Los Angeles Kings': 8,
    'Minnesota Wild': 30,
    'Montreal Canadiens': 10,
    'Philadelphia Flyers': 15,
    'San Jose Sharks': 18,
    'Tampa Bay Lightning': 20,
    'Toronto Maple Leafs': 21,
    'Vancouver Canucks': 22,
    'Winnipeg Jets': 28,
}

async def main():
    conn = await asyncpg.connect(
        host='db', port=5432,
        user='postgres', password='postgres', database='sports_predict'
    )
    
    missing_rows = await conn.fetch("""
        SELECT p.id, p.name, t.name as team FROM players p
        JOIN teams t ON t.id = p.team_id
        WHERE t.sport_id = (SELECT id FROM sports WHERE name='Хокей')
        AND p.espn_id IS NULL
    """)
    
    updated = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for row in missing_rows:
            name = row['name']
            team = row['team']
            pid = row['id']
            
            # Try ESPN search
            search_url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/athletes?limit=5&search={name.replace(' ', '+')}"
            try:
                r = await client.get(search_url)
                data = r.json()
                athletes = data.get('athletes', [])
                if not athletes:
                    # fallback: try items array
                    athletes = data.get('items', [])
                
                if athletes:
                    best = None
                    for a in athletes:
                        aname = a.get('displayName', '')
                        if aname.lower() == name.lower():
                            best = a
                            break
                    if not best and athletes:
                        best = athletes[0]
                    
                    if best:
                        espn_id = str(best.get('id', ''))
                        display = best.get('displayName', '')
                        photo = f"https://a.espncdn.com/i/headshots/nhl/players/full/{espn_id}.png"
                        await conn.execute("""
                            UPDATE players SET espn_id=$1, photo_url=COALESCE(NULLIF(photo_url,''), $2)
                            WHERE id=$3
                        """, espn_id, photo, pid)
                        updated += 1
                        print(f"  Fixed via search: {name} -> {display} ESPN {espn_id}")
            except Exception as e:
                print(f"  Search error for {name}: {e}")
    
    print(f"\nTotal updated: {updated}")
    remaining = await conn.fetchval("SELECT COUNT(*) FROM players WHERE espn_id IS NULL AND team_id IN (SELECT id FROM teams WHERE sport_id = (SELECT id FROM sports WHERE name='Хокей'))")
    print(f"Still missing hockey: {remaining}")
    await conn.close()

asyncio.run(main())
