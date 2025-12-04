from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from keyboards.main_keyboard import show_main_menu
from services.tasks import tasks_service
from services.teachers import TSUTeachers
from states.create_task import CreateTaskFSM
from utils.auth_utils import ensure_auth
from utils.messages import answer_and_delete
import asyncio

router = Router()

PAGE_SIZE = 5


@router.callback_query(F.data == "dean_create_task")
async def start_create_task(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    await state.clear()
    await state.set_state(CreateTaskFSM.waiting_for_title)

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    await callback.message.answer("Введите название задачи 👇")
    await callback.answer()


@router.message(CreateTaskFSM.waiting_for_title)
async def handle_task_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("❗ Пожалуйста, введите название задачи.")
        return

    await state.update_data(title=title)
    await state.set_state(CreateTaskFSM.waiting_for_description)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="task_skip_description")]
    ])
    await message.answer("Введите описание задачи 👇", reply_markup=keyboard)


@router.callback_query(F.data == "task_skip_description", CreateTaskFSM.waiting_for_description)
async def skip_task_description(callback: CallbackQuery, state: FSMContext):
    await state.update_data(description="")

    telegram_id = callback.from_user.id
    teachers_data = await TSUTeachers.get_teachers_page(telegram_id, page=0, page_size=PAGE_SIZE)

    if not teachers_data.get("results"):
        await callback.message.answer("❗ Нет доступных подтвержденных преподавателей. Создание задачи отменено.")
        await state.clear()
        await callback.answer()
        return

    await state.update_data(teacher_page=0)
    await state.set_state(CreateTaskFSM.waiting_for_assignee)

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    await show_teacher_selection(callback.message, teachers_data, state)
    await callback.answer()


@router.message(CreateTaskFSM.waiting_for_description)
async def handle_task_description(message: Message, state: FSMContext):
    description = (message.text or "").strip()

    await state.update_data(description=description)

    telegram_id = message.from_user.id
    teachers_data = await TSUTeachers.get_teachers_page(telegram_id, page=0, page_size=PAGE_SIZE)

    if not teachers_data.get("results"):
        await message.answer("❗ Нет доступных подтвержденных преподавателей. Создание задачи отменено.")
        await state.clear()
        return

    await state.update_data(teacher_page=0)
    await state.set_state(CreateTaskFSM.waiting_for_assignee)
    await show_teacher_selection(message, teachers_data, state)


async def show_teacher_selection(message: Message, teachers_data: dict, state: FSMContext):
    results = teachers_data.get("results", [])
    current_page = teachers_data.get("current_page", 0)
    total_pages = teachers_data.get("total_pages", 1)

    if not results:
        await message.answer("❗ Нет доступных преподавателей.")
        return

    text = f"Выберите преподавателя для назначения задачи 👇\n\nСтраница {current_page + 1} из {total_pages}"

    keyboard_rows = []
    for teacher in results:
        teacher_name = f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip()
        teacher_id = teacher.get('id')
        keyboard_rows.append([
            InlineKeyboardButton(
                text=teacher_name,
                callback_data=f"task_select_teacher_{teacher_id}"
            )
        ])

    nav_row = []
    if current_page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"task_teachers_page_{current_page - 1}"
        ))
    if current_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"task_teachers_page_{current_page + 1}"
        ))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_create_task")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.regexp(r"^task_teachers_page_(\d+)$"))
async def handle_teacher_page_navigation(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    page = int(callback.data.split("_")[-1])

    teachers_data = await TSUTeachers.get_teachers_page(telegram_id, page=page, page_size=PAGE_SIZE)
    await state.update_data(teacher_page=page)

    results = teachers_data.get("results", [])
    current_page = teachers_data.get("current_page", 0)
    total_pages = teachers_data.get("total_pages", 1)

    text = f"Выберите преподавателя для назначения задачи 👇\n\nСтраница {current_page + 1} из {total_pages}"

    keyboard_rows = []
    for teacher in results:
        teacher_name = f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip()
        teacher_id = teacher.get('id')
        keyboard_rows.append([
            InlineKeyboardButton(
                text=teacher_name,
                callback_data=f"task_select_teacher_{teacher_id}"
            )
        ])

    nav_row = []
    if current_page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"task_teachers_page_{current_page - 1}"
        ))
    if current_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"task_teachers_page_{current_page + 1}"
        ))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_create_task")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard)

    await callback.answer()


