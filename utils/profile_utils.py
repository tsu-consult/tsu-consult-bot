from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from services.profile import profile


async def show_profile(message: Message, telegram_id: int, edit_message: Message | None = None):
    profile_text = await profile.format_profile_text(telegram_id)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить профиль", callback_data="edit_profile")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")],
        ]
    )

    if edit_message:
        await edit_message.edit_text(profile_text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(profile_text, parse_mode="HTML", reply_markup=keyboard)
