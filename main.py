
import asyncio
import sys
from os import getenv
from aiogram import Bot, Dispatcher
from handlers.routes import router
from config import BOT_TOKEN
import aiosqlite
from databases import (
    init_db, init_db_prices, 
    init_db_orders, 
    init_complaints_and_suggestions,
)
from utils.health import health_check
from utils.backup import backup_db


TOKEN = BOT_TOKEN

dp = Dispatcher()
dp.include_router(router)




# Запуск бота
async def main():
    bot = Bot(token=TOKEN, request_timeout = 60)
    try:
        # Створення таблиці в БД якщо такої немає
        await init_db()
        await init_db_prices()
        await init_db_orders()
        await init_complaints_and_suggestions()

        asyncio.create_task(health_check())
        asyncio.create_task(backup_db())
        
        
        # Перевірка запуску бота
        print('Start...')
        # Запуск і постійна робота бота
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        raise e
    finally:
        await bot.session.close()

# Перевірка, що каже виконуй код лише тоді, коли файл запущено напряму
if __name__ == '__main__':
    # Запуск асинхронної функції
    asyncio.run(main())