from aiogram.fsm.state import State, StatesGroup

class RegisterState(StatesGroup):
    waiting_for_role = State()
    waiting_for_contact = State()
    waiting_for_credentials_choice = State()
    waiting_for_email = State()
    waiting_for_password = State()
