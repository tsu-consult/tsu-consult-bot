import asyncio
import json
import logging

from aiogram import Router, F, types
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from aiogram.filters import Command
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


@router.message(Command("register"))
async def start_registration(event: Message | CallbackQuery, state: FSMContext):
    if isinstance(event, types.CallbackQuery):
        telegram_id = event.from_user.id
        message = event.message
    else:
        telegram_id = event.from_user.id
        message = event

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

    if raw_username:
        username = raw_username if raw_username.startswith("@") else f"@{raw_username}"
    else:
        username = ""

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
        ],
        [
            InlineKeyboardButton(text="🏛️ Деканат", callback_data="role_dean")
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

    await state.update_data(role=role)

    if role == "dean":
        credentials_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, добавить сейчас", callback_data="add_credentials_yes")
            ],
            [
                InlineKeyboardButton(text="⏭️ Пропустить (добавлю позже)", callback_data="add_credentials_skip")
            ]
        ])

        await edit_step(
            callback.message,
            state,
            "🔐 <b>Настройка доступа к веб-версии</b>\n\n"
            "Для доступа к веб-версии системы вам нужно указать email (логин) и пароль.\n\n"
            "Вы можете добавить их сейчас или позже в профиле.\n\n"
            "❓ Хотите добавить email и пароль сейчас?",
            keyboard=credentials_keyboard
        )
        await state.set_state(RegisterState.waiting_for_credentials_choice)
        await callback.answer()
        return

    await complete_registration(callback, state)


@router.callback_query(RegisterState.waiting_for_credentials_choice, F.data == "add_credentials_skip")
async def skip_credentials(callback: CallbackQuery, state: FSMContext):
    await complete_registration(callback, state)


@router.callback_query(RegisterState.waiting_for_credentials_choice, F.data == "add_credentials_yes")
async def ask_for_email(callback: CallbackQuery, state: FSMContext):
    await edit_step(
        callback.message,
        state,
        "📧 <b>Введите email</b>\n\n"
        "Это будет ваш логин для входа в веб-версию.\n"
        "Пример: ivanov@example.com"
    )
    await state.set_state(RegisterState.waiting_for_email)
    await callback.answer()


@router.message(RegisterState.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    email = message.text.strip()

    if "@" not in email or "." not in email.split("@")[-1]:
        await message.answer("❌ Некорректный email. Попробуйте ещё раз.\nПример: ivanov@example.com")
        return

    await state.update_data(email=email)

    step_msg = await message.answer(
        "🔒 <b>Введите пароль</b>\n\n"
        "Требования к паролю:\n"
        "• Минимум 8 символов\n"
        "• Должен содержать буквы и цифры\n"
        "• Только латинские буквы и цифры",
        parse_mode="HTML"
    )
    await state.update_data(step_msg_id=step_msg.message_id)
    await state.set_state(RegisterState.waiting_for_password)


@router.message(RegisterState.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    import re

    password = message.text.strip()

    if len(password) < 8:
        await message.answer("❌ Пароль слишком короткий. Минимум 8 символов.")
        return

    if not re.match(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$", password):
        await message.answer(
            "❌ Пароль не соответствует требованиям:\n"
            "• Минимум 8 символов\n"
            "• Должен содержать буквы и цифры\n"
            "• Только латинские буквы и цифры"
        )
        return

    try:
        await message.delete()
    except Exception:
        pass

    await state.update_data(password=password)

    data = await state.get_data()
    step_msg_id = data.get("step_msg_id")

    if step_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, step_msg_id)
        except Exception:
            pass

    processing_msg = await message.answer("⏳ Регистрация...")
    await state.update_data(processing_msg_id=processing_msg.message_id)

    await complete_registration_with_credentials(message, state)


async def complete_registration(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    telegram_id = data["telegram_id"]
    username = data["username"]
    first_name = data["first_name"]
    last_name = data["last_name"]
    phone_number = data["phone_number"]
    role = data["role"]

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

        commands = [BotCommand(command="/home", description="Главное меню")]

        if role == "teacher":
            commands.append(BotCommand(command="/todos", description="Управление задачами"))

        tasks.append(
            callback.bot.set_my_commands(
                commands=commands,
                scope=BotCommandScopeChat(chat_id=callback.message.chat.id)
            )
        )

        try:
            await asyncio.gather(*tasks)
        except (TelegramBadRequest, TelegramAPIError):
            pass

        await show_main_menu(callback, role)
        await callback.answer()

    else:
        await handle_registration_error(callback, state)

    await state.clear()


async def complete_registration_with_credentials(message: Message, state: FSMContext):
    from services.dean_credentials import dean_credentials

    data = await state.get_data()

    telegram_id = data["telegram_id"]
    username = data["username"]
    first_name = data["first_name"]
    last_name = data["last_name"]
    phone_number = data["phone_number"]
    role = data["role"]
    email = data["email"]
    password = data["password"]

    logger.info(
        "Register attempt with credentials: telegram_id=%s | username=%s | phone=%s | role=%s | email=%s",
        telegram_id, username, phone_number, role, email
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

        if not result:
            processing_msg_id = data.get("processing_msg_id")
            if processing_msg_id:
                try:
                    await message.bot.delete_message(message.chat.id, processing_msg_id)
                except Exception:
                    pass
            await message.answer("❌ Ошибка при регистрации. Попробуйте позже.")
            await state.clear()
            return

        success, error_msg = await dean_credentials.add_credentials(telegram_id, email, password)

        processing_msg_id = data.get("processing_msg_id")
        success_msg_id = data.get("success_msg_id")

        delete_tasks = []
        if processing_msg_id:
            delete_tasks.append(message.bot.delete_message(message.chat.id, processing_msg_id))
        if success_msg_id:
            delete_tasks.append(message.bot.delete_message(message.chat.id, success_msg_id))

        try:
            await asyncio.gather(*delete_tasks)
        except Exception:
            pass

        if success:
            await message.answer(
                "✅ Регистрация прошла успешно!\n"
                "🔐 Email и пароль добавлены."
            )
        else:
            await message.answer(
                f"⚠️ Регистрация прошла успешно, но не удалось добавить учетные данные:\n{error_msg}\n\n"
                "Вы можете добавить их позже в профиле."
            )

        commands = [BotCommand(command="/home", description="Главное меню")]

        if role == "teacher":
            commands.append(BotCommand(command="/todos", description="Управление задачами"))

        await message.bot.set_my_commands(
            commands=commands,
            scope=BotCommandScopeChat(chat_id=message.chat.id)
        )

        await show_main_menu(message, role)


    except json.JSONDecodeError as e:
        logger.error("Invalid JSON response: %s", e)
        await message.answer("❌ Некорректный ответ от сервера.")
    except ValueError as e:
        await message.answer(f"❌ {str(e)}")
    except Exception as e:
        logger.error(f"Registration error: {e}")
        await message.answer("❌ Ошибка при регистрации. Попробуйте позже.")
    finally:
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
