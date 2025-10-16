from aiogram import types
from aiogram.types import Message

from services.profile import profile
from services.auth import auth

student_menu = types.InlineKeyboardMarkup(
    inline_keyboard=[
        [
            types.InlineKeyboardButton(text="👨‍🏫 Преподаватели", callback_data="student_view_teachers"),
            types.InlineKeyboardButton(text="📄 Запросы на консультацию", callback_data="student_requests")
        ],
        [
            types.InlineKeyboardButton(text="📝 Создать запрос на консультацию", callback_data="student_create_request")
        ],
        [
            types.InlineKeyboardButton(text="📅 Мои консультации", callback_data="student_my_consultations"),
        ],
        [
            types.InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"),
            types.InlineKeyboardButton(text="🚪 Выйти", callback_data="menu_logout")
        ]
    ]
)

teacher_menu = types.InlineKeyboardMarkup(
    inline_keyboard=[
        [
            types.InlineKeyboardButton(text="➕ Создать консультацию", callback_data="teacher_create_consultation"),
        ],
        [
            types.InlineKeyboardButton(text="🔒 Закрыть запись", callback_data="teacher_close_consultation"),
            types.InlineKeyboardButton(text="❌ Отменить консультацию", callback_data="teacher_cancel_consultation")
        ],
        [
            types.InlineKeyboardButton(text="📝 Запросы студентов", callback_data="teacher_requests")
        ],
        [
            types.InlineKeyboardButton(text="📅 Мои консультации", callback_data="teacher_my_consultations")
        ],
        [
            types.InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"),
            types.InlineKeyboardButton(text="🚪 Выйти", callback_data="menu_logout")
        ]
    ]
)

teacher_unconfirmed_menu = types.InlineKeyboardMarkup(
    inline_keyboard=[
        [
            types.InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"),
            types.InlineKeyboardButton(text="🚪 Выйти", callback_data="menu_logout")
        ]
    ]
)

guest_menu = types.InlineKeyboardMarkup(
    inline_keyboard=[
        [
            types.InlineKeyboardButton(text="🔑 Регистрация / Вход", callback_data="start")
        ]
    ]
)


async def show_main_menu(message: Message, role: str | None, edit_message: types.Message | None = None):
    telegram_id = message.from_user.id
    first_name, last_name = await auth.get_user_name(telegram_id)

    if role == "student":
        greeting = f"🎓 Добро пожаловать, {first_name} {last_name}."
        keyboard = student_menu
    elif role == "teacher":
        status = await profile.get_teacher_status(telegram_id)
        greeting = f"👨‍🏫 Добро пожаловать, {first_name} {last_name}."

        if status == "active":
            keyboard = teacher_menu
        else:
            greeting += "\n\n⏳ Ваш аккаунт преподавателя находится на рассмотрении администратора.\nПока доступны только основные функции." if status == "pending" else "\n\n❌ Ваша заявка на аккаунт преподавателя была отклонена.\nПока доступны только основные функции."
            keyboard = teacher_unconfirmed_menu
    else:
        greeting = "👋 Привет!\n\nЧтобы продолжить, зарегистрируйтесь или войдите в систему 👇"
        keyboard = guest_menu

    if edit_message:
        await edit_message.edit_text(greeting, reply_markup=keyboard)
    else:
        await message.answer(greeting, reply_markup=keyboard)
