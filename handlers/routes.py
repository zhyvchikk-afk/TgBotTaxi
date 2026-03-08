from aiogram import Router, F
from aiogram.filters import Command
import random
from asyncio import sleep
from config import DB_USERS, DB_PRICES, DB_ORDERS
from config import MY_COMPUTER, KRISTINA, EUGENE, KOSTYA_LIFE
from config import ADMIN_ID, ADMIN_USERNAME
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
    inline_way_button,
    location_button,
    to_leave_line,
    accept_reject_button,
    admin_button,
    cancel_admin,
    admin_id,
)
from databases import (
    user_exists,
    add_user,
    get_users,
    init_db_prices,
    get_prices,
    get_user_address,
)
import json
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from datetime import datetime
from zoneinfo import ZoneInfo


# Клас з додатковими полями для реєстрації
from aiogram.fsm.state import State, StatesGroup
class Register(StatesGroup):
    age = State()
    address = State()

class RegisterDriver(StatesGroup):
    car = State()
    color = State()
    number = State()

class AdminStates(StatesGroup):
    add_driver = State()
    remove_driver = State()



router = Router()
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

driversWork = []
driver_index = 0
driversID = [MY_COMPUTER, KRISTINA, EUGENE, KOSTYA_LIFE]
active_order = {}

# --- Функція отримання данних користувача з БД
async def get_passenger_info(passenger_id: int) -> dict:
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT full_name, username FROM users WHERE id = ?",
            (passenger_id,)
        )
        row = await cursor.fetchone()

    if row:
        full_name, username = row
        return {"full_name": full_name, "username": username}
    else:
        return {"full_name": "Невідомо", "username": "Невідомо"}



# --- Старт та реєстрація
@router.message(Command("start"))
async def start(message: Message):
    if not await user_exists(message.from_user.id):
        await message.answer(
        "Привіт! Я Бот для замовлення таксі в місті Южнукраїнськ і не тільки!\n" \
        "Спершу зареєструємо тебе!", parse_mode="HTML",
        reply_markup=register_button())
        return
    
    if message.from_user.id != ADMIN_ID:
        await message.answer(
            "<b>Замовляй авто</b>, або обери інший пункт який тебе ціквить.", parse_mode="HTML",
            reply_markup=get_order_some_keyboard())
    else:
        await message.answer(
            "Привіт, що робитиемо сьогодні?", parse_mode="HTML",
                reply_markup=admin_id()
        )

