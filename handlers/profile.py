from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from keyboards.main_keyboard import show_main_menu
from services.profile import profile
from utils.auth_utils import ensure_auth

router = Router()


@router.callback_query(F.data == "menu_profile")
async def menu_profile_handler(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback, state)
    if not role:
        await callback.answer()
        return

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
async def menu_back_handler(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback, state)
    if not role:
        await callback.answer()
        return

    await show_main_menu(callback.message, role, edit_message=callback.message)
    await callback.answer()