@router.callback_query(F.data.regexp(r"^task_select_teacher_(\d+)$"))
async def handle_teacher_selection(callback: CallbackQuery, state: FSMContext):
    teacher_id = int(callback.data.split("_")[-1])
    await state.update_data(assignee_id=teacher_id)

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    await state.set_state(CreateTaskFSM.waiting_for_deadline_date)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="task_skip_deadline")]
    ])
    await callback.message.answer(
        "Введите дату дедлайна в формате ДД-ММ-ГГГГ (например, 16-12-2025) 👇",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "task_skip_deadline", CreateTaskFSM.waiting_for_deadline_date)
async def skip_task_deadline(callback: CallbackQuery, state: FSMContext):
    await state.update_data(deadline=None)
    await state.set_state(CreateTaskFSM.waiting_for_reminders_choice)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Использовать напоминания по умолчанию", callback_data="task_reminders_default")],
        [InlineKeyboardButton(text="🔕 Без напоминаний", callback_data="task_reminders_none")]
    ])

    try:
        await callback.message.edit_text(
            "Выберите настройку напоминаний 👇\n\n"
            "• По умолчанию, за 15 минут до дедлайна\n"
            "• Без напоминаний: уведомления не будут отправляться",
            reply_markup=keyboard
        )
    except TelegramBadRequest:
        await callback.message.answer(
            "Выберите настройку напоминаний 👇\n\n"
            "• По умолчанию, за 15 минут до дедлайна\n"
            "• Без напоминаний: уведомления не будут отправляться",
            reply_markup=keyboard
        )

    await callback.answer()


@router.message(CreateTaskFSM.waiting_for_deadline_date)
async def handle_task_deadline_date(message: Message, state: FSMContext):
    date_input = (message.text or "").strip()

    try:
        dt = datetime.strptime(date_input, "%d-%m-%Y")
        if dt.date() < datetime.now().date():
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="task_skip_deadline")]
            ])
            await message.answer(
                "❗ Дата в прошлом. Введите будущую дату в формате ДД-ММ-ГГГГ.",
                reply_markup=keyboard
            )
            return
    except ValueError:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="task_skip_deadline")]
        ])
        await message.answer(
            "❗ Неверный формат. Введите дату как ДД-ММ-ГГГГ (например, 16-12-2025).",
            reply_markup=keyboard
        )
        return

    date_iso = dt.strftime("%Y-%m-%d")
    await state.update_data(deadline_date=date_iso)
    await state.set_state(CreateTaskFSM.waiting_for_deadline_time)
    await message.answer("Введите время дедлайна в формате ЧЧ:ММ (например, 14:30) 👇")


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.strptime(value.strip(), "%H:%M")
    except ValueError:
        return None


