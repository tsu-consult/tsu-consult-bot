from aiogram.fsm.state import StatesGroup, State

class BookConsultation(StatesGroup):
    waiting_for_request = State()
