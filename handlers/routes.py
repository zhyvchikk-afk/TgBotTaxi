from aiogram import Router, F
from aiogram.filters import Command
import random
from asyncio import sleep
from config import DB_USERS, DB_PRICES
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
)
from databases import (
    user_exists,
    add_user,
    get_users,
    init_db_prices,
    get_prices,
    get_user_address,
)

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
current_driver_index = 0
driversID = [MY_COMPUTER, KRISTINA, EUGENE]
delay = random.randint(3, 8)



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
async def get_next_driver():
    global current_driver_index

    if not driversWork:
        return None
    
    driver = driversWork[current_driver_index]
    current_driver_index += 1

    if current_driver_index >= len(driversWork):
        current_driver_index = 0
    
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

    next_driver = await get_next_driver()

    if not next_driver:
        await message.answer("Вибачте, наразі жодного водія немає❌")
        return
    
    await message.bot.send_message(chat_id=next_driver, text=f"🚕 <b>Нове замовлення:</b>\n\n"
                                     f"👤 <b>Пасажир: {message.from_user.full_name}</b>"
                                     f"👤 <b>Username: @{message.from_user.username}</b>"
                                     f"📍 <b>Локація:</b>", parse_mode="HTML"
        )
    await message.bot.send_location(chat_id=next_driver, latitude=shyryna, longitude=dovzhyna)
    await sleep(delay)
    await message.answer("Водій прийняв ваше замовлення!\nОчікуйте на авто🚕")


# --- Відправка адреси
@router.message(F.text == "Надіслати збережену адресу 🏠")
async def address(message: Message):
    user_address = await get_user_address(message.from_user.id)

    next_driver = await get_next_driver()

    if not next_driver:
        await message.answer("Вибачте, наразі жодного водія немає❌")
        return

    if user_address:
        await message.answer(f"Вашу адресу <b>{user_address}</b> надіслано водію!", parse_mode="HTML")
        await message.bot.send_message(
            chat_id=next_driver, text=f"🚕 <b>Нове замовлення:</b>\n\n"
                                     f"👤 <b>Пасажир: {message.from_user.full_name}</b>"
                                     f"👤 <b>Username: @{message.from_user.username}</b>"
                                     f"📍 <b>Адреса: {user_address}</b>", parse_mode="HTML"
        )
        await sleep(delay)
        await message.answer("Водій прийняв ваше замовлення!\nОчікуйте на авто🚕")
    else:
        await message.answer("❌ Вашої адреси в базі немає. Пройдіть реєстрацію ще раз.")

@router.message(F.text == "Повернутися до головного меню 🔙")
async def cancel(message: Message):
    await message.answer("<b>Замовляй авто</b>, або обери інший пункт який тебе ціквить.", parse_mode="HTML",
                         reply_markup=get_order_some_keyboard())


@router.message(F.text == "Тарифи 📋")
async def price(message: Message):
    await message.answer("Оберіть який напрямок вас цікавить 📋", reply_markup=inline_way_button())

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

    if user_id in driversWork:
        await message.answer("Ви вже працюєте🤑\nЧекайте на змовлення", reply_markup=to_leave_line())

    if user_id not in driversID:
        await message.answer(f"Вибачте, на жаль, ви не є водієм нашої компанії\n" \
        f"Якщо хочете стати водієм - пишіть @{ADMIN_USERNAME}")
        return
    
    if user_id not in driversWork:
        driversWork.append(user_id)
        await message.answer("Вітаємо, ви на лінії✅\nСкоро замовлення!🚕", 
                             reply_markup=to_leave_line())
        return

    
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





