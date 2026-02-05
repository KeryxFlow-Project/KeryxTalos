
import asyncio
from sqlalchemy import text
from keryxflow.core.database import get_session
from keryxflow.config import get_settings

async def check_db():
    print(f"Checking DB at: {get_settings().database.url}")
    async for session in get_session():
        try:
            result = await session.execute(text("SELECT * FROM paperbalance"))
            rows = result.fetchall()
            print(f"Found {len(rows)} balance records:")
            for row in rows:
                print(row)
        except Exception as e:
            print(f"Error querying DB: {e}")

if __name__ == "__main__":
    asyncio.run(check_db())
