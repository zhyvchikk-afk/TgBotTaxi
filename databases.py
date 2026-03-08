import aiosqlite
from config import DB_USERS, DB_PRICES, DB_ORDERS
from aiogram.types import Message
import asyncio
from prices import all_data



# Функція зі створення таблиці в БД якщо такої немає 
async def init_db():
    async with aiosqlite.connect(DB_USERS) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         role TEXT DEFAULT "passenger",
                         is_online INTEGER DEFAULT 0,
                         telegram_id INTEGER UNIQUE,
                         username TEXT,
                         full_name TEXT,
                         age INTEGER,
                         address TEXT,
                         phone TEXT,
                         car TEXT,
                         color TEXT,
                         number TEXT
                         )
                        """)
        await db.commit()

async def user_exists(telegram_id: int):
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute("SELECT 1 FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        user = await cursor.fetchone()
        return user is not None

async def add_user(message: Message, age: int, address: str, phone: str):
    async with aiosqlite.connect(DB_USERS) as db:
        await db.execute("""INSERT INTO users 
            (telegram_id, username, full_name, age, address, phone)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                message.from_user.id,
                message.from_user.username,
                message.from_user.full_name,
                age,
                address,
                phone
            )
        )
        await db.commit()

async def get_users():
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute("SELECT telegram_id, username, full_name, age, address FROM users")
        result = await cursor.fetchall()
        return result

async def get_user_address(telegram_id: int):
    async with aiosqlite.connect(DB_USERS) as db:
        async with db.execute("SELECT address FROM users WHERE telegram_id = ?",
            (telegram_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None



# Функція зі створення таблиці в БД якщо такої немає 
async def init_db_prices():
    
    async with aiosqlite.connect(DB_PRICES) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         category TEXT,
                         destination TEXT UNIQUE,
                         one_way TEXT,
                         two_way TEXT
                         )
                        """)
        await db.executemany("""INSERT OR IGNORE INTO prices 
            (category, destination, one_way, two_way)
            VALUES (?, ?, ?, ?)""", all_data
        )
        await db.commit()

# --- Отримання цін
async def get_prices():
    async with aiosqlite.connect(DB_PRICES) as db:
        cursor = await db.execute("SELECT destination, one_way, two_way FROM prices")
        result = await cursor.fetchall()
        return result
    

# --- Створення таблиці замовлень
async def init_db_orders():
    async with aiosqlite.connect(DB_ORDERS) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         passenger_id INTEGER NOT NULL,
                         driver_id INTEGER,
                         status TEXT NOT NULL,
                         latitude REAL,
                         longitude REAL,
                         address TEXT,
                         rejected_drivers TEXT DEFAULT '[]',
                         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                         )
                        """)
        await db.commit()