from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from services.profile import profile


async def show_profile(message: Message, telegram_id: int, edit_message: Message | None = None, origin: str | None = None):
    profile_text = await profile.format_profile_text(telegram_id)

    teacher_status = await profile.get_teacher_status(telegram_id)
    dean_status = await profile.get_dean_status(telegram_id)

    status = teacher_status or dean_status

    from services.auth import auth
    role = await auth.get_role(telegram_id)

    back_callback = f"menu_back:{origin}" if origin else "menu_back"

    if status == "pending":
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]
            ]
        )
    elif status == "rejected":
        resubmit_callback = "resubmit_teacher_request" if teacher_status else "resubmit_dean_request"
        edit_callback = f"edit_profile:{origin}" if origin else "edit_profile"
        keyboard_rows = [
            [
                InlineKeyboardButton(text="✏️ Изменить профиль", callback_data=edit_callback),
                InlineKeyboardButton(text="🔄 Отправить заявку повторно", callback_data=resubmit_callback)
            ]
        ]

        credentials_callback = f"dean_manage_credentials:{origin}" if origin else "dean_manage_credentials"
        if role == "dean":
            keyboard_rows.append([InlineKeyboardButton(text="🔐 Учетные данные", callback_data=credentials_callback)])
        keyboard_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    else:
        edit_callback = f"edit_profile:{origin}" if origin else "edit_profile"
        credentials_callback = f"dean_manage_credentials:{origin}" if origin else "dean_manage_credentials"
        keyboard_rows = [
            [InlineKeyboardButton(text="✏️ Изменить профиль", callback_data=edit_callback)]
        ]

        if role == "dean":
            keyboard_rows.append([InlineKeyboardButton(text="🔐 Учетные данные", callback_data=credentials_callback)])
            if status == "active":
                keyboard_rows.append([InlineKeyboardButton(text="📅 Google Calendar", callback_data="dean_manage_calendar")])
        elif role == "teacher":
            if status == "active":
                keyboard_rows.append([InlineKeyboardButton(text="📅 Google Calendar", callback_data="teacher_manage_calendar")])
        keyboard_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    if edit_message:
        await edit_message.edit_text(profile_text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(profile_text, parse_mode="HTML", reply_markup=keyboard)
