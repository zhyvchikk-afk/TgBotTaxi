from aiogram import Router, F
from aiogram.filters import Command
import random
from asyncio import sleep
from config import DB_USERS, DB_PRICES, DB_ORDERS, DB_CAS
from config import ADMIN_ID
from aiogram.types import (
    Message,
    FSInputFile,
    CallbackQuery,
    ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext
import aiosqlite
from button import (
    get_order_some_keyboard,
    register_button,
    send_phone, 
    inline_way_button,
    location_button,
    to_leave_line,
    accept_reject_button,
    admin_button,
    cancel_admin,
    admin_id,
    complaints_and_suggestions_button,
    done_order_button,
    complaint_on_driver_btn,
)
from databases import (
    user_exists,
    add_user,
    get_users,
    init_db_prices,
    get_prices,
    get_user_address,
    history_orders,
)
import json
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from datetime import datetime
from zoneinfo import ZoneInfo
from aiogram.fsm.state import State, StatesGroup
from states import Register, RegisterDriver, AdminStates, Address, Complaints, Suggestions
import asyncio
import logging

router = Router()

@router.errors()
async def error_handler(event, exception):
    logging.error(f"Error: {exception}")
    return True

@router.message(F.text == "/restart")
async def restart_bot(message: Message):
    await message.answer("Бот перезапускається...")
    exit()



def split_text(text, limit=4000):
    chunks = []
    
    while len(text) > limit:
        # шукаємо останній перенос рядка перед лімітом
        split_index = text.rfind("\n", 0, limit)
        
        if split_index == -1:
            split_index = limit
        
        chunk = text[:split_index]
        
        # перевірка чи не обірвався <b>
        if chunk.count("<b>") > chunk.count("</b>"):
            chunk += "</b>"
        
        chunks.append(chunk)
        text = text[split_index + 1:].lstrip()
    
    chunks.append(text)
    return chunks

driver_index = 0
active_order = {}

# --- Функція отримання данних користувача з БД
async def get_passenger_info(passenger_id: int) -> dict:
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT full_name, username, phone FROM users WHERE telegram_id = ?",
            (passenger_id,)
        )
        row = await cursor.fetchone()

    if row:
        full_name, username, phone = row
        return {"full_name": full_name, "username": username, "phone": phone}
    else:
        return {"full_name": "Невідомо", "username": "Невідомо", "phone": "Невідомо"}

# --- Функція таймера для замовлень
async def order_timeout(bot, order_id, driver_id):
    await asyncio.sleep(30)

    async with aiosqlite.connect(DB_ORDERS)as db:
        cursor = await db.execute(
            "SELECT status FROM orders WHERE id = ?",
            (order_id,)
        )
        row = await cursor.fetchone()

    if not row:
        return
    
    status = row[0]

    if status == "pending":
        fake_callback = type("obj", (), {})()
        fake_callback.data = f"reject_{order_id}"
        fake_callback.from_user = type("obj", (), {"id": driver_id})()
        fake_callback.bot = bot

        async def fake_answer(*args, **kwargs): return True
        fake_callback.answer = fake_answer

        async def fake_edit(*args, **kwargs): return True    
        
        fake_callback.message = type("obj", (), {
            "chat": type("obj", (), {"id": driver_id})(),
            "bot": bot,
            "edit_text": fake_edit
        })()

        await reject_order(fake_callback)




# --- Старт та реєстрація
@router.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    if not await user_exists(message.from_user.id):
        await message.answer(
        "Привіт! Я Бот для замовлення таксі в місті Південнокраїнськ і не тільки!\n" \
        "Спершу зареєструємо тебе!", parse_mode="HTML",
        reply_markup=register_button())
        return

    await message.answer(
            "<b>Замовляй авто</b>, або обери інший пункт який тебе ціквить.", parse_mode="HTML",
            reply_markup=get_order_some_keyboard() if user_id != ADMIN_ID else admin_id())

@router.message(F.text == "Зареєструватися✈️")
async def register_start(message: Message, state: FSMContext):
    if await user_exists(message.from_user.id):
        await message.answer(
            "Ви вже зареєстровані ✅", parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove())
        return
    
    await message.answer("Будь ласка, вкажіть свій вік: ", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Register.age)

@router.message(Register.age, F.text)
async def get_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введіть число 🔢")
        return
    
    if int(message.text) < 10 or int(message.text) > 90:
        await message.answer("Вік повинен бути від 1️⃣0️⃣ до 9️⃣0️⃣")
        return

    await state.update_data(age=int(message.text))
    await message.answer("Введіть адресу на яку частіше викликаєте авто.\n"
    "Наприклад домашню 🏠: ")
    await state.set_state(Register.address)

@router.message(Register.address, F.text)
async def get_address(message: Message, state: FSMContext):
    await state.update_data(address=str(message.text))
    await message.answer("Поділіться Вашим номером телефону:", reply_markup=send_phone())
    await state.set_state(Register.phone)

@router.message(Register.phone, F.contact)    
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    age = data["age"]
    address = data["address"]
    phone = message.contact.phone_number

    phone_clean = phone.strip()
    if not phone_clean.startswith("+"):
        phone_clean = f"+{phone_clean}"

    await add_user(message, age, address, phone_clean)
    await message.answer("Реєстрацію завершено 🎉", reply_markup=get_order_some_keyboard() if message.from_user.id != ADMIN_ID else admin_id())
    await state.clear()
    
