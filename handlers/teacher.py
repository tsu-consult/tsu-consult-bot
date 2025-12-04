import asyncio
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from handlers.student_and_teacher import show_requests_page
from keyboards.main_keyboard import show_main_menu
from services.consultations import consultations
from services.profile import profile
from services.tasks import tasks_service
from states.create_consultation import CreateConsultationFSM
from states.update_task import UpdateTaskFSM
from utils.auth_utils import ensure_auth
from utils.consultations_utils import format_date_verbose
from utils.messages import answer_and_delete
router = Router()

PAGE_SIZE = 3


async def show_cancel_page(callback: CallbackQuery, telegram_id: int, page: int):
    page_data = await consultations.get_consultations(telegram_id, page=page, page_size=PAGE_SIZE)
    results = page_data.get("results", [])
    current_page = page_data.get("current_page", page)
    total_pages = max(page_data.get("total_pages", 1), 1)

    if not results:
        text = "Сейчас у вас нет активных консультаций, которые можно отменить."
    else:
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
    if results and current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"teacher_cancel_consultation_{current_page - 1}"
        ))
    if results and current_page < total_pages:
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
        await callback.answer("❌ Не удалось отменить консультацию. Возможно, она уже отмененна. Попробуйте позже.", show_alert=True)
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

    await asyncio.create_task(answer_and_delete(callback.message, "❌ Создание консультации отменено.", delay=5))

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

    if not results:
        text = "Сейчас у вас нет консультаций, доступных для закрытия записи."
    else:
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
    if results and current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"teacher_close_consultation_{current_page - 1}"
        ))
    if results and current_page < total_pages:
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


@router.callback_query(F.data == "teacher_view_tasks")
async def view_teacher_tasks_first_page(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    await show_teacher_tasks_page(callback, telegram_id, page=1)


@router.callback_query(F.data.regexp(r"^teacher_tasks_page_(\d+)$"))
async def paginate_teacher_tasks(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    page = int(callback.data.split("_")[-1])
    await show_teacher_tasks_page(callback, telegram_id, page=page)


async def show_teacher_tasks_page(callback: CallbackQuery, telegram_id: int, page: int):
    from services.tasks import tasks_service

    tasks_data = await tasks_service.get_tasks(telegram_id, page=page, page_size=PAGE_SIZE)

    results = tasks_data.get("results", [])
    results = [task for task in results if task.get("status") not in ["deleted", "cancelled", "archived"]]

    current_page = tasks_data.get("current_page", page)
    total_pages = max(tasks_data.get("total_pages", 1), 1)

    if not results:
        text = "📋 У вас пока нет назначенных задач."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
        ])
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
        return

    text_lines = [f"📋 <b>Мои задачи — страница {current_page} из {total_pages}</b>\n"]

    for task in results:
        title = task.get("title", "Без названия")
        status = task.get("status", "unknown")

        status_text_map = {
            "in_progress": "В процессе",
            "in progress": "В процессе",
            "active": "В процессе",
            "completed": "Выполнено",
            "pending": "Ожидает",
            "deleted": "Удалена",
            "cancelled": "Отменена",
            "archived": "Архивирована"
        }
        status_text = status_text_map.get(status, status.title() if status != 'unknown' else 'Неизвестно')

        deadline = task.get("deadline")
        if deadline:
            try:
                dt_utc = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
                tomsk_tz = timezone(timedelta(hours=7))
                dt_local = dt_utc.astimezone(tomsk_tz)
                deadline_text = dt_local.strftime("%d.%m.%Y %H:%M")
            except:
                deadline_text = "—"
        else:
            deadline_text = "—"

        text_lines.append(
            f"\n<b>{title}</b>\n"
            f"📊 Статус: {status_text}\n"
            f"📅 Дедлайн: {deadline_text}"
        )

    keyboard_rows = []

    keyboard_rows.append([
        InlineKeyboardButton(
            text="📝 Просмотреть подробнее",
            callback_data=f"teacher_choose_task_{current_page}"
        )
    ])

    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"teacher_tasks_page_{current_page - 1}"
        ))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"teacher_tasks_page_{current_page + 1}"
        ))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        await callback.message.answer(
            "\n".join(text_lines),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_choose_task_(\d+)$"))
async def choose_teacher_task_for_details(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    page = int(callback.data.split("_")[-1])
    await show_teacher_task_selection_page(callback, telegram_id, page=page)


async def show_teacher_task_selection_page(callback: CallbackQuery, telegram_id: int, page: int):
    tasks_data = await tasks_service.get_tasks(telegram_id, page=page, page_size=PAGE_SIZE)

    results = tasks_data.get("results", [])
    results = [task for task in results if task.get("status") not in ["deleted", "cancelled", "archived"]]

    current_page = tasks_data.get("current_page", page)
    total_pages = max(tasks_data.get("total_pages", 1), 1)

    if not results:
        await callback.answer("❌ Нет доступных задач", show_alert=True)
        return

    text = f"📋 <b>Выберите задачу для подробного просмотра</b>\n\nСтраница {current_page} из {total_pages}"

    keyboard_rows = []

    for task in results:
        title = task.get("title", "Без названия")

        keyboard_rows.append([
            InlineKeyboardButton(
                text=title,
                callback_data=f"teacher_task_detail_{task['id']}_{current_page}"
            )
        ])

    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"teacher_choose_task_{current_page - 1}"
        ))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"teacher_choose_task_{current_page + 1}"
        ))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 К списку задач", callback_data=f"teacher_tasks_page_{current_page}")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


