from aiogram import types, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from handlers import register

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

@router.callback_query(lambda c: c.data == "start_register")
async def start_register_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await register.start_registration(callback.message, state)
    await callback.answer()