# --- Функція з визначення наступного водія
async def get_next_driver(exclude: list[int] = []):
    global driver_index

    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT telegram_id FROM users WHERE role = 'driver' AND is_online = 1"
                                  )
        rows = await cursor.fetchall()

    drivers = [row[0] for row in rows if row[0] not in exclude]

    if not drivers:
        return None
    
    driver = drivers[driver_index % len(drivers)]

    driver_index += 1

    return driver


# --- Замовлення авто, тарифи, про нас
@router.message(F.text == "Замовити таксі 🚕")
async def order(message: Message):
    user_id = message.from_user.id
    
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT is_online FROM users WHERE telegram_id = ?",
            (user_id,)
        )
        await db.commit()
        row = await cursor.fetchone()
        is_online = row[0] if row else None
    
    if is_online != 0:
        await message.answer("Ви не можете замовити машину, якщо знаходитесь на лінії!")
        return

    await message.answer("Оберіть пункт нижче👇🏻",
                        reply_markup=location_button())
    

@router.message(F.text == "Ввести адресу вручну✏️")
async def write_address(message: Message, state: FSMContext):
    await message.answer("Введіть адресу. Наприклад: Шевченка 8, 3 під'їзд", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Address.address)

# --- Відправка разової адреси
@router.message(Address.address, F.text)
async def get_address_write(message: Message, state: FSMContext):
    address = message.text
    await message.answer("Адресу отримано!✅\nШукаємо водія...")

    timeKyiv = datetime.now(ZoneInfo("Europe/Kyiv"))
    created_at = timeKyiv.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_ORDERS)as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE passenger_id = ?",
            (message.from_user.id,)
        )
        row = await cursor.fetchone()
        order_number = row[0] + 1

        cursor = await db.execute(""
            "INSERT INTO orders (passenger_order_number, passenger_id, status, address, created_at, rejected_drivers)" \
            "VALUES (?, ?, ?, ?, ?, ?)",
            (order_number, message.from_user.id, "pending", address, created_at, json.dumps([]))
        )
        await db.commit()
        order_id = cursor.lastrowid
    await state.clear()

    next_driver = await get_next_driver()
    if not next_driver:
        async with aiosqlite.connect(DB_ORDERS) as db:
            await db.execute(
                "UPDATE orders SET status = 'canceled' WHERE id = ?",
                (order_id,)
            )
            await db.commit()
            await message.answer("Вибачте, наразі жодного водія немає❌", reply_markup=get_order_some_keyboard())
            return
    
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT phone FROM users WHERE telegram_id = ?",
            (message.from_user.id,)
        )
        await db.commit()
        row = await cursor.fetchone()
        phone_passenger = row[0] if row else None
    
    await message.bot.send_message(chat_id=next_driver, text=f"🚕 <b>Нове замовлення: #{order_id}</b>\n\n"
                                     f"🪪 Пасажир: <b>{message.from_user.full_name}</b>\n"
                                     f"👤 Username: <b>@{message.from_user.username}</b>\n"
                                     f"📱 Телефон: <b><a href='tel:{phone_passenger}'>{phone_passenger}</a></b>\n"
                                     f"📍 Адреса: {address}", parse_mode="HTML"
        )
    await message.bot.send_message(
        chat_id=next_driver,
        text=f"<b>Прийняти замовлення #{order_id}?</b>🏎", parse_mode="HTML",
                                   reply_markup=accept_reject_button(order_id))
    
    asyncio.create_task(
        order_timeout(message.bot, order_id, next_driver)
    )


# --- Відправка локації
@router.message(F.location)
async def location(message: Message, state: FSMContext):
    shyryna = message.location.latitude
    dovzhyna = message.location.longitude

    await state.update_data(latitude=shyryna, longitude=dovzhyna)
    await message.answer("Локацію отримано ✅\nШукаємо водія...")

    timeKyiv = datetime.now(ZoneInfo("Europe/Kyiv"))
    created_at = timeKyiv.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_ORDERS) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE passenger_id = ?",
            (message.from_user.id,)
        )
        row = await cursor.fetchone()
        order_number = row[0] + 1

        cursor = await db.execute(
            "INSERT INTO orders (passenger_order_number, passenger_id, status, latitude, longitude, created_at, rejected_drivers)" \
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (order_number, message.from_user.id, "pending", shyryna, dovzhyna, created_at, json.dumps([]))
        )
        await db.commit()
        order_id = cursor.lastrowid

    next_driver = await get_next_driver()
    if not next_driver:
        async with aiosqlite.connect(DB_ORDERS) as db:
            cursor = await db.execute(
                "UPDATE orders SET status = 'canceled' WHERE id = ?",
                (order_id,)
            )
            await message.answer("Вибачте, наразі жодного водія немає❌", reply_markup=get_order_some_keyboard())
            await db.commit()
            return
    
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT phone FROM users WHERE telegram_id = ?",
            (message.from_user.id,)
        )
        await db.commit()
        row = await cursor.fetchone()
        phone_passenger = row[0] if row else None
    
    await message.bot.send_message(chat_id=next_driver, text=f"🚕 <b>Нове замовлення: #{order_id}</b>\n\n"
                                     f"🪪 Пасажир: <b>{message.from_user.full_name}</b>\n"
                                     f"👤 Username: <b>@{message.from_user.username}</b>\n"
                                     f"📱 Телефон: <b><a href='tel:{phone_passenger}'>{phone_passenger}</a></b>\n"
                                     f"📍 Локація:", parse_mode="HTML"
        )
    await message.bot.send_location(chat_id=next_driver, latitude=shyryna, longitude=dovzhyna)
    await message.bot.send_message(chat_id=next_driver, text=f"<b>Прийняти замовлення #{order_id}?</b>🏎", parse_mode="HTML",
                                   reply_markup=accept_reject_button(order_id))
       
    asyncio.create_task(
        order_timeout(message.bot, order_id, next_driver)
    )
    

