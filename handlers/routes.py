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

# Клас з додатковими полями для реєстрації
from aiogram.fsm.state import State, StatesGroup
class Register(StatesGroup):
    age = State()
    address = State()



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

    await message.answer(
        "<b>Замовляй авто</b>, або обери інший пункт який тебе ціквить.", parse_mode="HTML",
        reply_markup=get_order_some_keyboard())


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
async def get_next_driver(exclude: list[int] | None = None):
    global driver_index

    if exclude is None:
        exclude = []

    if not driversWork:
        return None
    
    checked = 0

    while checked < len(driversWork):
        driver = driversWork[driver_index]

        driver_index += 1
        if driver_index >= len(driversWork):
            driver_index = 0

        if driver not in exclude:
            return driver
        
        checked += 1

    return None


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

    async with aiosqlite.connect(DB_ORDERS) as db:
        cursor = await db.execute(
            "INSERT INTO orders (passenger_id, status, latitude, longitude, rejected_drivers)" \
            "VALUES (?, ?, ?, ?, ?)",
            (message.from_user.id, "pending", shyryna, dovzhyna, json.dumps([]))
        )
        await db.commit()
        order_id = cursor.lastrowid

    next_driver = await get_next_driver(exclude=[])
    if not next_driver:
        await message.answer("Вибачте, наразі жодного водія немає❌")
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
    user_address = await get_user_address(message.from_user.id)
    await message.answer("Адресу отримано ✅\nШукаємо водія...")
    async with aiosqlite.connect(DB_USERS) as db:
        cursor = await db.execute(
            "SELECT address FROM users WHERE telegram_id = ?",
            (message.from_user.id,)
        )
        await db.commit()
        user_address = cursor.fetchone()

    async with aiosqlite.connect(DB_ORDERS) as db:
        cursor = await db.execute(
            "INSERT INTO orders (passenger_id, status, address, rejected_drivers)" \
            "VALUES (?, ?, ?, ?)",
            (message.from_user.id, "pending", user_address, json.dumps([]))
        )
        await db.commit()
        order_id = cursor.lastrowid

    next_driver = await get_next_driver(exclude=[])
    if not next_driver:
        await message.answer("Вибачте, наразі жодного водія немає❌")
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
    
    else:
        await message.answer("❌ Вашої адреси в базі немає. Пройдіть реєстрацію ще раз.")


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
            await callback.answer("Замовлення не знайдено", show_alert=True)
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
                                            text="Нажаль, віьних водіїв зараз немає")
            await callback.message.edit_text("Ви відхилили замовлення")
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














    # async with aiosqlite.connect(DB_ORDERS) as db:
    #     cursor = await db.execute("SELECT passenger_id, status FROM orders WHERE id =?",
    #                               (order_id,))
    #     order = await cursor.fetchone()

    # if not order or order[1] != "pending":
    #     await callback.answer("Замовлення вже оброблено", show_alert=True)
    #     return
    
    # passenger_id = order[0]

    # await callback.bot.send_message(chat_id=passenger_id, text="Нажаль усі водії зара зайняті, спробуйте пізнше!")    
    #     async with aiosqlite.connect(DB_ORDERS) as db:
    #         await db.execute(
    #         "UPDATE orders SET status = ?, driver_id = ? WHERE id = ?",
    #         ("canceled", callback.from_user.id, order_id)
    #     )

    # await callback.bot.send_message(chat_id=passenger_id,
    #         text="❌ Водій відхилив замовлення. Шукаємо наступного водія")
    
    # await callback.message.edit_text("❌ Ви відхилили замовлення")

    # await callback.answer()

# --- Повернутися до головнх кнопок
@router.message(F.text == "Повернутися до головного меню 🔙")
async def cancel(message: Message):
    await message.answer("<b>Замовляй авто</b>, або обери інший пункт який тебе ціквить.", parse_mode="HTML",
                         reply_markup=get_order_some_keyboard())


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

    if user_id not in driversID:
        await message.answer(f"Вибачте, на жаль, ви не є водієм нашої компанії\n" \
            f"Якщо хочете стати водієм - пишіть @{ADMIN_USERNAME}")
        return

    async with aiosqlite.connect(DB_USERS) as db:

        cursor = await db.execute(
            "SELECT role FROM users WHERE telegram_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        role = row[0] if row else None

        if role == "driver":
            await message.answer("Ви вже працюєте🤑\nЧекайте на змовлення", reply_markup=to_leave_line())
            return
        

        await db.execute("UPDATE users SET role = 'driver' WHERE telegram_id = ?",
                            (user_id,)
        )
        await db.commit()
    
    if user_id not in driversWork:
        driversWork.append(user_id)
    
    await message.answer("Вітаємо, ви на лінії✅\nСкоро замовлення!🚕", 
                             reply_markup=to_leave_line())
    
# --- Функція зняття з лінії
@router.message(F.text == "Зійти з лінії")
async def go_home(message: Message):
    user_id = message.from_user.id
    
    if user_id not in driversID:
        return
    
    if user_id not in driversWork:
        await message.answer("Ви і так не на лінії!🚫", reply_markup=get_order_some_keyboard())
        return
    
    if user_id in driversWork:
        driversWork.remove(user_id)
        await message.answer("Гарно відпочити!😌", reply_markup=get_order_some_keyboard())


# --- Функція зі зміни ролі на ВОДІЯ
async def change_role_driver(telegram_id: int):
    async with aiosqlite.connect(DB_USERS) as db:
        await db.execute("UPDATE users SET role = 'driver' WHERE telegram_id = ?", (telegram_id,))
        await db.commit()
    
# --- Функція зі зміни ролі на ПАСАЖИРА
async def change_role_passenger(telegram_id: int):
    async with aiosqlite.connect(DB_USERS) as db:
        await db.execute("UPDATE users SET role = 'passenger' WHERE telegram_id = ?", (telegram_id,))
        await db.commit()



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





