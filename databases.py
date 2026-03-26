import aiosqlite
from config import DB_USERS, DB_PRICES, DB_ORDERS, DB_CAS, DB_COUNTORDERS
from aiogram.types import Message
import asyncio
from prices import all_data
from datetime import datetime
from zoneinfo import ZoneInfo



# Функція зі створення таблиці в БД якщо такої немає 
async def init_db():
    async with aiosqlite.connect(DB_USERS) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         role TEXT DEFAULT "passenger",
                         is_online INTEGER DEFAULT 0,
                         telegram_id INTEGER,
                         username TEXT,
                         full_name TEXT,
                         age INTEGER,
                         address TEXT,
                         phone TEXT,
                         car TEXT,
                         color TEXT,
                         number TEXT,
                         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                         rating REAL DEFAULT 5.0,
                         count_rating INTEGER DEFAULT 20
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

    timeKyiv = datetime.now(ZoneInfo("Europe/Kyiv"))
    created_at = timeKyiv.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_USERS) as db:
        await db.execute("""INSERT INTO users 
            (telegram_id, username, full_name, age, address, phone, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                message.from_user.id,
                message.from_user.username,
                message.from_user.full_name,
                age,
                address,
                phone,
                created_at
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
                         passenger_order_number INTEGER,
                         passenger_id INTEGER NOT NULL,
                         driver_id INTEGER,
                         status TEXT NOT NULL,
                         latitude REAL,
                         longitude REAL,
                         address TEXT,
                         rejected_drivers TEXT DEFAULT '[]',
                         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                         finished_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                         )
                        """)
        await db.commit()

    
# --- Історія замовлень
async def history_orders(message: Message):
    passenger_id = message.from_user.id

    async with aiosqlite.connect(DB_ORDERS) as db:
        cursor = await db.execute("""
            SELECT passenger_order_number, driver_id, status, address, created_at 
            FROM orders 
            WHERE passenger_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        """, (passenger_id,))

        rows = await cursor.fetchall()

    text = "📝Останні 10 замовлень:\n\n"
    
    for order in rows:
        order_num, driver_id, status, address, created_at = order

        if not address:
            address = "Замовлення за локацією"

        async with aiosqlite.connect(DB_USERS) as db:
            cursor = await db.execute("""
                SELECT full_name, car, color, number 
                FROM users
                WHERE telegram_id = ?""",
                (driver_id,)
            )
            driver = await cursor.fetchone()

        if driver:
            driver_name, car, color, number = driver
        else:
            driver_name, car, color, number = "-", "-", "-", "-"

        if status == "completed":
            status = "🟢Виконано"
        else:
            status = "🔴Відхилено"

        text += (
            f"<b>#{order_num}</b>\n"
            f"👤Водій: <b>{driver_name}</b>\n"
            f"🚘Авто: <b>{color} {car}</b>\n"
            f"🔢Номерний знак: <b>{number}</b>\n"
            f"📍Адреса: <b>{address}</b>\n"
            f"📊Статус: <b>{status}</b>\n"
            f"🕒<b>{created_at}</b>\n\n"
        )

    return text


# --- Створення таблиці з відгуками та пропозиціями якщо такої немає
async def init_complaints_and_suggestions():
    async with aiosqlite.connect(DB_CAS) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cas (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         passenger_id INTEGER,
                         driver_id INTEGER,
                         name TEXT,
                         text TEXT,
                         category TEXT,
                         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                         answer TEXT,
                         created_at_answer TIMESTAMP DEFAULT NULL
                         )
                        """)
        await db.commit()

# --- Створення таблиці з кількістю замовлень якщо такої немає
async def init_count_orders():
    async with aiosqlite.connect(DB_COUNTORDERS) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS countorders (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         passenger_id INTEGER,
                         username TEXT,
                         name TEXT,
                         count INTEGER,
                         )
                        """)
        await db.commit()