# --- Відправка адреси
@router.message(F.text == "Надіслати збережену адресу 🏠")
async def address(message: Message):
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT address FROM users WHERE telegram_id = ?",
            (message.from_user.id,)
        )
        row = await cursor.fetchone()
        user_address = row[0] if row else None
    
    if not user_address:
        await message.answer("❌ Вашої адреси в базі немає. Пройдіть реєстрацію ще раз.", reply_markup=register_button())
        return

    timeKyiv = datetime.now(ZoneInfo("Europe/Kyiv"))
    created_at = timeKyiv.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_ORDERS) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE passenger_id = ?",
            (message.from_user.id,)
        )
        row = await cursor.fetchone()
        order_number = row[0] + 1

        cursor = await db.execute(
            "INSERT INTO orders (passenger_order_number, passenger_id, status, address, created_at, rejected_drivers)" \
            "VALUES (?, ?, ?, ?, ?, ?)",
            (order_number, message.from_user.id, "pending", user_address, created_at, json.dumps([]))
        )
        await db.commit()
        order_id = cursor.lastrowid

    next_driver = await get_next_driver()
    if not next_driver:
        async with aiosqlite.connect(DB_ORDERS) as db:
            cursor = await db.execute(
                "UPDATE orders SET status = 'canceled' WHERE id = ?",
                (order_id,)
            )
            await message.answer("Вибачте, наразі жодного водія немає❌", reply_markup=get_order_some_keyboard())
            await db.commit()
            return

    if user_address:
        await message.answer(f"Вашу адресу <b>{user_address}</b> отримано! Шукаємо водія...", parse_mode="HTML")
    
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT phone FROM users WHERE telegram_id = ?",
            (message.from_user.id,)
        )
        await db.commit()
        row = await cursor.fetchone()
        phone_passenger = row[0] if row else None
    
    await message.bot.send_message(chat_id=next_driver, text=f"🚕 <b>Нове замовлення: #{order_id}</b>\n\n"
                                     f"🪪 Пасажир: <b>{message.from_user.full_name}</b>\n"
                                     f"👤 Username: <b>@{message.from_user.username}</b>\n"
                                     f"📱 Телефон: <b><a href='tel:{phone_passenger}'>{phone_passenger}</a></b>\n"
                                     f"📍 Адреса: {user_address}", parse_mode="HTML"
        )
    await message.bot.send_message(chat_id=next_driver, text="<b>Прийняти замовлення?</b>🏎", parse_mode="HTML",
                                reply_markup=accept_reject_button(order_id))
        
    asyncio.create_task(
        order_timeout(message.bot, order_id, next_driver)
    )

# --- Прийняття замовлення водієм
@router.callback_query(F.data.startswith("accept_"))
async def accept_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    driver_id = callback.from_user.id

    async with aiosqlite.connect(DB_ORDERS) as db:
        cursor = await db.execute("SELECT passenger_id, status FROM orders WHERE id = ?",
                              (order_id,)
                              )
        order = await cursor.fetchone()

        if not order or order[1] != "pending":
            await callback.message.edit_text("Замовлення вже обробленно")
            await callback.answer()
            return
        
        passenger_id = order[0]
    
        await db.execute(
            "UPDATE orders SET status = ?, driver_id = ? WHERE id = ?", 
            ("in progress", driver_id, order_id)
        )
        await db.commit()
    
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT full_name, phone, car, color, number FROM users WHERE telegram_id = ?",
            (driver_id,)
        )
        row = await cursor.fetchone()
        full_name, phone, car, color, number = row
    text_info = (
        f"👤 Водій <b>{full_name}</b> прийняв Ваше замовлення!\n"
        f"📱 Телефон: <a href='tel:{phone}'>{phone}</a>\n"
        f"🚕 Автомобіль: <b>{color} {car}</b>\n"
        f"🔢 Номерний знак: <b>{number}</b>\n"
    )
    # --- Повідомлення пасажиру
    await callback.bot.send_message(chat_id=passenger_id,
                                    text=text_info, parse_mode="HTML",
                                    reply_markup=complaint_on_driver_btn(order_id))
    
    # --- Повідомлення водію
    await callback.message.edit_text(f"✅ Ви прийняли замовлення #{order_id}", reply_markup=done_order_button(order_id))
    await callback.answer()

# --- Скрга на водія
@router.callback_query(F.data.startswith("complaint_"))
async def complaint_on_driver(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[1])

    async with aiosqlite.connect(DB_ORDERS) as db:
        cursor = await db.execute(
            "SELECT status, driver_id FROM orders WHERE id = ?",
            (order_id,)
        )
        row = await cursor.fetchone()
    
    driver_id = row[1]

    if not row or row[0] != "in progress":
        await callback.answer("Скаргу можна залишити тільки під час поїздки\nПерейдіть у розділ скарг та пропозицій та залиште скаргу там.", 
                              show_alert=True)
        return
    
    await state.update_data(order_id=order_id, driver_id=driver_id)

    await callback.message.answer("Опишіть, що у Вас сталося:")

    await state.set_state(Complaints.driver)
    await callback.answer()

