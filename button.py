from aiogram.types import (    
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram_calendar import SimpleCalendar

def register_button():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Зареєструватися")]
        ],
        resize_keyboard=True
    )
    return keyboard

def send_phone():
    keyboard = ReplyKeyboardMarkup(
        keyboard = [
            [KeyboardButton(text="📱 Поділитися номером", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

def get_order_some_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Замовити таксі 🚕"), KeyboardButton(text="Тарифи 📋")],
            [KeyboardButton(text="Про нас ✌🏻"), KeyboardButton(text="Працювати з нами🪙")]
        ],
        resize_keyboard=True
    )
    return keyboard

def admin_id():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Замовити таксі 🚕"), KeyboardButton(text="Тарифи 📋")],
            [KeyboardButton(text="Про нас ✌🏻"), KeyboardButton(text="Працювати з нами🪙")],
            [KeyboardButton(text="Адмін-панель🧮")]
        ],
        resize_keyboard=True
    )
    return keyboard

def location_button():
    keyboard = ReplyKeyboardMarkup(
        keyboard = [
            [KeyboardButton(text='Надіслати локацію 📍', request_location=True), 
            KeyboardButton(text="Ввести адресу вручну✏️")],
            [KeyboardButton(text="Надіслати збережену адресу 🏠"), KeyboardButton(text="Повернутися до головного меню 🔙")]
        ],
        resize_keyboard=True
    )
    return keyboard

def inline_way_button():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard = [
            [InlineKeyboardButton(text="Місто", callback_data="city")],
            [InlineKeyboardButton(text="Костянтинівка", callback_data="kostyantynivka")],
            [InlineKeyboardButton(text="Передмістя", callback_data="suburbs")],
            [InlineKeyboardButton(text="Більше 30км", callback_data="intercity")],
        ]
    )
    return keyboard

def accept_reject_button(order_id: int):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Прийняти ✅", callback_data=f"accept_{order_id}")],
            [InlineKeyboardButton(text="Відхилити ❌", callback_data=f"reject_{order_id}")]
        ]
    )
    return keyboard

def to_leave_line():
    keyboard = ReplyKeyboardMarkup(
        keyboard = [
            [KeyboardButton(text="Зійти з лінії")]
        ],
        resize_keyboard=True
    )
    return keyboard

def admin_button():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Додати водія➕"), 
             KeyboardButton(text="Видалити водія➖")],
            [KeyboardButton(text="Список водіїв"), 
             KeyboardButton(text="Водії на лінії"),
             KeyboardButton(text="📊Статистика замовлень")],
            [KeyboardButton(text="Повернутися до головного меню 🔙")]
        ],
        resize_keyboard=True
    )
    return keyboard

def cancel_admin():
    keyboard = ReplyKeyboardMarkup(
        keyboard = [
            [KeyboardButton(text="Скасувати ❌")]
        ],
        resize_keyboard=True
    )
    return keyboard

# def statistics_status_button():
#     keyboard = ReplyKeyboardMarkup(
#         keyboard = [
#             [KeyboardButton(text="✅Виконано"), KeyboardButton(text="❌Відмовлено"), KeyboardButton(text="🟡Очікує")],
#             [KeyboardButton(text="Всі"), KeyboardButton(text="🔙Назад")],
#         ],
#         resize_keyboard=True
#     )
#     return keyboard