async def _show_teacher_task_detail(callback: CallbackQuery, telegram_id: int, task_id: int, page: int):
    from services.tasks import tasks_service

    task = await tasks_service.get_task_details(telegram_id, task_id)

    if not task:
        await callback.answer("❌ Не удалось загрузить задачу", show_alert=True)
        return

    title = task.get("title", "Без названия")
    description = task.get("description", "Нет описания")
    status = task.get("status", "unknown")
    status_text_map = {
        "in progress": "В процессе",
        "active": "В процессе",
        "completed": "Выполнено",
        "pending": "Ожидает",
        "deleted": "Удалена",
        "cancelled": "Отменена",
        "archived": "Архивирована"
    }
    status_text = status_text_map.get(status, status.title() if status != 'unknown' else 'Неизвестно')

    deadline = task.get("deadline")
    if deadline:
        try:
            dt_utc = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
            tomsk_tz = timezone(timedelta(hours=7))
            dt_local = dt_utc.astimezone(tomsk_tz)
            deadline_text = dt_local.strftime("%d.%m.%Y %H:%M")
        except:
            deadline_text = "—"
    else:
        deadline_text = "Не указан"

    creator = task.get("creator")
    if creator:
        creator_name = f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
    else:
        creator_name = "Не указан"

    assignee = task.get("assignee")
    assignee_id = assignee.get("id") if assignee else None
    creator_id = creator.get("id") if creator else None

    user_reminders = task.get("assignee_reminders", []) if assignee_id else task.get("reminders", [])

    text_lines = [f"<b>{title}</b>"]

    if description and description != "Нет описания":
        text_lines.append(f"📝 {description}")

    text_lines.append(f"📊 {status_text}")
    text_lines.append(f"📅 Дедлайн: {deadline_text}")
    text_lines.append(f"👤 Автор: {creator_name}")

    if assignee_id and assignee_id != creator_id:
        assignee_name = f"{assignee.get('first_name', '')} {assignee.get('last_name', '')}".strip()
        text_lines.append(f"👨‍🏫 Назначен: {assignee_name}")

    if deadline:
        reminders = user_reminders
        if reminders:
            reminder_texts = []
            for reminder in reminders:
                minutes = reminder.get("minutes", 0)
                if minutes == 15:
                    reminder_texts.append("за 15 минут")
                elif minutes == 30:
                    reminder_texts.append("за 30 минут")
                elif minutes == 60:
                    reminder_texts.append("за 1 час")
                elif minutes == 1440:
                    reminder_texts.append("за 1 день")
                else:
                    reminder_texts.append(f"за {minutes} минут")
            text_lines.append(f"🔔 {', '.join(reminder_texts)}")
        else:
            text_lines.append("🔕 Напоминания отключены")

    text = "\n".join(text_lines)

    user_profile = await profile.get_profile(telegram_id)
    user_id = user_profile.get("id") if user_profile else None

    edit_delete_row = [
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"teacher_edit_task_{task_id}_{page}")
    ]

    if user_id == creator_id:
        edit_delete_row.append(
            InlineKeyboardButton(text="🗑 Удалить задачу", callback_data=f"teacher_delete_task_{task_id}_{page}")
        )

    keyboard_rows = [
        edit_delete_row,
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"teacher_choose_task_{page}"),
            InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")
        ]
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_task_detail_(\d+)_(\d+)$"))
async def view_teacher_task_detail(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступ запрещен.", show_alert=True)
        return

    parts = callback.data.split("_")
    task_id = int(parts[-2])
    page = int(parts[-1])

    await _show_teacher_task_detail(callback, telegram_id, task_id, page)


@router.callback_query(F.data.regexp(r"^teacher_edit_task_(\d+)_(\d+)$"))
async def edit_task_menu(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    parts = callback.data.split("_")
    task_id = int(parts[-2])
    page = int(parts[-1])

    task = await tasks_service.get_task_details(telegram_id, task_id)

    if not task:
        await callback.answer("❌ Не удалось загрузить задачу", show_alert=True)
        return

    user_profile = await profile.get_profile(telegram_id)
    user_id = user_profile.get("id") if user_profile else None
    creator = task.get("creator")
    creator_id = creator.get("id") if creator else None
    is_creator = (user_id == creator_id)

    await state.update_data(task_id=task_id, page=page, task=task, is_creator=is_creator)

    text = "✏️ <b>Выберите, что вы хотите изменить:</b>"

    keyboard_rows = [
        [InlineKeyboardButton(text="📝 Название", callback_data="teacher_edit_task_title")],
        [InlineKeyboardButton(text="📄 Описание", callback_data="teacher_edit_task_description")],
        [InlineKeyboardButton(text="📊 Статус", callback_data="teacher_edit_task_status")],
        [InlineKeyboardButton(text="📅 Дедлайн", callback_data="teacher_edit_task_deadline")]
    ]

    if task.get("deadline"):
        keyboard_rows.append([InlineKeyboardButton(text="🔔 Напоминания", callback_data="teacher_edit_task_reminders")])

    keyboard_rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"teacher_task_detail_{task_id}_{page}"),
        InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data == "teacher_edit_task_title")
