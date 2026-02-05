
import asyncio
from keryxflow.core.database import init_db, get_session
from sqlalchemy import text

async def simulate_startup():
    print("Simulating KeryxFlowApp startup...")
    
    from sqlmodel import SQLModel
    print(f"Registered tables: {list(SQLModel.metadata.tables.keys())}")
    
    # This matches the logic added to KeryxFlowApp._initialize_after_splash
    await init_db()
    print("Database initialized.")
    
    # Check if table exists now
    async for session in get_session():
        try:
            # Try to query the table that was missing
            result = await session.execute(text("SELECT count(*) FROM paper_balances"))
            count = result.scalar()
            print(f"SUCCESS: 'paper_balances' table exists. Row count: {count}")
        except Exception as e:
            print(f"FAILURE: Could not query 'paper_balances': {e}")

if __name__ == "__main__":
    asyncio.run(simulate_startup())
