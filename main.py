
import asyncio
import sys
from os import getenv
from aiogram import Bot, Dispatcher
from handlers.routes import router
from config import BOT_TOKEN
import aiosqlite
from databases import init_db, init_db_prices


TOKEN = BOT_TOKEN

dp = Dispatcher()
dp.include_router(router)




# Запуск бота
async def main():
    bot = Bot(token=TOKEN)

    # Створення таблиці в БД якщо такої немає
    await init_db()
    await init_db_prices()
    
    # Перевірка запуску бота
    print('Start...')
    # Запуск і постійна робота бота
    await dp.start_polling(bot)

# Перевірка, що каже виконуй код лише тоді, коли файл запущено напряму
if __name__ == '__main__':
    # Запуск аасинхронної функції
    asyncio.run(main())