@router.message(CreateTaskFSM.waiting_for_deadline_time)
async def handle_task_deadline_time(message: Message, state: FSMContext):
    time_input = (message.text or "").strip()
    time_dt = _parse_time(time_input)

    if not time_dt:
        await message.answer("❗ Неверный формат. Введите время как ЧЧ:ММ (например, 14:30).")
        return

    data = await state.get_data()
    deadline_date = data.get("deadline_date")

    if not deadline_date:
        await message.answer("❗ Ошибка: дата дедлайна не найдена. Попробуйте начать заново.")
        return

    try:
        deadline_datetime_local = datetime.strptime(f"{deadline_date} {time_input}", "%Y-%m-%d %H:%M")

        if deadline_datetime_local < datetime.now():
            await message.answer("❗ Дедлайн не может быть в прошлом. Введите будущее время.")
            return

        tomsk_tz = timezone(timedelta(hours=7))
        deadline_datetime_aware = deadline_datetime_local.replace(tzinfo=tomsk_tz)

        deadline_datetime_utc = deadline_datetime_aware.astimezone(timezone.utc)

        deadline_iso = deadline_datetime_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        await message.answer("❗ Ошибка при обработке даты и времени. Попробуйте снова.")
        return

    await state.update_data(deadline=deadline_iso)
    await state.set_state(CreateTaskFSM.waiting_for_reminders_choice)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Использовать напоминания по умолчанию", callback_data="task_reminders_default")],
        [InlineKeyboardButton(text="⚙️ Настроить напоминания", callback_data="task_reminders_custom")],
        [InlineKeyboardButton(text="🔕 Без напоминаний", callback_data="task_reminders_none")]
    ])

    await message.answer(
        "Выберите настройку напоминаний 👇\n\n"
        "• По умолчанию: за 15 минут до дедлайна\n"
        "• Настроить: выбрать свои варианты напоминаний\n"
        "• Без напоминаний: уведомления не будут отправляться",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "task_reminders_default")
async def handle_reminders_default(callback: CallbackQuery, state: FSMContext):
    await state.update_data(reminders=None)
    await show_task_confirmation(callback, state)
    await callback.answer()


@router.callback_query(F.data == "task_reminders_none")
async def handle_reminders_none(callback: CallbackQuery, state: FSMContext):
    await state.update_data(reminders=[])
    await show_task_confirmation(callback, state)
    await callback.answer()


@router.callback_query(F.data == "task_reminders_custom")
async def handle_reminders_custom(callback: CallbackQuery, state: FSMContext):
    await state.update_data(selected_reminders=[])
    await state.set_state(CreateTaskFSM.waiting_for_custom_reminders)
    await show_reminders_selection(callback, state)
    await callback.answer()


async def show_reminders_selection(callback: CallbackQuery, state: FSMContext):
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
                callback_data=f"task_reminder_toggle_{minutes}"
            )
        ])

    if selected_reminders:
        keyboard_rows.append([
            InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="task_reminder_confirm")
        ])

    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="task_reminder_back")
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


@router.callback_query(F.data.regexp(r"^task_reminder_toggle_(\d+)$"), CreateTaskFSM.waiting_for_custom_reminders)
async def handle_reminder_toggle(callback: CallbackQuery, state: FSMContext):
    minutes = int(callback.data.split("_")[-1])

    data = await state.get_data()
    selected_reminders = data.get("selected_reminders", [])

    if minutes in selected_reminders:
        selected_reminders.remove(minutes)
    else:
        selected_reminders.append(minutes)

    await state.update_data(selected_reminders=selected_reminders)
    await show_reminders_selection(callback, state)
    await callback.answer()


@router.callback_query(F.data == "task_reminder_confirm", CreateTaskFSM.waiting_for_custom_reminders)
async def handle_reminder_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_reminders = data.get("selected_reminders", [])

    if not selected_reminders:
        await callback.answer("❗ Выберите хотя бы одно напоминание", show_alert=True)
        return

    reminders = [{"method": "popup", "minutes": minutes} for minutes in selected_reminders]

    await state.update_data(reminders=reminders)
    await show_task_confirmation(callback, state)
    await callback.answer()


