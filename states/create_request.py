from aiogram.fsm.state import StatesGroup, State

class CreateRequestFSM(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_subscription_choice = State()