@router.message(F.text == "Зареєструватися")
async def register_start(message: Message, state: FSMContext):
    if await user_exists(message.from_user.id):
        await message.answer(
            "Ви вже зареєстровані ✅", parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove())
        return
    
    await message.answer("Будь ласка, вкажіть свій вік: ")
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
    data = await state.get_data()
    age = data["age"]
    address = message.text

    await add_user(message, age, address)
    await message.answer("Реєстрацію завершено 🎉", reply_markup=get_order_some_keyboard())
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
    await message.answer("Введіть адресу, або оберіть пункт нижче: ",
                         reply_markup=location_button())


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
            "INSERT INTO orders (passenger_id, status, latitude, longitude, created_at, rejected_drivers)" \
            "VALUES (?, ?, ?, ?, ?, ?)",
            (message.from_user.id, "pending", shyryna, dovzhyna, created_at, json.dumps([]))
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
            await message.answer("Вибачте, наразі жодного водія немає❌")
            await db.commit()
            return
    
    await message.bot.send_message(chat_id=next_driver, text=f"🚕 <b>Нове замовлення: #{order_id}</b>\n\n"
                                     f"👤 Пасажир: <b>{message.from_user.full_name}</b>\n"
                                     f"👤 Username: <b>@{message.from_user.username}</b>\n"
                                     f"📍 Локація:", parse_mode="HTML"
        )
    await message.bot.send_location(chat_id=next_driver, latitude=shyryna, longitude=dovzhyna)
    await message.bot.send_message(chat_id=next_driver, text=f"<b>Прийняти замовлення #{order_id}?</b>🏎", parse_mode="HTML",
                                   reply_markup=accept_reject_button(order_id))
    

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
        await message.answer("❌ Вашої адреси в базі немає. Пройдіть реєстрацію ще раз.")
        return
    
    await message.answer("Адресу отримано ✅\nШукаємо водія...")

    timeKyiv = datetime.now(ZoneInfo("Europe/Kyiv"))
    created_at = timeKyiv.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_ORDERS) as db:
        cursor = await db.execute(
            "INSERT INTO orders (passenger_id, status, address, created_at, rejected_drivers)" \
            "VALUES (?, ?, ?, ?, ?)",
            (message.from_user.id, "pending", user_address, created_at, json.dumps([]))
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
            await message.answer("Вибачте, наразі жодного водія немає❌")
            await db.commit()
            return

    if user_address:
        await message.answer(f"Вашу адресу <b>{user_address}</b> надіслано водію!", parse_mode="HTML")
        await message.bot.send_message(
            chat_id=next_driver, text=f"🚕 <b>Нове замовлення:</b>\n\n"
                                     f"👤 Пасажир: <b>{message.from_user.full_name}</b>\n"
                                     f"👤 Username: <b>@{message.from_user.username}</b>\n"
                                     f"📍 Адреса: <b>{user_address}</b>\n", parse_mode="HTML"
        )
        await message.bot.send_message(chat_id=next_driver, text="<b>Прийняти замовлення?</b>🏎", parse_mode="HTML",
                                   reply_markup=accept_reject_button(order_id))

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
            ("accepted", driver_id, order_id)
        )
        await db.commit()

    # --- Повідомлення пасажиру
    await callback.bot.send_message(chat_id=passenger_id,
                                    text="🚕 Водій прийняв ваше замовлення!")
    
    # --- Повідомлення водію
    await callback.message.edit_text(f"✅ Ви прийняли замовлення #{order_id}")
    await callback.answer()


# --- Відхилення замовлення водієм
@router.callback_query(F.data.startswith("reject_"))
async def reject_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    current_driver_id = callback.from_user.id

    async with aiosqlite.connect(DB_ORDERS) as db:
        cursor = await db.execute(
            "SELECT passenger_id, status, rejected_drivers, latitude, longitude "
            "FROM orders WHERE id = ?",
                                  (order_id,))
        order = await cursor.fetchone()

        if not order:
            await callback.answer("❌Замовлення не знайдено", show_alert=True)
            return
    
        passenger_id, status, rejected_json, shyryna, dovzhyna = order

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
                                            text="Нажаль, вільних водіїв зараз немає❌\nСпробуйте пізніше")
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

    await callback.bot.send_message(
        chat_id=next_driver,
        text=f"🚕 <b>Нове замовлення:</b>\n\n"
            f"👤 Пасажир: <b>{passenger_name}</b>\n"
            f"👤 Username: <b>@{passenger_username}</b>\n"
            f"📍 Локація:", 
            parse_mode="HTML"
    )
    await callback.bot.send_location(chat_id=next_driver, latitude=shyryna, longitude=dovzhyna)
    await callback.bot.send_message(chat_id=next_driver, text="<b>Прийняти замовлення?</b>🏎", parse_mode="HTML",
                                   reply_markup=accept_reject_button(order_id))
    
    await callback.message.edit_text("Ви відхилили замовлення")
    await callback.answer()



