import asyncio
import aiosqlite
from datetime import datetime

async def health_check():
    while True:
        try:
            async with aiosqlite.connect("orders.db") as db:
                await db.execute("SELECT 1")
            print(f"[{datetime.now()}] Health check OK")
        except Exception as e:
            print(f"[{datetime.now()}] Health check FAILED: {e}")
        await asyncio.sleep(300)  # кожні 5 хвилин