async def edit_task_title_start(callback: CallbackQuery, state: FSMContext):
    from states.update_task import UpdateTaskFSM

    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    data = await state.get_data()
    is_creator = data.get("is_creator", False)

    if not is_creator:
        await callback.answer("❌ Только создатель может редактировать название задачи.", show_alert=True)
        return

    await state.set_state(UpdateTaskFSM.waiting_for_title)

    text = "✏️ Введите новое название задачи:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="teacher_cancel_edit_task")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data == "teacher_edit_task_description")
async def edit_task_description_start(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    data = await state.get_data()
    is_creator = data.get("is_creator", False)
    task = data.get("task")

    if not is_creator:
        await callback.answer("❌ Только создатель может редактировать описание задачи.", show_alert=True)
        return

    await state.set_state(UpdateTaskFSM.waiting_for_description)

    text = "✏️ Введите новое описание задачи:"

    keyboard_rows = []

    if task and task.get("description"):
        keyboard_rows.append([InlineKeyboardButton(text="🗑️ Убрать описание", callback_data="teacher_remove_description")])

    keyboard_rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="teacher_cancel_edit_task")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data == "teacher_edit_task_status")
async def edit_task_status_start(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    await state.set_state(UpdateTaskFSM.waiting_for_status)

    text = "✏️ Выберите новый статус задачи:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 В процессе", callback_data="teacher_set_status_in_progress")],
        [InlineKeyboardButton(text="✅ Выполнено", callback_data="teacher_set_status_completed")],
        [InlineKeyboardButton(text="⏳ Ожидает", callback_data="teacher_set_status_pending")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="teacher_cancel_edit_task")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_set_status_(.+)$"))
async def edit_task_status_process(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    status = callback.data.replace("teacher_set_status_", "")

    status_map = {
        "in_progress": "in progress",
        "completed": "completed",
        "pending": "pending"
    }

    status_text_map = {
        "in_progress": "В процессе",
        "completed": "Выполнено",
        "pending": "Ожидает"
    }

    api_status = status_map.get(status, status)
    status_text = status_text_map.get(status, status)

    data = await state.get_data()
    task_id = data.get("task_id")
    page = data.get("page")

    result = await tasks_service.update_task(telegram_id, task_id, status=api_status)

    if result:
        text = f"✅ Статус задачи успешно изменен на: <b>{status_text}</b>"
    else:
        text = "❌ Не удалось обновить задачу. Попробуйте позже."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"teacher_task_detail_{task_id}_{page}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "teacher_edit_task_deadline")
async def edit_task_deadline_start(callback: CallbackQuery, state: FSMContext):
    from states.update_task import UpdateTaskFSM

    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    data = await state.get_data()
    task = data.get("task")

    await state.set_state(UpdateTaskFSM.waiting_for_deadline_date)

    text = "📅 Введите новую дату дедлайна в формате ДД.ММ.ГГГГ (например, 25.12.2025):"

    keyboard_rows = []

    if task and task.get("deadline"):
        keyboard_rows.append([InlineKeyboardButton(text="🗑️ Отменить дедлайн", callback_data="teacher_remove_deadline")])

    keyboard_rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="teacher_cancel_edit_task")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.message(UpdateTaskFSM.waiting_for_deadline_time)
