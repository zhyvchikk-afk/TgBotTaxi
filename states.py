from aiogram.fsm.state import State, StatesGroup
class Register(StatesGroup):
    age = State()
    address = State()
    phone = State()

class RegisterDriver(StatesGroup):
    car = State()
    color = State()
    number = State()

class AdminStates(StatesGroup):
    add_driver = State()
    remove_driver = State()

class Address(StatesGroup):
    address = State()