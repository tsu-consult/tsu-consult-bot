from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, BotCommand, BotCommandScopeChat

from keyboards.main_keyboard import show_main_menu
from handlers import register
from services.auth import auth

router = Router()


@router.message(Command("home"))
async def cmd_home(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    role = await auth.get_role(telegram_id)

    if not role:
        try:
            await auth.login(telegram_id)
            role = await auth.get_role(telegram_id)
        except ValueError:
            await register.start_registration(message, state)
            return

    if role:
        await message.bot.set_my_commands(
            commands=[
                BotCommand(command="/home", description="Главное меню"),
            ],
            scope=BotCommandScopeChat(chat_id=message.chat.id)
        )
        await show_main_menu(message, role)
