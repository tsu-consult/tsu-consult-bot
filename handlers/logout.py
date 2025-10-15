import logging

from aiogram import F
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, BotCommand, BotCommandScopeChat, Message

from keyboards.main_keyboard import guest_menu
from services.auth import auth

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("logout"))
@router.callback_query(F.data == "menu_logout")
async def logout_callback(event: Message | CallbackQuery, state: FSMContext):
    if isinstance(event, CallbackQuery):
        telegram_id = event.from_user.id
        message = event.message
    else:
        telegram_id = event.from_user.id
        message = event

    chat_id = message.chat.id

    logger.info("Logout attempt: telegram_id=%s", telegram_id)

    await auth.logout(telegram_id)
    await state.clear()
    await message.delete()

    await message.bot.set_my_commands(
        commands = [
            BotCommand(command="start", description="Начать"),
        ],
        scope = BotCommandScopeChat(chat_id=chat_id)
    )

    await message.answer(
        "Вы успешно вышли из аккаунта 👋",
        reply_markup=guest_menu
    )
