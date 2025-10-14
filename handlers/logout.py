import logging

from aiogram import F
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, BotCommand, BotCommandScopeChat

from keyboards.main_keyboard import guest_menu
from services.auth import auth

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "menu_logout")
async def logout_callback(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    chat_id = callback.message.chat.id

    logger.info("Logout attempt: telegram_id=%s", telegram_id)

    await auth.logout()
    await state.clear()
    await callback.message.delete()

    await callback.bot.set_my_commands(
        commands = [
            BotCommand(command="start", description="Начать"),
        ],
        scope = BotCommandScopeChat(chat_id=chat_id)
    )

    await callback.message.answer(
        "Вы успешно вышли из аккаунта 👋",
        reply_markup=guest_menu
    )
    await callback.answer()
