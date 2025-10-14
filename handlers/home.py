from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from keyboards.main_keyboard import show_main_menu
from services.auth import auth

router = Router()

@router.message(Command("home"))
async def cmd_home(message: Message):
    telegram_id = message.from_user.id
    role = await auth.get_role(telegram_id)

    await show_main_menu(message, role)
