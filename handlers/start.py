from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BotCommand, BotCommandScopeChat

from handlers import register
from keyboards.main_keyboard import show_main_menu
from services.auth import auth

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if message.text and len(message.text.split()) > 1:
        param = message.text.split(maxsplit=1)[1]

        if "google_success" in param:
            import logging
            logger = logging.getLogger(__name__)

            telegram_id = message.from_user.id
            logger.info(f"Processing Google Calendar redirect for telegram_id={telegram_id}, param={param}")

            role = await auth.get_role(telegram_id)
            logger.info(f"User role: {role}")

            if role == "dean":
                from aiogram import types
                from services.profile import profile

                await profile.set_calendar_connected(telegram_id, True)
                logger.info(f"Calendar connected status set to True for telegram_id={telegram_id}")

                keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]
                ])
                await message.answer(
                    "✅ <b>Google Calendar успешно подключен!</b>",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                return

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