async def edit_task_deadline_time_process(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    role = await ensure_auth(telegram_id, message)
    if role != "teacher" and role != "dean":
        await message.answer("Доступно только для преподавателей и деканата.")
        return

    if not message.text:
        await message.answer("❗ Пожалуйста, введите текст.")
        return

    time_input = message.text.strip()
    data = await state.get_data()
    deadline_date = data.get("deadline_date")
    task_id = data.get("task_id")
    page = data.get("page")

    if not deadline_date or not task_id or page is None:
        await message.answer("❗ Ошибка: не удалось получить данные. Попробуйте начать заново.")
        await state.clear()
        return

    try:
        local_dt = datetime.strptime(f"{deadline_date} {time_input}", "%Y-%m-%d %H:%M")

        tomsk_tz = timezone(timedelta(hours=7))
        local_dt = local_dt.replace(tzinfo=tomsk_tz)

        current_time_tomsk = datetime.now(timezone.utc).astimezone(tomsk_tz)

        if local_dt <= current_time_tomsk:
            prefix = "teacher" if role == "teacher" else "dean"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data=f"{prefix}_cancel_edit_task")]
            ])
            current_formatted = current_time_tomsk.strftime("%d.%m.%Y %H:%M")
            deadline_formatted = local_dt.strftime("%d.%m.%Y %H:%M")
            await message.answer(
                f"❗ Дедлайн не может быть в прошлом или настоящем.\n\n"
                f"Текущее время (Томск): {current_formatted}\n"
                f"Указанный дедлайн: {deadline_formatted}\n\n"
                f"Введите будущую дату и время.",
                reply_markup=keyboard
            )
            return

        utc_dt = local_dt.astimezone(timezone.utc)
        deadline_iso = utc_dt.isoformat()

        result = await tasks_service.update_task(telegram_id, task_id, deadline=deadline_iso)

        if result:
            text = f"✅ Дедлайн задачи успешно обновлен на: 📅 {local_dt.strftime('%d.%m.%Y')} в ⏰ {time_input}"
        else:
            text = "❌ Не удалось обновить задачу. Попробуйте позже."

        prefix = "teacher" if role == "teacher" else "dean"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"{prefix}_task_detail_{task_id}_{page}")],
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
        ])

        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()
    except ValueError:
        text = "❌ Неверный формат времени. Используйте формат ЧЧ:ММ (например, 23:59)."
        prefix = "teacher" if role == "teacher" else "dean"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"{prefix}_cancel_edit_task")]
        ])
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "teacher_edit_task_reminders")
async def edit_task_reminders_start(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    await state.set_state(UpdateTaskFSM.waiting_for_reminders_choice)

    text = "Выберите настройку напоминаний 👇\n\n" \
           "• Настроить: выбрать свои варианты напоминаний\n" \
           "• Без напоминаний: уведомления не будут отправляться"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Настроить напоминания", callback_data="teacher_reminder_custom")],
        [InlineKeyboardButton(text="🔕 Без напоминаний", callback_data="teacher_reminder_none")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="teacher_cancel_edit_task")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data == "teacher_reminder_none")
