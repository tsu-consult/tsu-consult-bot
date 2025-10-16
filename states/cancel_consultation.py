from aiogram.fsm.state import StatesGroup, State

class CancelConsultation(StatesGroup):
    choosing_consultation = State()