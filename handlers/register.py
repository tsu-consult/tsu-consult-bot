import asyncio
import json
import logging

from aiogram import Router, F, types
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove, BotCommand, BotCommandScopeChat, CallbackQuery
)

from keyboards.main_keyboard import show_main_menu
from services.auth import auth
from states.register_state import RegisterState
from utils.messages import edit_step

router = Router()
logger = logging.getLogger(__name__)

HOME_COMMANDS = [
    BotCommand(command="/home", description="Главное меню")
]


@router.message(F.text == "/register")
@router.callback_query(lambda c: c.data == "start")
async def start_registration(event: Message | CallbackQuery, state: FSMContext):
    if isinstance(event, types.CallbackQuery):
        telegram_id = event.from_user.id
        message = event.message
    else:
        telegram_id = event.from_user.id
        message = event

    role = await auth.get_role(telegram_id)
    if role:
        await show_main_menu(message, role)
        return

    await state.update_data(
        telegram_id=telegram_id
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить контакт", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await message.answer(
        "Пожалуйста, поделитесь вашим контактом для регистрации 👇",
        reply_markup=keyboard
    )
    await state.set_state(RegisterState.waiting_for_contact)


@router.message(RegisterState.waiting_for_contact, F.contact)
async def process_contact(message: Message, state: FSMContext):
    contact = message.contact

    phone_number = contact.phone_number
    raw_username = message.from_user.username

    username = raw_username if raw_username.startswith("@") else f"@{raw_username}"

    first_name = contact.first_name or ""
    last_name = contact.last_name or ""

    await state.update_data(
        phone_number=phone_number,
        username=username,
        first_name=first_name,
        last_name=last_name
    )

    success_msg = await message.answer(
        "Успешно ✅",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.update_data(success_msg_id=success_msg.message_id)

    role_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎓 Студент", callback_data="role_student"),
            InlineKeyboardButton(text="👨‍🏫 Преподаватель", callback_data="role_teacher")
        ]
    ])

    await edit_step(
        message,
        state,
        "Выберите вашу роль:",
        keyboard=role_keyboard
    )
    await state.set_state(RegisterState.waiting_for_role)


@router.callback_query(RegisterState.waiting_for_role, F.data.startswith("role_"))
async def process_role_selection(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    role = callback.data.split("_")[1]

    telegram_id = data["telegram_id"]
    username = data["username"]
    first_name = data["first_name"]
    last_name = data["last_name"]
    phone_number = data["phone_number"]

    logger.info(
        "Register attempt: telegram_id=%s | username=%s | phone=%s | role=%s",
        telegram_id, username, phone_number, role
    )

    try:
        result = await auth.register(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            role=role
        )
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON response: %s", e)
        await handle_registration_error(callback, state, "Некорректный ответ от сервера.")
        return
    except ValueError as e:
        await handle_registration_error(callback, state, str(e))
        return

    if result:
        success_msg_id = data.get("success_msg_id")

        tasks = []

        if success_msg_id:
            tasks.append(callback.bot.delete_message(callback.message.chat.id, success_msg_id))
        tasks.append(edit_step(callback.message, state, "✅ Регистрация прошла успешно!"))

        tasks.append(
            callback.bot.set_my_commands(
                commands=HOME_COMMANDS,
                scope=BotCommandScopeChat(chat_id=callback.message.chat.id)
            )
        )

        try:
            await asyncio.gather(*tasks)
        except (TelegramBadRequest, TelegramAPIError):
            pass

        await show_main_menu(callback.message, role)

    else:
        await handle_registration_error(callback, state)

    await state.clear()


async def handle_registration_error(callback: types.CallbackQuery, state: FSMContext, error_text: str = None):
    data = await state.get_data()
    chat_id = callback.message.chat.id
    success_msg_id = data.get("success_msg_id")

    delete_tasks = []

    if success_msg_id:
        delete_tasks.append(callback.bot.delete_message(chat_id, success_msg_id))
    delete_tasks.append(callback.bot.delete_message(chat_id, callback.message.message_id))

    try:
        await asyncio.gather(*delete_tasks)
    except (TelegramBadRequest, TelegramAPIError):
        pass

    user_message = error_text or "❌ Ошибка при регистрации. Попробуйте позже."
    await callback.message.answer(f"❌ {user_message}")

    from handlers.start import cmd_start
    await cmd_start(callback.message)

    await state.clear()


@router.message(RegisterState.waiting_for_contact)
async def invalid_contact(message: Message):
    await message.answer("Пожалуйста, нажмите кнопку «📱 Отправить контакт».")
