from datetime import datetime

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from handlers.student_and_teacher import show_requests_page
from keyboards.main_keyboard import show_main_menu
from services.consultations import consultations
from states.create_consultation import CreateConsultationFSM
from utils.auth_utils import ensure_auth
from utils.consultations_utils import format_date_verbose
from utils.messages import answer_and_delete
import asyncio

router = Router()

PAGE_SIZE = 3


async def show_cancel_page(callback: CallbackQuery, telegram_id: int, page: int):
    page_data = await consultations.get_consultations(telegram_id, page=page, page_size=PAGE_SIZE, is_closed=False)
    results = page_data.get("results", [])
    current_page = page_data.get("current_page", page)
    total_pages = max(page_data.get("total_pages", 1), 1)

    text = f"Выберите консультацию, которую хотите отменить 👇\n\nСтраница {current_page} из {total_pages}"

    keyboard_rows: list[list[InlineKeyboardButton]] = []
    for c in results:
        title = c.get("title", "Без названия")
        date_iso = c.get("date")
        date_human = format_date_verbose(date_iso) if date_iso else "—"
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{title} ({date_human})",
                callback_data=f"teacher_choose_cancel_{c['id']}_{current_page}"
            )
        ])

    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"teacher_cancel_consultation_{current_page - 1}"
        ))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"teacher_cancel_consultation_{current_page + 1}"
        ))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "teacher_cancel_consultation")
async def teacher_start_cancel_consultation(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    await show_cancel_page(callback, telegram_id, page=1)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_cancel_consultation_(\d+)$"))
async def teacher_cancel_consultation_paginate(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    page = int(callback.data.split("_")[-1])
    await show_cancel_page(callback, telegram_id, page=page)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_choose_cancel_(\d+)_(\d+)$"))
async def teacher_choose_cancel(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    parts = callback.data.split("_")
    consultation_id = int(parts[-2])
    page = int(parts[-1])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить отмену", callback_data=f"teacher_confirm_cancel_{consultation_id}_{page}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"teacher_cancel_consultation_{page}")]
    ])

    try:
        await callback.message.edit_text(
            "Вы уверены, что хотите отменить эту консультацию?",
            reply_markup=keyboard
        )
    except TelegramBadRequest:
        await callback.message.answer(
            "Вы уверены, что хотите отменить эту консультацию?",
            reply_markup=keyboard
        )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_confirm_cancel_(\d+)_(\d+)$"))
async def teacher_confirm_cancel(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    parts = callback.data.split("_")
    consultation_id = int(parts[-2])
    page = int(parts[-1])

    result = await consultations.cancel_consultation(telegram_id, consultation_id)

    if result == "success":
        await callback.message.edit_text("✅ Консультация успешно отменена.")
        await show_main_menu(callback, role)
    else:
        await asyncio.sleep(0)
        await show_cancel_page(callback, telegram_id, page=page)
        await callback.answer("❌ Не удалось отменить консультацию. Попробуйте позже.", show_alert=True)
        return

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "teacher_create_consultation")
async def start_create_consultation(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    await state.clear()
    await state.set_state(CreateConsultationFSM.waiting_for_title)

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

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
    except ValueError:
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
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    await state.clear()

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    asyncio.create_task(answer_and_delete(callback.message, "❌ Создание консультации отменено.", delay=5))

    await show_main_menu(callback, role)
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

    source_request_id = data.get("source_request_id")
    if source_request_id:
        result = await consultations.create_consultation_from_request(
            telegram_id=telegram_id,
            request_id=source_request_id,
            title=title,
            date=date,
            start_time=start_time,
            end_time=end_time,
            max_students=max_students
        )
    else:
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
        await show_main_menu(callback, role)
    else:
        await callback.message.edit_text("❌ Не удалось создать консультацию. Попробуйте позже.")

    await state.clear()
    await callback.answer()


async def show_close_page(callback: CallbackQuery, telegram_id: int, page: int):
    page_data = await consultations.get_consultations(telegram_id, page=page, page_size=PAGE_SIZE, is_closed=False)
    results = page_data.get("results", [])
    current_page = page_data.get("current_page", page)
    total_pages = max(page_data.get("total_pages", 1), 1)

    text = f"Выберите консультацию, которую хотите закрыть для записи 👇\n\nСтраница {current_page} из {total_pages}"

    keyboard_rows: list[list[InlineKeyboardButton]] = []
    for c in results:
        title = c.get("title", "Без названия")
        date_iso = c.get("date")
        date_human = format_date_verbose(date_iso) if date_iso else "—"
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{title} ({date_human})",
                callback_data=f"teacher_choose_close_{c['id']}_{current_page}"
            )
        ])

    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"teacher_close_consultation_{current_page - 1}"
        ))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"teacher_close_consultation_{current_page + 1}"
        ))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "teacher_close_consultation")
async def teacher_start_close_consultation(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    await show_close_page(callback, telegram_id, page=1)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_close_consultation_(\d+)$"))
async def teacher_close_consultation_paginate(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    page = int(callback.data.split("_")[-1])
    await show_close_page(callback, telegram_id, page=page)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_choose_close_(\d+)_(\d+)$"))
async def teacher_choose_close(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    parts = callback.data.split("_")
    consultation_id = int(parts[-2])
    page = int(parts[-1])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Подтвердить закрытие", callback_data=f"teacher_confirm_close_{consultation_id}_{page}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"teacher_close_consultation_{page}")],
    ])

    try:
        await callback.message.edit_text(
            "Вы уверены, что хотите закрыть запись на эту консультацию?",
            reply_markup=keyboard
        )
    except TelegramBadRequest:
        await callback.message.answer(
            "Вы уверены, что хотите закрыть запись на эту консультацию?",
            reply_markup=keyboard
        )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_confirm_close_(\d+)_(\d+)$"))
async def teacher_confirm_close(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    parts = callback.data.split("_")
    consultation_id = int(parts[-2])
    page = int(parts[-1])

    result = await consultations.close_consultation(telegram_id, consultation_id)

    if result == "success":
        await callback.message.edit_text("🔒 Запись на консультацию закрыта.")
        await show_main_menu(callback, role)
    else:
        await show_close_page(callback, telegram_id, page=page)
        await callback.answer("❌ Не удалось закрыть запись. Попробуйте позже.", show_alert=True)
        return

    await callback.answer()

@router.callback_query(F.data == "teacher_requests")
async def teacher_view_requests(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    await show_requests_page(callback, telegram_id, role, page=1)