@router.message(Complaints.driver)
async def save_driver_complaint(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    driver_id = data["driver_id"]

    text = message.text

    timeKyiv = datetime.now(ZoneInfo("Europe/Kyiv"))
    created_at = timeKyiv.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_CAS) as db:
        await db.execute(
            "INSERT INTO cas " \
            "(passenger_id, name, text, category, driver_id, created_at) " \
            "VALUES (?, ?, ?, ?, ?, ?)",
            (message.from_user.id,
             message.from_user.full_name,
             text,
             f"Скарга на водія (замовлення #{order_id})",
             driver_id,
             created_at
             )
        )
        await db.commit()

    await message.answer("✅ Скаргу на водія відправлено. Ми її розглянемо і повідомимо Вам про результат.")
    await state.clear()







# --- Завершення поїздки
@router.callback_query(F.data.startswith("finish_"))
async def finish_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    driver_id = callback.from_user.id

    timeKyiv = datetime.now(ZoneInfo("Europe/Kyiv"))
    finished_at = timeKyiv.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_ORDERS) as db:
        cursor = await db.execute(
            "SELECT passenger_id, status FROM orders WHERE id = ? AND driver_id = ?",
            (order_id, driver_id)
        )
        order = await cursor.fetchone()

        if not order:
            await callback.message.edit_text("Замовлення не знйдено або Ви не його водій🚫")
            await callback.answer()
            return
        
        if order[1] != "in progress":
            await callback.message.edit_text("Замовлення вже завершено, або ще не прийняте.")
            await callback.answer()
            return
        
        passenger_id = order[0]

        await db.execute(
            "UPDATE orders SET status = ?, finished_at = ? WHERE id = ?",
            ("completed", finished_at, order_id)
        )
        await db.commit()

    await callback.bot.send_message(chat_id = passenger_id,
                                    text=f"✅ Поїздку завершено. Дякуємо, що обрали нас!")
        
    await callback.message.edit_text(
        f"Ви закінчили поїздку✅", reply_markup=None
    )
    await callback.answer("Поїздку завершено!")

# --- Відхилення замовлення водієм
@router.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    current_driver_id = callback.from_user.id

    async with aiosqlite.connect(DB_ORDERS) as db:
        cursor = await db.execute(
            "SELECT passenger_id, status, rejected_drivers, latitude, longitude, address FROM orders WHERE id = ?",
            (order_id,))
        order = await cursor.fetchone()

        if not order:
            await callback.answer("❌Замовлення не знайдено", show_alert=True)
            return
    
        passenger_id, status, rejected_json, latitude, longitude, address = order

        if status != "pending":
            await callback.message.edit_text("Замовлення вже оброблено")
            await callback.answer()
            return
    
        rejected_list = json.loads(rejected_json) if rejected_json else []
        if current_driver_id not in rejected_list:
            rejected_list.append(current_driver_id)

        next_driver = await get_next_driver(exclude=rejected_list)

        if not next_driver:
            await db.execute(
                "UPDATE orders SET status = ?, rejected_drivers = ? WHERE id = ?",
                ("canceled", json.dumps(rejected_list), order_id)
            )
            await db.commit()

            await callback.bot.send_message(chat_id=passenger_id,
                                            text="Нажаль, вільних водіїв зараз немає❌\nСпробуйте пізніше",
                                            reply_markup=get_order_some_keyboard() if passenger_id != ADMIN_ID else admin_id())
            await callback.message.edit_text("Ви відхилили замовлення❌")
            await callback.answer()
            return
    
        await db.execute(
            "UPDATE orders SET rejected_drivers = ? WHERE id = ?",
            (json.dumps(rejected_list), order_id)
        )
        await db.commit()

    passenger_data = await get_passenger_info(passenger_id)
    passenger_name = passenger_data.get("full_name", "Невідомо")
    passenger_username = passenger_data.get("username", "Невідомо")
    passenger_phone = passenger_data.get("phone", "Невідомо")

    if not address: 
        await callback.bot.send_message(
            chat_id=next_driver,
            text=f"🚕 <b>Нове замовлення: #{order_id}</b>\n\n"
                f"🪪 Пасажир: <b>{passenger_name}</b>\n"
                f"👤 Username: <b>@{passenger_username}</b>\n"
                f"📱 Телефон: <b><a href='tel:{passenger_phone}'>{passenger_phone}</a></b>\n"
                f"📍 Локація:", 
                parse_mode="HTML"
        )
        await callback.bot.send_location(chat_id=next_driver, latitude=latitude, longitude=longitude)
        await callback.bot.send_message(chat_id=next_driver, text="<b>Прийняти замовлення?</b>🏎", parse_mode="HTML",
                                    reply_markup=accept_reject_button(order_id))
    else:
        await callback.bot.send_message(
            chat_id=next_driver,
            text=f"🚕 <b>Нове замовлення: #{order_id}</b>\n\n"
                f"🪪 Пасажир: <b>{passenger_name}</b>\n"
                f"👤 Username: <b>@{passenger_username}</b>\n"
                f"📱 Телефон: <b><a href='tel:{passenger_phone}'>{passenger_phone}</a></b>\n"
                f"📍 Адреса: <b>{address}</b>", 
                parse_mode="HTML"
        )
        await callback.bot.send_message(chat_id=next_driver, text="<b>Прийняти замовлення?</b>🏎", parse_mode="HTML",
                            reply_markup=accept_reject_button(order_id))
        
    await callback.message.edit_text("Ви відхилили замовлення")
    await callback.answer()



