from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from handlers import register
from keyboards.main_keyboard import show_main_menu
from services.auth_api import TSUAuth

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    auth = TSUAuth()
    telegram_id = message.from_user.id

    if auth.is_registered(telegram_id):
        role = auth.get_role(telegram_id)
        await show_main_menu(message, role)
    else:
        await show_main_menu(message, None)

@router.callback_query(lambda c: c.data == "start")
async def start_register_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await register.start_registration(callback, state)
    await callback.answer()
