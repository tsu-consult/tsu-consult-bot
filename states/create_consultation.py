from aiogram.fsm.state import StatesGroup, State

class CreateConsultationFSM(StatesGroup):
    waiting_for_title = State()
    waiting_for_date = State()
    waiting_for_start_time = State()
    waiting_for_end_time = State()
    waiting_for_max_students = State()
    confirming = State()
