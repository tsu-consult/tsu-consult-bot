import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards.main_keyboard import show_main_menu
from services.profile import profile
from states.edit_profile import EditProfile
from utils.auth_utils import ensure_auth
from utils.messages import answer_and_delete, delete_msg
from utils.profile_utils import show_profile

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "menu_profile")
async def menu_profile_handler(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    await show_profile(callback.message, telegram_id, edit_message=callback.message)
    await callback.answer()


@router.callback_query(F.data == "edit_profile")
async def edit_profile_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новое имя и фамилию 👇\n\nПример: <b>Иван Иванов</b>\n\n⚠️ Внимание! Указывайте реальные имена и фамилии", parse_mode="HTML")
    await state.set_state(EditProfile.name)
    await callback.answer()
@router.message(EditProfile.name)
async def edit_profile_name(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    new_name = message.text.strip()

    parts = new_name.split(maxsplit=1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    success = await profile.update_profile(telegram_id, first_name, last_name)
    success_msg = None

    if success:
        success_msg = await message.answer("Успешно ✅")
    else:
        await answer_and_delete(message, "❌ Не удалось обновить имя. Попробуйте позже.")

    await state.update_data(status_msg_id=success_msg.message_id)

    await show_profile(message, telegram_id)


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


@router.callback_query(F.data == "menu_back")
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

    await state.clear()
    await show_main_menu(callback.message, role, edit_message=callback.message)
    await callback.answer()