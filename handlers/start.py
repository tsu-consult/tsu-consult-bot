from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BotCommand, BotCommandScopeChat

from handlers import register
from keyboards.main_keyboard import show_main_menu
from services.auth import auth

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await show_main_menu(message, role=None)

@router.callback_query(lambda c: c.data == "start")
async def start_register_callback(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id

    role = await auth.get_role(telegram_id)

    if not role:
        try:
            await auth.login(telegram_id)
            role = await auth.get_role(telegram_id)
        except ValueError:
            await register.start_registration(callback, state)
            await callback.answer()
            return

    if role:
        await callback.message.bot.set_my_commands(
            commands=[
                BotCommand(command="/home", description="Главное меню"),
            ],
            scope=BotCommandScopeChat(chat_id=callback.message.chat.id)
        )
        await show_main_menu(callback, role)

    await callback.answer()
