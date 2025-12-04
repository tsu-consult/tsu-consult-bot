from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from services.profile import profile


async def show_profile(message: Message, telegram_id: int, edit_message: Message | None = None):
    profile_text = await profile.format_profile_text(telegram_id)

    teacher_status = await profile.get_teacher_status(telegram_id)
    dean_status = await profile.get_dean_status(telegram_id)

    status = teacher_status or dean_status

    from services.auth import auth
    role = await auth.get_role(telegram_id)

    if status == "pending":
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")]
            ]
        )
    elif status == "rejected":
        resubmit_callback = "resubmit_teacher_request" if teacher_status else "resubmit_dean_request"
        keyboard_rows = [
            [
                InlineKeyboardButton(text="✏️ Изменить профиль", callback_data="edit_profile"),
                InlineKeyboardButton(text="🔄 Отправить заявку повторно", callback_data=resubmit_callback)
            ]
        ]

        if role == "dean":
            keyboard_rows.append([InlineKeyboardButton(text="🔐 Учетные данные", callback_data="dean_manage_credentials")])
        keyboard_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    else:
        keyboard_rows = [
            [InlineKeyboardButton(text="✏️ Изменить профиль", callback_data="edit_profile")]
        ]

        if role == "dean":
            keyboard_rows.append([InlineKeyboardButton(text="🔐 Учетные данные", callback_data="dean_manage_credentials")])
        keyboard_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    if edit_message:
        await edit_message.edit_text(profile_text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(profile_text, parse_mode="HTML", reply_markup=keyboard)
