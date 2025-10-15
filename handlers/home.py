from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards.main_keyboard import show_main_menu
from utils.auth_utils import ensure_auth

router = Router()


@router.message(Command("home"))
async def cmd_home(message: Message):
    telegram_id = message.from_user.id
    role = await ensure_auth(telegram_id, message)
    if role:
        await show_main_menu(message, role)