async def teacher_edit_task_reminders_none(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    data = await state.get_data()
    task_id = data.get("task_id")
    page = data.get("page")

    result = await tasks_service.update_task(telegram_id, task_id, reminders=[])

    if result:
        text = "✅ Напоминания отключены"
    else:
        text = "❌ Не удалось обновить задачу. Попробуйте позже."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"teacher_task_detail_{task_id}_{page}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "teacher_reminder_custom")
async def teacher_edit_task_reminders_custom(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    await state.update_data(selected_reminders=[])
    await state.set_state(UpdateTaskFSM.waiting_for_custom_reminders)
    await teacher_show_reminders_selection(callback, state)
    await callback.answer()


async def teacher_show_reminders_selection(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_reminders = data.get("selected_reminders", [])

    reminder_options = [
        (15, "15 минут"),
        (30, "30 минут"),
        (60, "1 час"),
        (1440, "1 день")
    ]

    keyboard_rows = []

    for minutes, label in reminder_options:
        is_selected = minutes in selected_reminders
        button_text = f"{'✅' if is_selected else '⬜'} За {label}"
        keyboard_rows.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"teacher_reminder_toggle_{minutes}"
            )
        ])

    if selected_reminders:
        keyboard_rows.append([
            InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="teacher_reminder_confirm")
        ])

    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="teacher_reminder_back")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    selected_count = len(selected_reminders)
    text = "Выберите время для напоминаний 👇\n\n"
    if selected_count > 0:
        text += f"Выбрано: {selected_count}\n\n"
    text += "Вы можете выбрать несколько вариантов"

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.regexp(r"^teacher_reminder_toggle_(\d+)$"), UpdateTaskFSM.waiting_for_custom_reminders)
async def teacher_handle_reminder_toggle(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    minutes = int(callback.data.split("_")[-1])

    data = await state.get_data()
    selected_reminders = data.get("selected_reminders", [])

    if minutes in selected_reminders:
        selected_reminders.remove(minutes)
    else:
        selected_reminders.append(minutes)

    await state.update_data(selected_reminders=selected_reminders)
    await teacher_show_reminders_selection(callback, state)
    await callback.answer()


@router.callback_query(F.data == "teacher_reminder_confirm", UpdateTaskFSM.waiting_for_custom_reminders)
async def teacher_handle_reminder_confirm(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    data = await state.get_data()
    selected_reminders = data.get("selected_reminders", [])
    task_id = data.get("task_id")
    page = data.get("page")

    if not selected_reminders:
        await callback.answer("❗ Выберите хотя бы одно напоминание", show_alert=True)
        return

    reminders = [{"method": "popup", "minutes": minutes} for minutes in selected_reminders]

    result = await tasks_service.update_task(telegram_id, task_id, reminders=reminders)

    if result:
        reminder_labels = {15: "15 минут", 30: "30 минут", 60: "1 час", 1440: "1 день"}
        reminders_text = ", ".join([f"за {reminder_labels[m]}" for m in sorted(selected_reminders)])
        text = f"✅ Напоминания установлены: {reminders_text}"
    else:
        text = "❌ Не удалось обновить задачу. Попробуйте позже."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"teacher_task_detail_{task_id}_{page}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "teacher_reminder_back", UpdateTaskFSM.waiting_for_custom_reminders)
async def teacher_handle_reminder_back(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    await state.set_state(UpdateTaskFSM.waiting_for_reminders_choice)

    text = "Выберите настройку напоминаний 👇\n\n" \
           "• Настроить: выбрать свои варианты напоминаний\n" \
           "• Без напоминаний: уведомления не будут отправляться"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Настроить напоминания", callback_data="teacher_reminder_custom")],
        [InlineKeyboardButton(text="🔕 Без напоминаний", callback_data="teacher_reminder_none")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="teacher_cancel_edit_task")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data == "teacher_remove_description")
async def teacher_remove_description(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    data = await state.get_data()
    task_id = data.get("task_id")
    page = data.get("page")
    is_creator = data.get("is_creator", False)

    if not is_creator:
        await callback.answer("❌ Только создатель может редактировать описание задачи.", show_alert=True)
        return

    if not task_id or page is None:
        await callback.answer("❌ Ошибка: не удалось определить задачу.", show_alert=True)
        await state.clear()
        return

    result = await tasks_service.update_task(telegram_id, task_id, description="")

    if result:
        text = "✅ Описание задачи успешно удалено"
    else:
        text = "❌ Не удалось обновить задачу. Попробуйте позже."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"teacher_task_detail_{task_id}_{page}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "teacher_remove_deadline")
async def teacher_remove_deadline(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    data = await state.get_data()
    task_id = data.get("task_id")
    page = data.get("page")

    if not task_id or page is None:
        await callback.answer("❌ Ошибка: не удалось определить задачу.", show_alert=True)
        await state.clear()
        return

    result = await tasks_service.update_task(telegram_id, task_id, deadline=None)

    if result:
        text = "✅ Дедлайн задачи успешно отменен"
    else:
        text = "❌ Не удалось обновить задачу. Попробуйте позже."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"teacher_task_detail_{task_id}_{page}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "teacher_cancel_edit_task")
async def cancel_edit_task(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    data = await state.get_data()
    task_id = data.get("task_id")
    page = data.get("page")

    await state.clear()

    if task_id is not None and page is not None:
        await _show_teacher_task_detail(callback, telegram_id, task_id, page)
    else:
        text = "❌ Редактирование отменено"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
        ])
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except TelegramBadRequest:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()


@router.callback_query(F.data == "teacher_delete_task_from_menu")
async def teacher_delete_task_from_main_menu(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    await teacher_show_task_deletion_page(callback, telegram_id, page=1)


@router.callback_query(F.data.regexp(r"^teacher_choose_task_delete_(\d+)$"))
async def teacher_choose_task_for_deletion(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    page = int(callback.data.split("_")[-1])
    await teacher_show_task_deletion_page(callback, telegram_id, page=page)


async def teacher_show_task_deletion_page(callback: CallbackQuery, telegram_id: int, page: int):
    tasks_data = await tasks_service.get_tasks(telegram_id, page=page, page_size=PAGE_SIZE)

    results = tasks_data.get("results", [])
    results = [task for task in results if task.get("status") not in ["deleted", "cancelled", "archived"]]

    current_page = tasks_data.get("current_page", page)
    total_pages = max(tasks_data.get("total_pages", 1), 1)

    if not results:
        await callback.answer("❌ Нет доступных задач для удаления", show_alert=True)
        return

    user_profile = await profile.get_profile(telegram_id)
    user_id = user_profile.get("id") if user_profile else None

    text = f"🗑 <b>Выберите задачу для удаления</b>\n\nСтраница {current_page} из {total_pages}"

    keyboard_rows = []

    for task in results:
        title = task.get("title", "Без названия")
        creator = task.get("creator")
        creator_id = creator.get("id") if creator else None

        if user_id == creator_id:
            keyboard_rows.append([
                InlineKeyboardButton(
                    text=title,
                    callback_data=f"teacher_delete_task_confirm_{task['id']}_{current_page}"
                )
            ])

    if not keyboard_rows:
        await callback.answer("❌ У вас нет задач, которые можно удалить", show_alert=True)
        return

    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"teacher_choose_task_delete_{current_page - 1}"
        ))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"teacher_choose_task_delete_{current_page + 1}"
        ))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 К списку задач", callback_data=f"teacher_tasks_page_{current_page}")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_delete_task_confirm_(\d+)_(\d+)$"))
