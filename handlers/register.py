import logging

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from services.auth import TSUAuth
from states.register import RegisterState
from utils.messages import answer_and_delete, edit_step

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "/register")
async def start_registration(message: Message, state: FSMContext):
    auth = TSUAuth()
    telegram_id = message.from_user.id

    auth.telegram_id = telegram_id
    if auth.is_registered(telegram_id):
        await answer_and_delete(message, "✅ Вы уже зарегистрированы и авторизованы.")
        return

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить контакт", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await message.answer(
        "Пожалуйста, поделитесь вашим контактом для регистрации.",
        reply_markup=keyboard
    )
    await state.set_state(RegisterState.waiting_for_contact)


@router.message(RegisterState.waiting_for_contact, F.contact)
async def process_contact(message: Message, state: FSMContext):
    contact = message.contact

    telegram_id = contact.user_id
    phone_number = contact.phone_number
    raw_username = message.from_user.username

    username = raw_username if raw_username.startswith("@") else f"@{raw_username}"

    first_name = contact.first_name or ""
    last_name = contact.last_name or ""

    await state.update_data(
        telegram_id=telegram_id,
        phone_number=phone_number,
        username=username,
        first_name=first_name,
        last_name=last_name
    )

    role_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎓 Студент", callback_data="role_student"),
            InlineKeyboardButton(text="👨‍🏫 Преподаватель", callback_data="role_teacher")
        ]
    ])

    await edit_step(
        message,
        state,
        "Выберите вашу роль:",
        keyboard=role_keyboard
    )
    await state.set_state(RegisterState.waiting_for_role)


@router.callback_query(RegisterState.waiting_for_role, F.data.startswith("role_"))
async def process_role_selection(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    role = callback.data.split("_")[1]

    telegram_id = data["telegram_id"]
    username = data["username"]
    first_name = data["first_name"]
    last_name = data["last_name"]
    phone_number = data["phone_number"]

    auth = TSUAuth()

    logger.info(
        "Register attempt: telegram_id=%s | username=%s | phone=%s | role=%s",
        telegram_id, username, phone_number, role
    )

    try:
        result = auth.register(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            role=role
        )
    except Exception as e:
        logger.error("Registration error: %s", e)
        await answer_and_delete(callback.message, "❌ Ошибка при регистрации. Попробуйте позже.")
        await state.clear()
        return

    if result:
        await edit_step(callback.message, state, "✅ Регистрация прошла успешно!")
    else:
        await answer_and_delete(callback.message, "❌ Ошибка при регистрации. Попробуйте позже.")

    await state.clear()


@router.message(RegisterState.waiting_for_contact)
async def invalid_contact(message: Message):
    await message.answer("Пожалуйста, нажмите кнопку «📱 Отправить контакт».")
