from aiogram.types import (    
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

def get_order_some_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Замовити таксі 🚕"), KeyboardButton(text="Тарифи 📋")],
            [KeyboardButton(text="Про нас ✌🏻"), KeyboardButton(text="Працювати з нами🪙")]
        ],
        resize_keyboard=True
    )
    return keyboard

def register_button():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Зареєструватися")]
        ],
        resize_keyboard=True
    )
    return keyboard

def location_button():
    keyboard = ReplyKeyboardMarkup(
        keyboard = [
            [KeyboardButton(text='Надіслати локацію 📍', request_location=True), 
            KeyboardButton(text="Надіслати збережену адресу 🏠")],
            [KeyboardButton(text="Повернутися до головного меню 🔙")]
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

def accept_reject_button(passenger_id: int):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Прийняти ✅", callback_data=f"accept_{passenger_id}")],
            [InlineKeyboardButton(text="Відхилити ❌", callback_data=f"reject_{passenger_id}")]
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