from aiogram.fsm.state import State, StatesGroup

class EditProfile(StatesGroup):
    name = State()
