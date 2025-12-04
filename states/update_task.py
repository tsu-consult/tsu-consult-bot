from aiogram.fsm.state import StatesGroup, State


class UpdateTaskFSM(StatesGroup):
    waiting_for_field_choice = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_status = State()
    waiting_for_deadline_date = State()
    waiting_for_deadline_time = State()
    waiting_for_reminders_choice = State()
    waiting_for_custom_reminders = State()
    waiting_for_assignee_selection = State()
    confirming = State()

