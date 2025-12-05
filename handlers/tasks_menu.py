from aiogram import Router, F
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from utils.auth_utils import ensure_auth
from services.profile import profile

router = Router()


@router.message(Command("todos"))
async def cmd_todos(message: Message):
    telegram_id = message.from_user.id
    role = await ensure_auth(telegram_id, message)

    if role != "teacher":
        await message.answer("❌ Эта команда доступна только для преподавателей.")
        return

    user_profile = await profile.get_profile(telegram_id)
    first_name = user_profile.get("first_name", "") if user_profile else ""
    last_name = user_profile.get("last_name", "") if user_profile else ""
    user_name = f"{first_name} {last_name}".strip() or "Пользователь"

    text = f"Добро пожаловать, {user_name}!\n\n📋 <b>Управление задачами</b>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Создать задачу", callback_data="teacher_create_task"),
            InlineKeyboardButton(text="🗑 Удалить задачу", callback_data="teacher_delete_task_from_menu")
        ],
        [
            InlineKeyboardButton(text="📋 Мои задачи", callback_data="teacher_view_tasks")
        ],
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile:tasks_menu"),
            InlineKeyboardButton(text="🚪 Выйти", callback_data="menu_logout")
        ],
        [
            InlineKeyboardButton(text="❓ Справка", callback_data="menu_help:tasks_menu")
        ]
    ])

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "teacher_tasks_menu")
async def show_teacher_tasks_menu(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    user_profile = await profile.get_profile(telegram_id)
    first_name = user_profile.get("first_name", "") if user_profile else ""
    last_name = user_profile.get("last_name", "") if user_profile else ""
    user_name = f"{first_name} {last_name}".strip() or "Пользователь"

    text = f"Добро пожаловать, {user_name}!\n\n📋 <b>Управление задачами</b>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Создать задачу", callback_data="teacher_create_task"),
            InlineKeyboardButton(text="🗑 Удалить задачу", callback_data="teacher_delete_task_from_menu")
        ],
        [
            InlineKeyboardButton(text="📋 Мои задачи", callback_data="teacher_view_tasks")
        ],
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile:tasks_menu"),
            InlineKeyboardButton(text="🚪 Выйти", callback_data="menu_logout")
        ],
        [
            InlineKeyboardButton(text="❓ Справка", callback_data="menu_help:tasks_menu")
        ]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()