# --- Повернутися до головнх кнопок
@router.message(F.text == "Повернутися до головного меню 🔙")
async def cancel(message: Message):
    user_id = message.from_user.id
    await message.answer("<b>Замовляй авто</b>, або обери інший пункт який тебе ціквить.", parse_mode="HTML",
                            reply_markup=get_order_some_keyboard() if user_id != ADMIN_ID else admin_id())


@router.message(F.text == "Тарифи 📋")
async def price(message: Message):
    await message.answer("Оберіть який напрямок вас цікавить 📋", reply_markup=inline_way_button())

@router.callback_query(F.data == "city")
async def show_city_price(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PRICES) as db:
        async with db.execute("SELECT destination, one_way FROM prices WHERE category = 'city'") as cursor:
            result = await cursor.fetchall()
    
    if not result:
        await callback.answer("Дані не знайдено", show_alert=True)
        return
    
    text = f"<b>Тарифи по місту: </b>\n\n"
    for dest, price1 in result:
        text += f"▪️{dest}: <b>{price1} грн</b>\n"

    for chunk in split_text(text, 4000):
        await callback.message.answer(chunk, parse_mode="HTML",
                                    reply_markup=inline_way_button())
    
    await callback.answer()

@router.callback_query(F.data == "kostyantynivka")
async def show_kostyantynivka_price(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PRICES) as db:
        async with db.execute("SELECT destination, one_way, two_way FROM prices WHERE category = 'kostyantynivka'") as cursor:
            result = await cursor.fetchall()

    if not result:
        await callback.answer("Дані не знайдено", show_alert=True)
        return
    
    text = f"<b>Тарифи по Костянтинівці: </b>\n\n"
    for dest, price1, price2 in result:
        text += f"▪️{dest}:  <b>{price1} грн</b>  |  {price2} грн\n"

    for chunk in split_text(text, 4000):
        await callback.message.answer(chunk, parse_mode="HTML",
                                      reply_markup=inline_way_button())

    await callback.answer()

@router.callback_query(F.data == "suburbs")
async def show_suburbs_price(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PRICES) as db:
        async with db.execute("SELECT destination, one_way, two_way FROM prices WHERE category = 'suburbs'") as cursor:
            result = await cursor.fetchall()
    
    if not result:
        await callback.answer("Данні не знайденно", show_alert=True)
        return

    text = f"<b>Тарифи передмісття: </b>\n\n"
    for dest, price1, price2 in result:
        text += f"▪️{dest}:  <b>{price1} грн</b>  |  {price2} грн\n"

    for chunk in split_text(text, 4000):
        await callback.message.answer(chunk, parse_mode="HTML",
                                      reply_markup=inline_way_button())

    await callback.answer()

@router.callback_query(F.data == "intercity")
async def show_intercity_price(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PRICES) as db:
        async with db.execute("SELECT destination, one_way, two_way FROM prices WHERE category = 'intercity'") as cursor:
            result = await cursor.fetchall()
    
    if not result:
        await callback.answer("Данні не знайденно", show_alert=True)
        return

    text = f"<b>Тарифи 30км +: </b>\n\n"
    for dest, price1, price2 in result:
        text += f"▪️{dest}:  <b>{price1} грн</b>  |  {price2} грн\n"

    for chunk in split_text(text, 4000):
        await callback.message.answer(chunk, parse_mode="HTML",
                                      reply_markup=inline_way_button())

    await callback.answer()
        

@router.message(F.text == "Про нас ✌🏻")
async def price(message: Message):
    await message.answer(
        f"Привіт! Це Таксі GO!🚕\nМи не чужі, не приїжджі, ба навіть більше, "
        f"ви нас вже знаєте...\nА знаєте, бо ми найшвидші... "
        f"Бо найкомфортніші... І найпривітливіші😌...\nАле все ж ми змінилися!\n"
        f"Чому так впевнено? Бо до цього моменту, не було однієї компанії "
        f"в якій працювали б найкращі водії, з любов'ю до свого авто та своєї справи\n"
        f"А ми таких зібрали в нас\n"
        f"Ви це можливо навіть і не помітите, але нам стало вільніше дихати!😋\n"
        f"А це значить ми стали ще швидшими, ще комфортнішими і ще привітливішими!🙂‍↕️\n"
        f"Скоро цей бот зможе ще більше ніж уміє зараз!\n"
        f"Замовляйте авто тут, або телефонуйте за номером телефону!\n"
        f"<a href='tel:+380730461929'>+380 73 046 1929</a>\n"       
        f"<b>МИ З РАДІСТЮ"
        f"ДОСТАВИМО ВАС У БУДЬ-ЯКУ ТОЧКУ УКРАЇНИ!</b> 🫶🏻❤️"
        , parse_mode="HTML")