@router.callback_query(F.data == "task_reminder_back", CreateTaskFSM.waiting_for_custom_reminders)
async def handle_reminder_back(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CreateTaskFSM.waiting_for_reminders_choice)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Использовать напоминания по умолчанию", callback_data="task_reminders_default")],
        [InlineKeyboardButton(text="⚙️ Настроить напоминания", callback_data="task_reminders_custom")],
        [InlineKeyboardButton(text="🔕 Без напоминаний", callback_data="task_reminders_none")]
    ])

    try:
        await callback.message.edit_text(
            "Выберите настройку напоминаний 👇\n\n"
            "• По умолчанию: за 15 минут до дедлайна\n"
            "• Настроить: выбрать свои варианты напоминаний\n"
            "• Без напоминаний: уведомления не будут отправляться",
            reply_markup=keyboard
        )
    except TelegramBadRequest:
        await callback.message.answer(
            "Выберите настройку напоминаний 👇\n\n"
            "• По умолчанию: за 15 минут до дедлайна\n"
            "• Настроить: выбрать свои варианты напоминаний\n"
            "• Без напоминаний: уведомления не будут отправляться",
            reply_markup=keyboard
        )

    await callback.answer()


async def show_task_confirmation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    title = data.get("title", "")
    description = data.get("description", "")
    deadline = data.get("deadline")
    assignee_id = data.get("assignee_id")
    reminders = data.get("reminders")

    telegram_id = callback.from_user.id
    teachers_data = await TSUTeachers.get_teachers_page(telegram_id, page=0, page_size=100)
    teacher_name = "Не найден"
    for teacher in teachers_data.get("results", []):
        if teacher.get("id") == assignee_id:
            teacher_name = f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip()
            break

    deadline_text = "Не указан"
    if deadline:
        try:
            dt_utc = datetime.fromisoformat(deadline.replace('Z', '+00:00'))

            tomsk_tz = timezone(timedelta(hours=7))
            dt_local = dt_utc.astimezone(tomsk_tz)

            deadline_text = dt_local.strftime("%d-%m-%Y %H:%M")
        except:
            deadline_text = deadline

    if reminders is None:
        reminders_text = "По умолчанию"
    elif not reminders:
        reminders_text = "Отключены"
    else:
        reminder_labels = []
        for reminder in reminders:
            minutes = reminder.get("minutes", 0)
            if minutes == 15:
                reminder_labels.append("15 минут")
            elif minutes == 30:
                reminder_labels.append("30 минут")
            elif minutes == 60:
                reminder_labels.append("1 час")
            elif minutes == 1440:
                reminder_labels.append("1 день")
            else:
                reminder_labels.append(f"{minutes} минут")
        reminders_text = "За " + ", ".join(reminder_labels)

    summary = (
        "Проверьте данные задачи:\n\n"
        f"📌 Название: {title}\n"
        f"📝 Описание: {description or 'Не указано'}\n"
        f"👨‍🏫 Назначен: {teacher_name}\n"
        f"📅 Дедлайн: {deadline_text}\n"
        f"🔔 Напоминания: {reminders_text}\n\n"
        "Создать задачу?"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_create_task")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_create_task")]
    ])

    await state.set_state(CreateTaskFSM.confirming)

    try:
        await callback.message.edit_text(summary, reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(summary, reply_markup=keyboard)


@router.callback_query(F.data == "cancel_create_task")
async def cancel_create_task(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    await state.clear()

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    await asyncio.create_task(answer_and_delete(callback.message, "❌ Создание задачи отменено.", delay=5))

    await show_main_menu(callback, role)
    await callback.answer()


@router.callback_query(F.data == "confirm_create_task")
async def confirm_create_task(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    data = await state.get_data()
    title = data.get("title")
    description = data.get("description", "")
    deadline = data.get("deadline")
    assignee_id = data.get("assignee_id")
    reminders = data.get("reminders")

    result = await tasks_service.create_task(
        telegram_id=telegram_id,
        title=title,
        description=description,
        deadline=deadline,
        assignee_id=assignee_id,
        reminders=reminders
    )

    if result:
        await callback.message.edit_text("✅ Задача успешно создана!")
        await show_main_menu(callback, role)
    else:
        await callback.message.edit_text("❌ Не удалось создать задачу. Попробуйте позже.")

    await state.clear()
    await callback.answer()

