from aiogram import Router, types, F

from keyboards.main_keyboard import show_main_menu
from services.api.profile_api import profile
from services.auth import auth

router = Router()


@router.callback_query(F.data == "menu_profile")
async def menu_profile_handler(callback: types.CallbackQuery):
    telegram_id = callback.from_user.id

    profile_text = await profile.format_profile_text(telegram_id)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="✏️ Изменить профиль", callback_data="edit_profile")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")],
        ]
    )

    await callback.message.edit_text(profile_text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "menu_back")
async def menu_back_handler(callback: types.CallbackQuery):
    telegram_id = callback.from_user.id

    role = await auth.get_role(telegram_id)

    await show_main_menu(callback.message, role, edit_message=callback.message)
    await callback.answer()