# --- Функція виходу водія на лінію
@router.message(F.text == "Працювати з нами🪙")
async def go_work(message: Message, state: FSMContext):
    user_id = message.from_user.id

    async with  aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute("SELECT role, is_online, car, color, number FROM users WHERE telegram_id = ?",
                                  (user_id,))
        row = await cursor.fetchone()

        if not row:
            await message.answer("❌ Ви не зареєстровані в системі.",
                                 reply_markup=register_button())
            return
        
        role, is_online, car, color, number = row

        if role != 'driver':
            await message.answer("Вибачте, але ви не є водієм компанії❌")
            return
        
        if not all([car, color, number]):
            await message.answer("Для роботи необхідно додати дані про автомобіль\nЯка марка та модель Вашого авто?🚗\nНаприклад Volkswagen Passat")
            await state.set_state(RegisterDriver.car)
            return

        if is_online != 0:
            await message.answer("Ви і так на лінії✅ ", reply_markup=to_leave_line() if user_id != ADMIN_ID else to_leave_line())
            return

        await db.execute("UPDATE users SET is_online = 1 WHERE telegram_id = ?",
                         (user_id,))
        await db.commit()
        await message.answer(f"Гарних пасажирів та вдалого заробітку!😌\n\n"
                                f"Ваше авто: <b>{color} {car}\n</b>"
                                f"Номерний знак: <b>{number}</b>", parse_mode="HTML",
                                reply_markup=to_leave_line() if user_id != ADMIN_ID else to_leave_line())
        
@router.message(RegisterDriver.car)
async def register_car(message: Message, state: FSMContext):
    await state.update_data(car=message.text)
    await message.answer("Який колір Вашого авто? 🎨")
    await state.set_state(RegisterDriver.color)

@router.message(RegisterDriver.color)
async def register_color(message: Message, state: FSMContext):
    await state.update_data(color=message.text)
    await message.answer("Введіть державний номерний знак🔢\n"
    "Наприклад: ВЕ 1234 НА")
    await state.set_state(RegisterDriver.number)

@router.message(RegisterDriver.number)
async def register_number(message: Message, state: FSMContext):
    data = await state.get_data()
    car = data["car"]
    color = data["color"]
    number = message.text

    async with aiosqlite.connect(DB_USERS) as db:
        await db.execute(
            "UPDATE users SET car = ?, color = ?, number = ?, is_online = 1 WHERE telegram_id = ?",
            (car, color, number, message.from_user.id)
        )
        await db.commit()

    await state.clear()
    await message.answer(
        f"✅ Дані збережено!\n"
        f"🚗 Авто: <b>{color} {car}</b>\n"
        f"🔢 Номерний знак: <b>{number}</b>\n\n"
        f"Ви на лінії! Вдалого заробітку! 🪙", parse_mode="HTML",
        reply_markup=to_leave_line()
    )


# --- Історія замовлень
@router.message(F.text == "Історія замовлень📝")
async def show_history_orders(message: Message):
    text = await history_orders(message)
    await message.answer(text, parse_mode="HTML")

# --- Скарги та пропозиції
@router.message(F.text == "Пропозиції та скарги✅")
async def complaints_and_suggestions(message: Message):
    await message.answer("Обирай👇🏻", reply_markup=complaints_and_suggestions_button())

# --- Пропозиція
@router.message(F.text == "Пропозиція/Відгук✅")
async def suggestions(message: Message, state: FSMContext):
    await message.answer("Нам є, що покращити?\nРозкажіть нам про свою пропозицію або залиште відгук!", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Suggestions.suggestions)

@router.message(Suggestions.suggestions)
async def save_suggestions(message: Message, state: FSMContext):
    suggestions=message.text

    timeKyiv = datetime.now(ZoneInfo("Europe/Kyiv"))
    created_at = timeKyiv.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_CAS) as db:
        await db.execute(
            "INSERT INTO cas (passenger_id, name, text, category, created_at)" \
            "VALUES (?, ?, ?, ?, ?)",
            (message.from_user.id, message.from_user.full_name, suggestions, "Пропозиція/Відгук", created_at)
        )
        await db.commit()
    
    await message.answer("Вашу пропозицію/відгук збережено! Очікуйте на відповідь",
                         reply_markup=get_order_some_keyboard() if message.from_user.id != ADMIN_ID else admin_id())
    await state.clear()

# --- Скарга
@router.message(F.text == "Скарга❌")
async def complaints(message: Message, state: FSMContext):
    await message.answer("Опишіть ситуацію, що Вам не сподобалася. До 1000 символів")
    await state.set_state(Complaints.complaints)

@router.message(Complaints.complaints)
async def save_complaints(message: Message, state: FSMContext):
    complaints = message.text

    if len(complaints) > 1000:
        await message.answer("❌ Максимальна довжина скарги — 1000 символів")
        return

    timeKyiv = datetime.now(ZoneInfo("Europe/Kyiv"))
    created_at = timeKyiv.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_CAS) as db:
        await db.execute(
            "INSERT INTO cas (passenger_id, name, text, category, created_at)" \
            "VALUES (?, ?, ?, ?, ?)",
            (message.from_user.id, message.from_user.full_name, complaints, "Скарга", created_at)
        )
        await db.commit()
    await message.answer("Одразу після обробки скарги ми приймемо міри і повідомимо Вам про результат!",
                         reply_markup=get_order_some_keyboard() if message.from_user.id != ADMIN_ID else admin_id())
    await state.clear()

    
