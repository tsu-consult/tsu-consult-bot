from aiogram.fsm.state import State, StatesGroup

class EditProfile(StatesGroup):
    name = State()
    waiting_for_email = State()
    waiting_for_password = State()
    waiting_for_current_password = State()
    waiting_for_new_password = State()
