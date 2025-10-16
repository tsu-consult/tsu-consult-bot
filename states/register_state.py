from aiogram.fsm.state import State, StatesGroup

class RegisterState(StatesGroup):
    waiting_for_role = State()
    waiting_for_contact = State()
