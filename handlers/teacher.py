from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from services.consultations import consultations
from states.create_consultation import CreateConsultationFSM
from utils.auth_utils import ensure_auth
from utils.consultations_utils import format_date_verbose

router = Router()


@router.callback_query(F.data == "teacher_create_consultation")
async def start_create_consultation(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    await state.clear()
    await state.set_state(CreateConsultationFSM.waiting_for_title)
    await callback.message.answer("Введите тему консультации 👇")
    await callback.answer()


@router.message(CreateConsultationFSM.waiting_for_title)
async def handle_consultation_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("❗ Пожалуйста, введите тему консультации.")
        return

    await state.update_data(title=title)
    await state.set_state(CreateConsultationFSM.waiting_for_date)
    await message.answer("Введите дату в формате ДД-ММ-ГГГГ (например, 16-10-2025) 👇")


@router.message(CreateConsultationFSM.waiting_for_date)
async def handle_consultation_date(message: Message, state: FSMContext):
    date_input = (message.text or "").strip()
    try:
        dt = datetime.strptime(date_input, "%d-%m-%Y")
        if dt.date() < datetime.now().date():
            await message.answer("❗ Дата в прошлом. Введите будущую дату в формате ДД-ММ-ГГГГ.")
            return
    except ValueError:
        await message.answer("❗ Неверный формат. Введите дату как ДД-ММ-ГГГГ (например, 16-10-2025).")
        return

    date_iso = dt.strftime("%Y-%m-%d")
    await state.update_data(date=date_iso)
    await state.set_state(CreateConsultationFSM.waiting_for_start_time)
    await message.answer("Введите время начала в формате ЧЧ:ММ (например, 10:00) 👇")


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.strptime(value.strip(), "%H:%M")
    except Exception:
        return None


@router.message(CreateConsultationFSM.waiting_for_start_time)
async def handle_consultation_start_time(message: Message, state: FSMContext):
    start_time = (message.text or "").strip()
    start_dt = _parse_time(start_time)
    if not start_dt:
        await message.answer("❗ Неверный формат. Введите время начала как ЧЧ:ММ (например, 10:00).")
        return

    await state.update_data(start_time=start_time)
    await state.set_state(CreateConsultationFSM.waiting_for_end_time)
    await message.answer("Введите время окончания в формате ЧЧ:ММ (например, 11:00) 👇")


@router.message(CreateConsultationFSM.waiting_for_end_time)
async def handle_consultation_end_time(message: Message, state: FSMContext):
    end_time = (message.text or "").strip()
    end_dt = _parse_time(end_time)
    data = await state.get_data()
    start_time = data.get("start_time")
    start_dt = _parse_time(start_time) if start_time else None

    if not end_dt or not start_dt:
        await message.answer("❗ Неверный формат времени. Повторите ввод времени окончания как ЧЧ:ММ.")
        return

    if end_dt <= start_dt:
        await message.answer("❗ Время окончания должно быть позже времени начала. Введите снова (ЧЧ:ММ).")
        return

    await state.update_data(end_time=end_time)
    await state.set_state(CreateConsultationFSM.waiting_for_max_students)
    await message.answer("Введите максимальное число студентов (целое число от 1 до 100) 👇")


@router.message(CreateConsultationFSM.waiting_for_max_students)
async def handle_consultation_max_students(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("❗ Введите целое число от 1 до 100.")
        return
    value = int(text)
    if not (1 <= value <= 100):
        await message.answer("❗ Число должно быть в диапазоне 1–100. Попробуйте снова.")
        return

    await state.update_data(max_students=value)
    data = await state.get_data()

    summary = (
        "Проверьте данные консультации:\n\n"
        f"📌 Тема: {data['title']}\n"
        f"📅 Дата: {format_date_verbose(data['date'])}\n"
        f"⏰ Время: {data['start_time']}–{data['end_time']}\n"
        f"👥 Лимит мест: {data['max_students']}\n\n"
        "Создать консультацию?"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_create_consultation")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_create_consultation")]
    ])

    await state.set_state(CreateConsultationFSM.confirming)
    await message.answer(summary, reply_markup=keyboard)


@router.callback_query(F.data == "cancel_create_consultation")
async def cancel_create_consultation(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Создание консультации отменено.")
    await callback.answer()


@router.callback_query(F.data == "confirm_create_consultation")
async def confirm_create_consultation(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    data = await state.get_data()
    title = data.get("title")
    date = data.get("date")
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    max_students = data.get("max_students")

    result = await consultations.create_consultation(
        telegram_id=telegram_id,
        title=title,
        date=date,
        start_time=start_time,
        end_time=end_time,
        max_students=max_students
    )

    if result:
        await callback.message.edit_text("✅ Консультация успешно создана!")
    else:
        await callback.message.edit_text("❌ Не удалось создать консультацию. Попробуйте позже.")

    await state.clear()
    await callback.answer()
