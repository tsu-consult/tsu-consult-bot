from aiogram import Router, F
from aiogram.types import CallbackQuery

from services.auth import auth
from services.profile import profile
from keyboards.help_keyboard import make_help_menu, make_help_page
from keyboards.main_keyboard import show_main_menu

router = Router()


@router.callback_query(F.data == "menu_help")
async def open_help_menu(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await auth.get_role(telegram_id)
    teacher_status = None
    if role == "teacher":
        teacher_status = await profile.get_teacher_status(telegram_id)

    kb = make_help_menu(role, teacher_status)
    await callback.message.edit_text("❓ Справка — выберите раздел:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("help_section:"))
async def help_section_callback(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await auth.get_role(telegram_id)
    teacher_status = None
    if role == "teacher":
        teacher_status = await profile.get_teacher_status(telegram_id)

    _, key = callback.data.split(":", 1)

    if key == "guest":
        text = (
            "👋 Руководство пользователя\n\n"
            "1. Регистрация и вход — нажмите кнопку 'Регистрация / Вход' в главном меню.\n"
            "2. Доступные функции для гостей — только просмотр справки и регистрация.\n"
            "3. После регистрации вы сможете создавать запросы и смотреть преподавателей.\n"
        )
    elif key == "student":
        text = (
            "📘 Руководство пользователя\n\n"
            "1. Как найти преподавателя\n"
            "2. Как создать запрос на консультацию\n"
            "3. Как просмотреть свои консультации\n"
        )
    elif key == "teacher":
        text = (
            "📗 Руководство пользователя\n\n"
            "1. Как создать консультацию\n"
            "2. Как просматривать запросы студентов\n"
            "3. Как управлять расписанием\n"
        )
    else:
        text = (
            "❓ Частые вопросы (FAQ):\n\n"
            "Q: Как зарегистрироваться?\nA: Нажмите кнопку 'Регистрация / Вход' в главном меню.\n\n"
            "Q: Что делать, если не приходит подтверждение?\nA: Проверьте, правильно ли указан Telegram ID в профиле.\n"
        )

    kb = make_help_page(role, key, teacher_status)

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.answer(text, reply_markup=kb)

    await callback.answer()


@router.callback_query(F.data == "help_back")
async def help_back_callback(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await auth.get_role(telegram_id)

    await show_main_menu(callback, role, edit_message=callback.message)
    await callback.answer()
