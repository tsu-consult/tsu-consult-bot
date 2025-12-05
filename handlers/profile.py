import asyncio
import logging

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
from handlers.tasks_menu import show_teacher_tasks_menu, show_teacher_tasks_menu_message
from keyboards.main_keyboard import show_main_menu
from services.profile import profile, TSUProfile
from states.edit_profile import EditProfile
from utils.auth_utils import ensure_auth
from utils.messages import answer_and_delete, delete_msg
from utils.profile_utils import show_profile

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.regexp(r"^menu_profile(?::(.+))?$"))
async def menu_profile_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    origin = None
    if ":" in callback.data:
        origin = callback.data.split(":", 1)[1]

    await show_profile(callback.message, telegram_id, edit_message=callback.message, origin=origin)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^edit_profile(?::(.+))?$"))
async def edit_profile_callback(callback: CallbackQuery, state: FSMContext):
    origin = None
    if ":" in callback.data:
        origin = callback.data.split(":", 1)[1]

    await state.update_data(profile_origin=origin)

    await callback.message.answer("Введите новое имя и фамилию 👇\n\nПример: <b>Иван Иванов</b>\n\n⚠️ Внимание! Указывайте реальные имена и фамилии", parse_mode="HTML")
    await state.set_state(EditProfile.name)
    await callback.answer()


@router.message(EditProfile.name)
async def edit_profile_name(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    new_name = message.text.strip()

    if not new_name:
        await message.answer("❗ Пожалуйста, введите имя и фамилию.")
        return

    parts = new_name.split(maxsplit=1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    success = await profile.update_profile(telegram_id, first_name, last_name)

    data = await state.get_data()
    origin = data.get("profile_origin")

    if success:
        success_msg = await message.answer("Успешно ✅")

        success_msg_id = success_msg.message_id

        await state.clear()

        await state.update_data(status_msg_id=success_msg_id)

        await show_profile(message, telegram_id, edit_message=None, origin=origin)
    else:
        await state.clear()

        error_msg = await message.answer("❌ Не удалось обновить имя. Попробуйте позже.")

        if origin == "tasks_menu":
            await show_teacher_tasks_menu_message(message)
        else:
            role = await ensure_auth(telegram_id, message)
            await show_main_menu(message, role)

        async def delete_after():
            await asyncio.sleep(2)
            try:
                await error_msg.delete()
            except:
                pass

        await asyncio.create_task(delete_after())


@router.callback_query(F.data == "resubmit_teacher_request")
async def resubmit_teacher_request(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    success = await profile.resubmit_teacher_request(telegram_id)

    if success:
        await callback.message.answer("Успешно ✅\n\nЗапрос на утверждение был отправлен повторно и ожидает подтверждения от администратора.")
    else:
        logger.warning(f"Failed to resubmit teacher request for telegram_id={telegram_id}")
        await answer_and_delete(callback.message, "❌ Не удалось отправить заявку. Попробуйте позже.")
    await callback.answer()


@router.callback_query(F.data == "resubmit_dean_request")
async def resubmit_dean_request(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    success = await profile.resubmit_dean_request(telegram_id)

    if success:
        await callback.message.answer("Успешно ✅\n\nЗапрос на утверждение был отправлен повторно и ожидает подтверждения от администратора.")
    else:
        logger.warning(f"Failed to resubmit dean request for telegram_id={telegram_id}")
        await answer_and_delete(callback.message, "❌ Не удалось отправить заявку. Попробуйте позже.")
    await callback.answer()


@router.callback_query(F.data.regexp(r"^menu_back(?::(.+))?$"))
async def menu_back_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    status_msg_id = data.get("status_msg_id")

    await delete_msg(callback.bot, callback.from_user.id, status_msg_id)
    await state.update_data(status_msg_id=None)

    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    origin = None
    if ":" in callback.data:
        origin = callback.data.split(":", 1)[1]

    await state.clear()

    if origin == "tasks_menu":
        from handlers.tasks_menu import show_teacher_tasks_menu
        await show_teacher_tasks_menu(callback)
    else:
        await show_main_menu(callback, role, edit_message=callback.message)
        await callback.answer()


@router.callback_query(F.data.regexp(r"^dean_manage_credentials(?::(.+))?$"))
async def dean_manage_credentials(callback: CallbackQuery):
    from services.dean_credentials import dean_credentials

    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)

    if not role or role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    origin = None
    if ":" in callback.data:
        origin = callback.data.split(":", 1)[1]

    back_callback = f"menu_profile:{origin}" if origin else "menu_profile"

    has_creds = await dean_credentials.has_credentials(telegram_id)

    if has_creds:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="📧 Изменить email", callback_data="dean_change_email"),
                types.InlineKeyboardButton(text="🔒 Изменить пароль", callback_data="dean_change_password")
            ],
            [types.InlineKeyboardButton(text="🌐 Открыть веб-версию", url=config.WEB_URL)],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]
        ])
        text = (
            "🔐 <b>Управление учетными данными</b>\n\n"
            "У вас уже настроены учетные данные для входа в веб-версию.\n\n"
            "Вы можете изменить email или пароль."
        )
    else:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="➕ Добавить учетные данные", callback_data="dean_add_credentials")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]
        ])
        text = (
            "🔐 <b>Управление учетными данными</b>\n\n"
            "У вас пока не настроены учетные данные для входа в веб-версию.\n\n"
            "Добавьте email (логин) и пароль для доступа к системе через веб-интерфейс."
        )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "dean_add_credentials")