# --- Функція отримання особистої статистики водія
@router.message(F.text == "Моя статистика📝")
async def my_statistics(message: Message):
    driver_id = message.from_user.id

    timeKyiv = datetime.now(ZoneInfo("Europe/Kyiv"))
    created_at = timeKyiv.strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_ORDERS) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE driver_id = ? AND status = ?",
            (driver_id, "completed")
        )
        row = await cursor.fetchone()
        total_orders = row[0] if row else 0

        if not total_orders:
            await message.answer("Поки ви не зробили жодного замовлення.")

        cursor = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE driver_id = ? AND DATE(created_at) = ? AND status = ?",
            (driver_id, created_at, "completed")
        )
        row = await cursor.fetchone()
        today_orders = row[0] if row else 0

    async with aiosqlite.connect(DB_CAS) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM cas WHERE driver_id = ?",
            (driver_id,)
        )
        row = await cursor.fetchone()
        count_cas = row[0] if row else 0

        cursor = await db.execute(
            "SELECT COUNT(*) FROM cas WHERE driver_id = ? AND answer IS NOT NULL",
            (driver_id,)
        )
        row = await cursor.fetchone()
        count_cas_answered = row[0] if row else 0

    await message.answer(
        f"🧮<b>Ваша статистика:</b> \n\n"
        f"🚕Загальна кількість замовлень: {total_orders}\n"
        f"📅Замовлень сьогодні: {today_orders}\n\n"
        f"⚠️Всього скарг: {count_cas}\n"
        f"✅Скарг вирішено: {count_cas_answered}\n", parse_mode="HTML"
                         )





# --- Функція зняття з лінії
@router.message(F.text == "Зійти з лінії❌")
async def go_home(message: Message):
    user_id = message.from_user.id
    
    async with  aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute("SELECT role, is_online FROM users WHERE telegram_id = ?",
                                  (user_id,))
        row = await cursor.fetchone()
        role = row[0] if row else None
        is_online = row[1] if row else None

        if role != 'driver':
            await message.answer("Вибачте, але ви не є водієм компанії", reply_markup=get_order_some_keyboard())
            return

        if is_online != 1:
            await message.answer("Ви і так не на лінії❌", reply_markup=get_order_some_keyboard() if user_id != ADMIN_ID else admin_id())
            return
        await db.execute("UPDATE users SET is_online = 0 WHERE telegram_id = ?",
                         (user_id,))
        await db.commit()
        await message.answer("Гарно відпочити!😌", reply_markup=get_order_some_keyboard() if user_id != ADMIN_ID else admin_id())


# --- Список користувачів ????????????????????????????????????????????????
@router.message(Command('users'))
async def users(message: Message):
    if message.from_user.id != ADMIN_ID: 
        return
    
    users = await get_users()

    if not users:
        await message.answer('Користувачі в базі відсутні')
        return
    
    text = "Користувачі в базі:\n\n"
    for telegram_id, username, full_name, age, address in users:
        text += f"- ID: {telegram_id} - @{username} - {full_name} - {age}\n- {address} -\n"
    
    await message.answer(text)



# ---
# --- Адмін панель
# ---
@router.message(F.text == "Адмін-панель🧮")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer("Адмін-панель🧮", reply_markup=admin_button())


# --- Додавання водія
@router.message(F.text == '➕Додати водія')
async def add_driver_start(message: Message, state: FSMContext):
    await message.answer("Введіть id користувача:", reply_markup=cancel_admin())
    await state.set_state(AdminStates.add_driver)

@router.message(AdminStates.add_driver, F.text == "Скасувати ❌")
async def cancel_add_driver(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Дію скасовано", reply_markup=admin_button())

@router.message(AdminStates.add_driver)
async def add_driver_process(message: Message, state: FSMContext):
    user_id = message.text

    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute("SELECT username, role FROM users WHERE telegram_id = ?",
                         (user_id,))
        row = await cursor.fetchone()

        if not row:
            await message.answer("❌ Користувача не знайдено")
            return
        
        username, role = row

        if role == "driver":
            await message.answer(f"@{username} вже є вашим водієм")
            return
        
        await db.execute("UPDATE users SET role = 'driver' WHERE telegram_id = ?",
                         (user_id,))
        await db.commit()
    
    await message.answer(f"✅ @{username} став водієм", parse_mode="HTML", reply_markup=admin_button())
    await state.clear()


# --- Видалення водія
@router.message(F.text == '➖Видалити водія')
async def remove_driver_start(message: Message, state: FSMContext):
    await message.answer("Введіть id користувача:", reply_markup=cancel_admin())
    await state.set_state(AdminStates.remove_driver)

@router.message(AdminStates.remove_driver, F.text == "Скасувати ❌")
async def cancel_remove_driver(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Дію скасовано", reply_markup=admin_button())

@router.message(AdminStates.remove_driver)
async def remove_driver_process(message: Message, state: FSMContext):
    user_id = message.text

    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute("SELECT username, role FROM users WHERE telegram_id = ?",
                         (user_id,))
        row = await cursor.fetchone()

        if not row:
            await message.answer("❌ Користувача не знайдено")
            return
        
        username, role = row

        if role == "passenger":
            await message.answer(f"@{username} не був вашим водієм")
            return
        
        await db.execute("UPDATE users SET role = 'passenger', is_online = 0 WHERE telegram_id = ?",
                         (user_id,))
        await db.commit()
    
    await message.answer(f"✅ @{username} більше не є водієм", parse_mode="HTML",
                        reply_markup=admin_button())
    await state.clear()


# --- Список водіїв
@router.message(F.text == "📋Список водіїв")
async def list_drivers(message: Message):
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT telegram_id, username, full_name, car, color, number FROM users WHERE role = 'driver'",
        )
        result = await cursor.fetchall()

        if not result:
            await message.answer("❌ Водіїв не знайдено")
            return
        
        text = f"<b>Усі водії компанії:</b>\n\n"
        for tg_id, username, fullname, car, color, number in result:
            data_list = [
                f"🪪 Username: <b>@{username}</b>\n"
                f"👤 Ім'я: <b>{fullname}</b>\n"
                f"🆔 ID: <b>{tg_id}</b>\n"
                f"🚘 Авто: <b>{car}</b>\n"
                f"🎨 Колір: <b>{color}</b>\n"
                f"🔢 Номерний знак: <b>{number}</b>\n\n"
            ]
            text += "\n\n".join(data_list)
        await message.answer(text, parse_mode="HTML")
        await db.commit()


# --- Список онлайн водіїв
@router.message(F.text == "📝Водії на лінії")
async def online_drivers(message: Message):
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT telegram_id, username, full_name, car, color, number FROM users WHERE role = 'driver' AND is_online = 1",
        )
        result = await cursor.fetchall()

        if not result:
            await message.answer("❌ Онлайн водіїв не знайдено")
            return
        
        text = f"<b>Водії на лінії:</b>\n\n"
        for tg_id, username, fullname, car, color, number in result:
            data_list = [
                f"🪪 Username: <b>@{username}</b>\n"
                f"👤 Ім'я: <b>{fullname}</b>\n"
                f"🆔 ID: <b>{tg_id}</b>\n"
                f"🚘 Авто: <b>{car}</b>\n"
                f"🎨 Колір: <b>{color}</b>\n"
                f"🔢 Номерний знак: <b>{number}</b>\n\n"
            ]
            text += "\n\n".join(data_list)
        await message.answer(text, parse_mode="HTML")
        await db.commit()



