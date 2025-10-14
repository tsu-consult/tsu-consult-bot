from aiogram import types, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from handlers import register
from keyboards.main import guest_menu

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Привет!\n\nЧтобы продолжить, зарегистрируйтесь или войдите в систему:", reply_markup=guest_menu)

@router.callback_query(lambda c: c.data == "start")
async def start_register_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await register.start_registration(callback.message, state)
    await callback.answer()
