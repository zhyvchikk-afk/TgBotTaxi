from config import DB_ORDERS, DB_USERS, DB_PRICES, DB_CAS
import os
import datetime
import asyncio
import aiosqlite

# список всіх файлів баз, які треба бекапити
DB_FILES = [
    DB_USERS,
    DB_ORDERS,
    DB_PRICES,
    DB_CAS
]

async def backup_db():
    backup_folder = "backup"
    os.makedirs(backup_folder, exist_ok=True)  # створює папку, якщо її нема

    while True:
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        for db_file in DB_FILES:
            if not os.path.exists(db_file):
                print(f"⚠️ Файл бази {db_file} не знайдено, пропускаю...")
                continue

            backup_file = os.path.join(
                backup_folder,
                f"{os.path.splitext(db_file)[0]}_backup_{now}.sql"
            )

            try:
                async with aiosqlite.connect(db_file) as db:
                    with open(backup_file, "w", encoding="utf-8") as f:
                        async for line in db.iterdump():
                            f.write(f"{line}\n")
                print(f"✅ Backup saved: {backup_file}")
            except Exception as e:
                print(f"⚠️ Backup error ({db_file}): {e}")

        await asyncio.sleep(60 * 60)  # повторювати кожну годину