async def dean_add_credentials_start(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)

    if not role or role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    await callback.message.edit_text(
        "📧 <b>Введите email</b>\n\n"
        "Это будет ваш логин для входа в веб-версию.\n"
        "Пример: ivanov@example.com",
        parse_mode="HTML"
    )
    await state.set_state(EditProfile.waiting_for_email)
    await callback.answer()


@router.message(EditProfile.waiting_for_email)
async def dean_process_email(message: Message, state: FSMContext):
    from services.dean_credentials import dean_credentials

    email = message.text.strip()

    if "@" not in email or "." not in email.split("@")[-1]:
        await message.answer("❌ Некорректный email. Попробуйте ещё раз.\nПример: ivanov@example.com")
        return

    data = await state.get_data()
    change_email_mode = data.get("change_email_mode", False)

    if change_email_mode:
        telegram_id = message.from_user.id
        processing_msg = await message.answer("⏳ Изменение email...")

        success, error_msg = await dean_credentials.change_email(telegram_id, email)

        try:
            await processing_msg.delete()
        except Exception:
            pass

        if success:
            keyboard_buttons = [
                [types.InlineKeyboardButton(text="🌐 Открыть веб-версию", url=config.WEB_URL)],
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]
            ]
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

            await message.answer(
                "✅ <b>Email успешно изменён!</b>\n\n"
                f"📧 Новый email: <code>{email}</code>\n\n"
                f"Используйте новый email для входа в веб-версию системы.",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await message.answer(f"❌ Не удалось изменить email:\n{error_msg}")

        await state.clear()
    else:
        await state.update_data(new_email=email)

        await message.answer(
            "🔒 <b>Введите пароль</b>\n\n"
            "Требования к паролю:\n"
            "• Минимум 8 символов\n"
            "• Должен содержать буквы и цифры\n"
            "• Только латинские буквы и цифры",
            parse_mode="HTML"
        )
        await state.set_state(EditProfile.waiting_for_password)


@router.message(EditProfile.waiting_for_password)
async def dean_process_password(message: Message, state: FSMContext):
    import re
    from services.dean_credentials import dean_credentials

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

    data = await state.get_data()
    email = data.get("new_email")
    telegram_id = message.from_user.id

    processing_msg = await message.answer("⏳ Добавление учетных данных...")

    success, error_msg = await dean_credentials.add_credentials(telegram_id, email, password)

    try:
        await processing_msg.delete()
    except Exception:
        pass

    if success:
        keyboard_buttons = [
            [types.InlineKeyboardButton(text="🌐 Открыть веб-версию", url=config.WEB_URL)],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]
        ]
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await message.answer(
            "✅ <b>Учетные данные успешно добавлены!</b>\n\n"
            f"📧 Email: <code>{email}</code>\n\n"
            f"Теперь вы можете войти в веб-версию системы используя эти данные.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await message.answer(f"❌ Не удалось добавить учетные данные:\n{error_msg}")

    await state.clear()


@router.callback_query(F.data == "dean_change_email")
async def dean_change_email_start(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)

    if not role or role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    profile_data = await profile.get_profile(telegram_id)
    current_email = profile_data.get("email", "") if profile_data else ""

    if current_email and not current_email.endswith("@telegram.local"):
        email_text = f"\n\nТекущий email: <code>{current_email}</code>"
    else:
        email_text = ""

    await callback.message.edit_text(
        f"📧 <b>Введите новый email</b>{email_text}\n\n"
        "Это будет ваш новый логин для входа в веб-версию.\n"
        "Пример: ivanov@example.com",
        parse_mode="HTML"
    )
    await state.set_state(EditProfile.waiting_for_email)
    await state.update_data(change_email_mode=True)
    await callback.answer()


@router.callback_query(F.data == "dean_change_password")
async def dean_change_password_start(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)

    if not role or role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    await callback.message.edit_text(
        "🔒 <b>Смена пароля</b>\n\n"
        "Сначала введите ваш текущий пароль для подтверждения:",
        parse_mode="HTML"
    )
    await state.set_state(EditProfile.waiting_for_current_password)
    await callback.answer()


@router.message(EditProfile.waiting_for_current_password)
async def dean_process_current_password(message: Message, state: FSMContext):
    current_password = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    await state.update_data(current_password=current_password)

    await message.answer(
        "🔒 <b>Введите новый пароль</b>\n\n"
        "Требования к паролю:\n"
        "• Минимум 8 символов\n"
        "• Должен содержать буквы и цифры\n"
        "• Только латинские буквы и цифры",
        parse_mode="HTML"
    )
    await state.set_state(EditProfile.waiting_for_new_password)


@router.message(EditProfile.waiting_for_new_password)
async def dean_process_new_password(message: Message, state: FSMContext):
    import re
    from services.dean_credentials import dean_credentials

    new_password = message.text.strip()

    if len(new_password) < 8:
        await message.answer("❌ Пароль слишком короткий. Минимум 8 символов.")
        return

    if not re.match(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$", new_password):
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

    data = await state.get_data()
    current_password = data.get("current_password")
    telegram_id = message.from_user.id

    processing_msg = await message.answer("⏳ Изменение пароля...")

    success, error_msg = await dean_credentials.change_password(telegram_id, current_password, new_password)

    try:
        await processing_msg.delete()
    except Exception:
        pass

    if success:
        keyboard_buttons = [
            [types.InlineKeyboardButton(text="🌐 Открыть веб-версию", url=config.WEB_URL)],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]
        ]
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await message.answer(
            "✅ <b>Пароль успешно изменён!</b>\n\n"
            "Используйте новый пароль для входа в веб-версию системы.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await message.answer(f"❌ Не удалось изменить пароль:\n{error_msg}")

    await state.clear()


@router.callback_query(F.data == "dean_manage_calendar")
async def dean_manage_calendar(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)

    if not role or role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    status = await profile.get_dean_status(telegram_id)
    if status != "active":
        await callback.answer("Доступно только для подтвержденного деканата.", show_alert=True)
        return

    is_connected = await TSUProfile.is_calendar_connected(telegram_id)

    if is_connected:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отключить календарь", callback_data="dean_disconnect_calendar")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]
        ])
        text = (
            "📅 <b>Google Calendar</b>\n\n"
            "✅ Ваш Google Calendar подключен!"
        )
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        auth_url = await TSUProfile.get_calendar_auth_url(telegram_id)

        if auth_url:
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔗 Авторизоваться в Google", url=auth_url)],
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]
            ])
            await callback.message.edit_text(
                "🔐 <b>Авторизация в Google Calendar</b>\n\n"
                "Для синхронизации задач с календарем необходимо авторизоваться в Google. "
                "Нажмите на кнопку ниже, чтобы перейти на страницу авторизации. 👇",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text("❌ Не удалось получить ссылку для авторизации. Попробуйте позже.")

    await callback.answer()
@router.callback_query(F.data == "dean_disconnect_calendar")
async def dean_disconnect_calendar(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)

    if not role or role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    success = await TSUProfile.disconnect_calendar(telegram_id)

    if success:
        await TSUProfile.set_calendar_connected(telegram_id, False)

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]
        ])
        await callback.message.edit_text(
            "✅ <b>Google Calendar отключен</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text("❌ Не удалось отключить календарь. Попробуйте позже.")

    await callback.answer()


@router.callback_query(F.data == "teacher_manage_calendar")
async def teacher_manage_calendar(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)

    if not role or role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    status = await profile.get_teacher_status(telegram_id)
    if status != "active":
        await callback.answer("Доступно только для подтвержденных преподавателей.", show_alert=True)
        return

    is_connected = await TSUProfile.is_calendar_connected(telegram_id)

    if is_connected:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отключить календарь", callback_data="teacher_disconnect_calendar")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]
        ])
        text = (
            "📅 <b>Google Calendar</b>\n\n"
            "✅ Ваш Google Calendar подключен!"
        )
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        auth_url = await TSUProfile.get_calendar_auth_url(telegram_id)

        if auth_url:
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔗 Авторизоваться в Google", url=auth_url)],
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]
            ])
            await callback.message.edit_text(
                "🔐 <b>Авторизация в Google Calendar</b>\n\n"
                "Для синхронизации задач с календарем необходимо авторизоваться в Google. "
                "Нажмите на кнопку ниже, чтобы перейти на страницу авторизации. 👇",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text("❌ Не удалось получить ссылку для авторизации. Попробуйте позже.")

    await callback.answer()


@router.callback_query(F.data == "teacher_disconnect_calendar")
async def teacher_disconnect_calendar(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)

    if not role or role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    success = await TSUProfile.disconnect_calendar(telegram_id)

    if success:
        await TSUProfile.set_calendar_connected(telegram_id, False)

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")]
        ])
        await callback.message.edit_text(
            "✅ <b>Google Calendar отключен</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text("❌ Не удалось отключить календарь. Попробуйте позже.")

    await callback.answer()