# --- Статистика замовлень
@router.message(F.text == "📊Статистика замовлень")
async def get_data(message: Message):
    await message.answer("Оберіть дату:",
                         reply_markup=await SimpleCalendar().start_calendar()
                         )

async def get_statistics(date):
    date_str = date.strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_ORDERS) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = ?",
            (date_str,)
        )
        total = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = ? AND status = 'completed'",
            (date_str,)
        )
        completed = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = ? AND status = 'canceled'",
            (date_str,)
        )
        canceled = (await cursor.fetchone())[0]

    date_str = date.strftime("%Y-%m-%d")
    day = date_str.split("-")[2].strip()
    mounth = date_str.split("-")[1].strip()
    year = date_str.split("-")[0].strip()
    result = [day, mounth, year]
    my_date = ".".join(result)

    return (
        f"📊Статистика за {my_date}\n\n"
        f"🚖Замовлень: {total}\n"
        f"✅Прийнято: {completed}\n"
        f"❌Відхилено: {canceled}\n"
    )


@router.callback_query(SimpleCalendarCallback.filter())
async def process_calendar(callback_query: CallbackQuery, callback_data: SimpleCalendarCallback):
    selected, date = await SimpleCalendar().process_selection(callback_query, callback_data)

    if selected:
        stats = await get_statistics(date)
        await callback_query.message.answer(stats)


# --- Обробка скарг та пропозицій
@router.message(F.text == "⚠️✅Скарги та пропозиції")
async def processing_cas(message: Message, state: FSMContext):
    async with aiosqlite.connect(DB_CAS) as db:
        cursor = await db.execute(
            "SELECT id, passenger_id, name, text, category, created_at FROM cas WHERE answer IS NULL LIMIT 1"
        )
        row = await cursor.fetchone()

    if not row:
        await message.answer("Записів не знайдено! Вітаю!")
        return

    cas_id, passenger_id, name, text, category, created_at = row

    user_text = (
        f"<b>{category}</b> від <b>{name}:</b> \n\n"
        f"{text} \n\n"
        f"{created_at}\n"
        f"ID коритувача: {passenger_id}\n"
        f"ID скарги: {cas_id}\n\n"
    )

    await message.answer(user_text, parse_mode="HTML")
    await state.update_data(cas_id=cas_id, passenger_id=passenger_id)
    await state.set_state(Complaints.processing)

@router.message(Complaints.processing)
async def answer_cas(message: Message, state: FSMContext):
    data = await state.get_data()
    cas_id = data["cas_id"]
    passenger_id = data["passenger_id"]

    answer = message.text
    
    timeKyiv = datetime.now(ZoneInfo("Europe/Kyiv"))
    created_at = timeKyiv.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_CAS) as db:
        await db.execute("""
            UPDATE cas
            SET answer = ?, created_at_answer = ?
            WHERE id = ?
        """, (answer, created_at, cas_id))
        await db.commit()

    await message.bot.send_message(passenger_id,
        f"📩Відповідь підтримки:\n\n{answer}")
    await message.answer("Відповідь надіслано")
    await state.clear()



ALLOWED_DBS = {
    "users": "/data/users.sql",
    "orders": "/data/orders.sql",
    "prices": "/data/prices.sql",
    "cas": "/data/cas.sql",
}

@router.message(F.text.startswith("/getdb_"), F.from_user.id == ADMIN_ID)
async def send_db(message: Message):

    try:
        name_db = message.text.split("_")[1]
        
        if name_db not in ALLOWED_DBS:
            await message.answer("❌ Невідома база")
            return
        
        db_file = FSInputFile(ALLOWED_DBS[name_db]) 
        
        await message.answer_document(
            db_file, 
            caption=f"📂 <b>Актуальна база даних</b>\n👤 Користувач: @{message.from_user.username}",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Помилка при отриманні файлу: {e}")


@router.message()
async def unknown(message: Message):
    await message.answer(
        "❗ Використовуйте кнопки меню."
    )