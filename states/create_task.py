from aiogram.fsm.state import StatesGroup, State


class CreateTaskFSM(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_assignee = State()
    waiting_for_deadline_date = State()
    waiting_for_deadline_time = State()
    waiting_for_reminders_choice = State()
    waiting_for_custom_reminders = State()
    confirming = State()

class CreateTeacherTaskFSM(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_deadline_date = State()
    waiting_for_deadline_time = State()
    waiting_for_reminders_choice = State()
    waiting_for_custom_reminders = State()
    confirming = State()