async def teacher_confirm_task_deletion(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    parts = callback.data.split("_")
    task_id = int(parts[-2])
    page = int(parts[-1])

    task = await tasks_service.get_task_details(telegram_id, task_id)

    if not task:
        await callback.answer("❌ Задача не найдена", show_alert=True)
        return

    user_profile = await profile.get_profile(telegram_id)
    user_id = user_profile.get("id") if user_profile else None
    creator = task.get("creator")
    creator_id = creator.get("id") if creator else None

    if user_id != creator_id:
        await callback.answer("❌ Только создатель может удалить задачу", show_alert=True)
        return

    title = task.get("title", "Без названия")
    text = f"⚠️ <b>Подтверждение удаления</b>\n\nВы уверены, что хотите удалить задачу:\n<b>{title}</b>?"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"teacher_delete_task_{task_id}_{page}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"teacher_task_detail_{task_id}_{page}")
        ]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_delete_task_(\d+)_(\d+)$"))
async def teacher_delete_task(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "teacher":
        await callback.answer("Доступно только для преподавателей.", show_alert=True)
        return

    parts = callback.data.split("_")
    task_id = int(parts[-2])
    page = int(parts[-1])

    task = await tasks_service.get_task_details(telegram_id, task_id)
    if task:
        user_profile = await profile.get_profile(telegram_id)
        user_id = user_profile.get("id") if user_profile else None
        creator = task.get("creator")
        creator_id = creator.get("id") if creator else None

        if user_id != creator_id:
            await callback.answer("❌ Только создатель может удалить задачу", show_alert=True)
            return

    success = await tasks_service.delete_task(telegram_id, task_id)

    if success:
        text = "✅ Задача успешно удалена"
    else:
        text = "❌ Не удалось удалить задачу. Попробуйте позже."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К списку задач", callback_data=f"teacher_tasks_page_{page}")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main_menu")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