# --- Повернутися до головнх кнопок
@router.message(F.text == "Повернутися до головного меню 🔙")
async def cancel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("<b>Замовляй авто</b>, або обери інший пункт який тебе ціквить.", parse_mode="HTML",
                            reply_markup=get_order_some_keyboard())
    else:
        await message.answer(
            "Привіт, що робитиемо сьогодні?", parse_mode="HTML",
            reply_markup=admin_id()
        )


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
    await message.answer("""
        Привіт! Це Таксі-Сервіс!🚕\nМи вирішили не міняти назву, адже
        ви знаєте нас саме за цим ім'ям...\n А ще, знаєте, бо ми найшвидші...
        Бо найкомфортніші... І найпривітливіші😌...\nАле все ж ми змінилися!
        Ви це можливо навіть і не помітите, але нам стало вільніше дихати!😋\n
        А це значить ми стали ще швидшими, ще комфортнішими і ще привтливішими!🙂‍↕️
        Замовляйте авто тут, або телефонуйте за номером телефону!\n<b>МИ З РАДІСТЮ
        ДОСТАВИМО ВАС У БУДЬ-ЯКУ ТОЧКУ УКРАЇНИ!</b> 🫶🏻❤️
                        """, parse_mode="HTML")

# --- Функція виходу водія на лінію
@router.message(F.text == "Працювати з нами🪙")
async def go_work(message: Message):
    user_id = message.from_user.id
    
    async with  aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute("SELECT role, is_online FROM users WHERE telegram_id = ?",
                                  (user_id,))
        row = await cursor.fetchone()
        role = row[0] if row else None
        is_online = row[1] if row else None

        if role != 'driver':
            await message.answer("Вибачте, але ви не є водієм компанії")
            return

        if is_online != 0:
            await message.answer("Ви і так на лінії✅ ", reply_markup=to_leave_line())
            return

        await db.execute("UPDATE users SET is_online = 1 WHERE telegram_id = ?",
                         (user_id,))
        await db.commit()
        await message.answer("Гарних пасажирів та вдалого заробітку!😌", reply_markup=to_leave_line())

    
# --- Функція зняття з лінії
@router.message(F.text == "Зійти з лінії")
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
            if user_id != ADMIN_ID:
                await message.answer("Ви і так не на лінії❌", reply_markup=get_order_some_keyboard())
                return
            else:
                await message.answer("Ви і так не на лінії❌", reply_markup=admin_id())
                return

        await db.execute("UPDATE users SET is_online = 0 WHERE telegram_id = ?",
                         (user_id,))
        await db.commit()
        if user_id != ADMIN_ID:
            await message.answer("Гарно відпочити!😌", reply_markup=get_order_some_keyboard())
        else:
            await message.answer("Гарно відпочити!😌", reply_markup=admin_id())

# --- Список користувачів
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
@router.message(F.text == 'Додати водія➕')
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
    
    await message.answer(f"✅ @{username} став водієм", parse_mode="HTML")
    await state.clear()


# --- Видалення водія
@router.message(F.text == 'Видалити водія➖')
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
    
    await message.answer(f"✅ @{username} більше не є водієм", parse_mode="HTML")
    await state.clear()


# --- Список водіїв
@router.message(F.text == "Список водіїв")
async def list_drivers(message: Message):
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT telegram_id, username, full_name FROM users WHERE role = 'driver'",
        )
        result = await cursor.fetchall()

        if not result:
            await message.answer("❌ Водіїв не знайдено")
            return
        
        text = f"<b>Усі водії компанії:</b>\n\n"
        for tg_id, username, fullname in result:
            text += f"🪪 <b>Username:</b> @{username}\n <b>| Ім'я:</b> {fullname}\n <b>| tg_id:</b> {tg_id}\n\n"

        await message.answer(text, parse_mode="HTML")
        await db.commit()


# --- Список онлайн водіїв
@router.message(F.text == "Водії на лінії")
async def online_drivers(message: Message):
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT telegram_id, username, full_name FROM users WHERE role = 'driver' AND is_online = 1",
        )
        result = await cursor.fetchall()

        if not result:
            await message.answer("❌ Онлайн водіїв не знайдено")
            return
        
        text = f"<b>Водії онлайн:</b>\n\n"
        for tg_id, username, fullname in result:
            text += f"🪪 <b>Username:</b> @{username}\n <b>| Ім'я:</b> {fullname}\n <b>| tg_id:</b> {tg_id}\n\n"

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
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = ? AND status = 'accepted'",
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





