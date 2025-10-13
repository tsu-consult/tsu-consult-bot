from aiogram import types, Router
from aiogram.filters import Command

router = Router()

start_menu = types.InlineKeyboardMarkup(
    inline_keyboard=[
        [
            types.InlineKeyboardButton(text="📝 Регистрация", callback_data="start_register"),
            types.InlineKeyboardButton(text="🔑 Войти", callback_data="start_login")
        ]
    ]
)


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Выберите действие:", reply_markup=start_menu)
