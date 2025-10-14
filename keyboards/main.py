from aiogram import types
from aiogram.types import Message, BotCommand, BotCommandScopeChat

student_menu = types.InlineKeyboardMarkup(
    inline_keyboard=[
        [
            types.InlineKeyboardButton(text="🗓️ Просмотр консультаций преподавателей", callback_data="student_view_consultations")
        ],
        [
            types.InlineKeyboardButton(text="✏️ Записаться на консультацию", callback_data="student_book_consultation"),
            types.InlineKeyboardButton(text="❌ Отменить запись", callback_data="student_cancel_booking")
        ],
        [
            types.InlineKeyboardButton(text="🔔 Подписаться на преподавателя", callback_data="student_subscribe_teacher"),
            types.InlineKeyboardButton(text="📝 Создать запрос на консультацию", callback_data="student_create_request")
        ],
        [
            types.InlineKeyboardButton(text="📄 Мои запросы на консультацию", callback_data="student_view_requests")
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
            types.InlineKeyboardButton(text="🗓️ Мои консультации", callback_data="teacher_my_consultations")
        ],
        [
            types.InlineKeyboardButton(text="➕ Создать консультацию", callback_data="teacher_create_consultation"),
            types.InlineKeyboardButton(text="📋 Список студентов на консультацию", callback_data="teacher_consultation_students")
        ],
        [
            types.InlineKeyboardButton(text="🔒 Закрыть запись", callback_data="teacher_close_consultation"),
            types.InlineKeyboardButton(text="❌ Отменить консультацию", callback_data="teacher_cancel_consultation")
        ],
        [
            types.InlineKeyboardButton(text="📝 Создать консультацию по запросу студентов", callback_data="teacher_create_from_request")
        ],
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


async def show_main_menu(message: Message, role: str | None):
    if role == "student":
        await message.answer("Вы вошли как студент 🎓", reply_markup=student_menu)
    elif role == "teacher":
        await message.answer("Вы вошли как преподаватель 👨‍🏫", reply_markup=teacher_menu)
    else:
        await message.answer("👋 Привет!\n\nЧтобы продолжить, зарегистрируйтесь или войдите в систему:", reply_markup=guest_menu)
