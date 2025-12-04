import asyncio
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from keyboards.main_keyboard import show_main_menu
from services.profile import profile
from services.tasks import tasks_service
from services.teachers import TSUTeachers
from states.create_task import CreateTaskFSM
from states.update_task import UpdateTaskFSM
from utils.auth_utils import ensure_auth
from utils.messages import answer_and_delete
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
    await state.update_data(deadline=None, reminders=[])
    await show_task_confirmation(callback, state)
    await callback.answer()


@router.message(CreateTaskFSM.waiting_for_deadline_date)
async def handle_task_deadline_date(message: Message, state: FSMContext):
    date_input = (message.text or "").strip()

    try:
        dt = datetime.strptime(date_input, "%d-%m-%Y")
        tomsk_tz = timezone(timedelta(hours=7))
        current_date_tomsk = datetime.now(timezone.utc).astimezone(tomsk_tz).date()
        if dt.date() < current_date_tomsk:
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

        tomsk_tz = timezone(timedelta(hours=7))
        deadline_datetime_aware = deadline_datetime_local.replace(tzinfo=tomsk_tz)

        current_time_tomsk = datetime.now(timezone.utc).astimezone(tomsk_tz)

        if deadline_datetime_aware <= current_time_tomsk:
            current_formatted = current_time_tomsk.strftime("%d.%m.%Y %H:%M")
            deadline_formatted = deadline_datetime_aware.strftime("%d.%m.%Y %H:%M")
            await message.answer(
                f"❗ Дедлайн не может быть в прошлом или настоящем.\n\n"
                f"Текущее время (Томск): {current_formatted}\n"
                f"Указанный дедлайн: {deadline_formatted}\n\n"
                f"Введите будущую дату и время."
            )
            return

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

    summary_parts = [
        "Проверьте данные задачи:\n",
        f"📌 Название: {title}",
        f"📝 Описание: {description or 'Не указано'}",
        f"👨‍🏫 Назначен: {teacher_name}",
        f"📅 Дедлайн: {deadline_text}"
    ]

    if deadline:
        if reminders is None:
            reminders_text = "за 15 минут"
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
        summary_parts.append(f"🔔 Напоминания: {reminders_text}")

    summary_parts.append("\nСоздать задачу?")
    summary = "\n".join(summary_parts)

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


@router.callback_query(F.data == "dean_view_tasks")
async def view_tasks_first_page(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    await show_tasks_page(callback, telegram_id, page=1)


@router.callback_query(F.data.regexp(r"^dean_tasks_page_(\d+)$"))
async def paginate_tasks(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    page = int(callback.data.split("_")[-1])
    await show_tasks_page(callback, telegram_id, page=page)


async def show_tasks_page(callback: CallbackQuery, telegram_id: int, page: int):
    tasks_data = await tasks_service.get_tasks(telegram_id, page=page, page_size=PAGE_SIZE)

    results = tasks_data.get("results", [])
    current_page = tasks_data.get("current_page", page)
    total_pages = max(tasks_data.get("total_pages", 1), 1)

    if not results:
        text = "📋 У вас пока нет задач."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
        ])
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
        return

    text_lines = [f"📋 <b>Список задач — страница {current_page} из {total_pages}</b>"]

    for task in results:
        title = task.get("title", "Без названия")
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
            callback_data=f"dean_choose_task_{current_page}"
        )
    ])

    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"dean_tasks_page_{current_page - 1}"
        ))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"dean_tasks_page_{current_page + 1}"
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


@router.callback_query(F.data.regexp(r"^dean_choose_task_(\d+)$"))
async def choose_task_for_details(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    page = int(callback.data.split("_")[-1])
    await show_task_selection_page(callback, telegram_id, page=page)


async def show_task_selection_page(callback: CallbackQuery, telegram_id: int, page: int):
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
                callback_data=f"dean_task_detail_{task['id']}_{current_page}"
            )
        ])

    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"dean_choose_task_{current_page - 1}"
        ))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"dean_choose_task_{current_page + 1}"
        ))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 К списку задач", callback_data=f"dean_tasks_page_{current_page}")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


async def _show_task_detail(callback: CallbackQuery, telegram_id: int, task_id: int, page: int):
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

    user_reminders = task.get("reminders", [])

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

    can_edit = (user_id == creator_id) or (user_id == assignee_id and user_id != creator_id)

    keyboard_rows = []

    edit_delete_row = []
    if can_edit:
        edit_delete_row.append(InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"dean_edit_task_{task_id}_{page}"))
    if user_id == creator_id:
        edit_delete_row.append(InlineKeyboardButton(text="🗑 Удалить задачу", callback_data=f"dean_delete_task_{task_id}_{page}"))

    if edit_delete_row:
        keyboard_rows.append(edit_delete_row)

    keyboard_rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"dean_choose_task_{page}"),
        InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data.regexp(r"^dean_task_detail_(\d+)_(\d+)$"))
async def view_task_detail(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступ запрещен.", show_alert=True)
        return

    parts = callback.data.split("_")
    task_id = int(parts[-2])
    page = int(parts[-1])

    await _show_task_detail(callback, telegram_id, task_id, page)

@router.callback_query(F.data.regexp(r"^dean_edit_task_(\d+)_(\d+)$"))
async def dean_edit_task_menu(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
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
        [InlineKeyboardButton(text="📝 Название", callback_data="dean_edit_task_title")],
        [InlineKeyboardButton(text="📄 Описание", callback_data="dean_edit_task_description")],
        [InlineKeyboardButton(text="📅 Дедлайн", callback_data="dean_edit_task_deadline")],
        [InlineKeyboardButton(text="👨‍🏫 Назначить исполнителя", callback_data="dean_edit_task_assignee")]
    ]

    if task.get("deadline"):
        keyboard_rows.append([InlineKeyboardButton(text="🔔 Напоминания", callback_data="dean_edit_task_reminders")])

    keyboard_rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"dean_task_detail_{task_id}_{page}"),
        InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data == "dean_edit_task_title")
async def dean_edit_task_title_start(callback: CallbackQuery, state: FSMContext):
    from states.update_task import UpdateTaskFSM

    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    await state.set_state(UpdateTaskFSM.waiting_for_title)

    text = "✏️ Введите новое название задачи:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="dean_cancel_edit_task")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.message(UpdateTaskFSM.waiting_for_title)
async def dean_edit_task_title_process(message: Message, state: FSMContext):
    telegram_id = message.from_user.id

    title = (message.text or "").strip()
    if not title:
        await message.answer("❗ Пожалуйста, введите название задачи.")
        return

    data = await state.get_data()
    task_id = data.get("task_id")
    page = data.get("page")

    if not task_id or page is None:
        await message.answer("❌ Ошибка: не удалось определить задачу. Попробуйте начать заново.")
        await state.clear()
        return

    result = await tasks_service.update_task(telegram_id, task_id, title=title)

    if result:
        text = f"✅ Название задачи успешно изменено на: <b>{title}</b>"
    else:
        text = "❌ Не удалось обновить задачу. Попробуйте позже."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"dean_task_detail_{task_id}_{page}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
    ])

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "dean_edit_task_description")
async def dean_edit_task_description_start(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    data = await state.get_data()
    task = data.get("task")

    await state.set_state(UpdateTaskFSM.waiting_for_description)

    text = "✏️ Введите новое описание задачи:"

    keyboard_rows = []

    if task and task.get("description"):
        keyboard_rows.append([InlineKeyboardButton(text="🗑️ Убрать описание", callback_data="dean_remove_description")])

    keyboard_rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="dean_cancel_edit_task")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.message(UpdateTaskFSM.waiting_for_description)
async def dean_edit_task_description_process(message: Message, state: FSMContext):
    telegram_id = message.from_user.id

    description = (message.text or "").strip()
    if not description:
        await message.answer("❗ Пожалуйста, введите описание задачи.")
        return

    data = await state.get_data()
    task_id = data.get("task_id")
    page = data.get("page")

    if not task_id or page is None:
        await message.answer("❌ Ошибка: не удалось определить задачу. Попробуйте начать заново.")
        await state.clear()
        return

    result = await tasks_service.update_task(telegram_id, task_id, description=description)

    if result:
        text = f"✅ Описание задачи успешно изменено на: <b>{description}</b>"
    else:
        text = "❌ Не удалось обновить задачу. Попробуйте позже."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"dean_task_detail_{task_id}_{page}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
    ])

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "dean_remove_description")
async def dean_remove_description(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    data = await state.get_data()
    task_id = data.get("task_id")
    page = data.get("page")

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
        [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"dean_task_detail_{task_id}_{page}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "dean_edit_task_deadline")
async def dean_edit_task_deadline_start(callback: CallbackQuery, state: FSMContext):
    from states.update_task import UpdateTaskFSM

    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    data = await state.get_data()
    is_creator = data.get("is_creator", False)
    task = data.get("task")

    if not is_creator:
        await callback.answer("❌ Только создатель может редактировать дедлайн задачи.", show_alert=True)
        return

    await state.set_state(UpdateTaskFSM.waiting_for_deadline_date)

    text = "📅 Введите новую дату дедлайна в формате ДД-ММ-ГГГГ (например, 25-12-2025):"

    keyboard_rows = []

    if task and task.get("deadline"):
        keyboard_rows.append([InlineKeyboardButton(text="🗑️ Отменить дедлайн", callback_data="dean_remove_deadline")])

    keyboard_rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="dean_cancel_edit_task")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.message(UpdateTaskFSM.waiting_for_deadline_date)
async def dean_edit_task_deadline_date_process(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    date_input = (message.text or "").strip()

    try:
        dt = datetime.strptime(date_input, "%d-%m-%Y")
        tomsk_tz = timezone(timedelta(hours=7))
        current_date_tomsk = datetime.now(timezone.utc).astimezone(tomsk_tz).date()
        if dt.date() < current_date_tomsk:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="dean_cancel_edit_task")]
            ])
            await message.answer(
                "❗ Дата в прошлом. Введите будущую дату в формате ДД-ММ-ГГГГ.",
                reply_markup=keyboard
            )
            return
    except ValueError:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="dean_cancel_edit_task")]
        ])
        await message.answer(
            "❗ Неверный формат. Введите дату как ДД-ММ-ГГГГ (например, 25-12-2025).",
            reply_markup=keyboard
        )
        return

    date_iso = dt.strftime("%Y-%m-%d")
    await state.update_data(deadline_date=date_iso)
    await state.set_state(UpdateTaskFSM.waiting_for_deadline_time)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="dean_cancel_edit_task")]
    ])
    await message.answer(
        "⏰ Введите время дедлайна в формате ЧЧ:ММ (например, 14:30):",
        reply_markup=keyboard
    )


@router.message(UpdateTaskFSM.waiting_for_deadline_time)
async def dean_edit_task_deadline_time_process(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    time_input = (message.text or "").strip()
    time_dt = _parse_time(time_input)

    if not time_dt:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="dean_cancel_edit_task")]
        ])
        await message.answer(
            "❗ Неверный формат. Введите время как ЧЧ:ММ (например, 14:30).",
            reply_markup=keyboard
        )
        return

    data = await state.get_data()
    deadline_date = data.get("deadline_date")
    task_id = data.get("task_id")
    page = data.get("page")

    if not deadline_date:
        await message.answer("❗ Ошибка: дата дедлайна не найдена. Попробуйте начать заново.")
        await state.clear()
        return

    if not task_id or page is None:
        await message.answer("❌ Ошибка: не удалось определить задачу. Попробуйте начать заново.")
        await state.clear()
        return

    try:
        deadline_datetime_local = datetime.strptime(f"{deadline_date} {time_input}", "%Y-%m-%d %H:%M")

        tomsk_tz = timezone(timedelta(hours=7))
        deadline_datetime_aware = deadline_datetime_local.replace(tzinfo=tomsk_tz)

        current_time_tomsk = datetime.now(timezone.utc).astimezone(tomsk_tz)

        if deadline_datetime_aware <= current_time_tomsk:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="dean_cancel_edit_task")]
            ])
            current_formatted = current_time_tomsk.strftime("%d.%m.%Y %H:%M")
            deadline_formatted = deadline_datetime_aware.strftime("%d.%m.%Y %H:%M")
            await message.answer(
                f"❗ Дедлайн не может быть в прошлом или настоящем.\n\n"
                f"Текущее время (Томск): {current_formatted}\n"
                f"Указанный дедлайн: {deadline_formatted}\n\n"
                f"Введите будущую дату и время.",
                reply_markup=keyboard
            )
            return


        deadline_datetime_utc = deadline_datetime_aware.astimezone(timezone.utc)

        deadline_iso = deadline_datetime_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        result = await tasks_service.update_task(telegram_id, task_id, deadline=deadline_iso)

        if result:
            text = f"✅ Дедлайн успешно изменен на: 📅 {deadline_datetime_local.strftime('%d.%m.%Y')} в ⏰ {time_input}"
        else:
            text = "❌ Не удалось обновить задачу. Попробуйте позже."

    except ValueError:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="dean_cancel_edit_task")]
        ])
        await message.answer("❗ Ошибка при обработке даты и времени. Попробуйте снова.", reply_markup=keyboard)
        await state.clear()
        return
    except Exception as e:
        text = f"❌ Произошла ошибка: {str(e)}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"dean_task_detail_{task_id}_{page}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
    ])

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "dean_remove_deadline")
async def dean_remove_deadline(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    data = await state.get_data()
    task_id = data.get("task_id")
    page = data.get("page")
    is_creator = data.get("is_creator", False)

    if not is_creator:
        await callback.answer("❌ Только создатель может редактировать дедлайн задачи.", show_alert=True)
        return

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
        [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"dean_task_detail_{task_id}_{page}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "dean_edit_task_assignee")
async def dean_edit_task_assignee_start(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    await state.set_state(UpdateTaskFSM.waiting_for_assignee_selection)
    await state.update_data(assignee_page=0)

    await dean_show_assignee_selection_page(callback, state, telegram_id, page=0)


async def dean_show_assignee_selection_page(callback: CallbackQuery, state: FSMContext, telegram_id: int, page: int):
    teachers_data = await TSUTeachers.get_teachers_page(telegram_id, page=page, page_size=PAGE_SIZE)

    results = teachers_data.get("results", [])
    current_page = teachers_data.get("current_page", page)
    total_pages = teachers_data.get("total_pages", 1)

    if not results:
        await callback.answer("❌ Нет доступных преподавателей", show_alert=True)
        return

    text = f"👨‍🏫 <b>Выберите исполнителя для задачи</b>\n\nСтраница {current_page + 1} из {total_pages}"

    keyboard_rows = []

    for teacher in results:
        first_name = teacher.get("first_name", "")
        last_name = teacher.get("last_name", "")
        teacher_id = teacher.get("id")
        full_name = f"{first_name} {last_name}".strip()

        keyboard_rows.append([
            InlineKeyboardButton(
                text=full_name,
                callback_data=f"dean_update_assignee_{teacher_id}"
            )
        ])

    nav_row = []
    if current_page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"dean_assignee_page_{current_page - 1}"
        ))
    if current_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"dean_assignee_page_{current_page + 1}"
        ))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="dean_cancel_edit_task")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data.regexp(r"^dean_assignee_page_(\d+)$"))
async def dean_assignee_page_navigation(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    page = int(callback.data.split("_")[-1])
    await state.update_data(assignee_page=page)
    await dean_show_assignee_selection_page(callback, state, telegram_id, page=page)


@router.callback_query(F.data.regexp(r"^dean_update_assignee_(\d+)$"))
async def dean_update_assignee_process(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    assignee_id = int(callback.data.split("_")[-1])

    data = await state.get_data()
    task_id = data.get("task_id")
    page = data.get("page")

    if not task_id or page is None:
        await callback.answer("❌ Ошибка: не удалось определить задачу.", show_alert=True)
        await state.clear()
        return

    result = await tasks_service.update_task(telegram_id, task_id, assignee_id=assignee_id)

    if result:
        teachers_data = await TSUTeachers.get_teachers_page(telegram_id, page=0, page_size=100)
        teacher = next((t for t in teachers_data.get("results", []) if t.get("id") == assignee_id), None)
        if teacher:
            teacher_name = f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip()
            text = f"✅ Исполнитель успешно изменен на: <b>{teacher_name}</b>"
        else:
            text = "✅ Исполнитель успешно изменен"
    else:
        text = "❌ Не удалось обновить задачу. Попробуйте позже."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"dean_task_detail_{task_id}_{page}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "dean_edit_task_reminders")
async def dean_edit_task_reminders_start(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    await state.set_state(UpdateTaskFSM.waiting_for_reminders_choice)

    text = "Выберите настройку напоминаний 👇\n\n" \
           "• Настроить: выбрать свои варианты напоминаний\n" \
           "• Без напоминаний: уведомления не будут отправляться"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Настроить напоминания", callback_data="dean_reminder_custom")],
        [InlineKeyboardButton(text="🔕 Без напоминаний", callback_data="dean_reminder_none")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="dean_cancel_edit_task")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data == "dean_reminder_none")
async def dean_edit_task_reminders_none(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
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
        [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"dean_task_detail_{task_id}_{page}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "dean_reminder_custom")
async def dean_edit_task_reminders_custom(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    await state.update_data(selected_reminders=[])
    await state.set_state(UpdateTaskFSM.waiting_for_custom_reminders)
    await dean_show_reminders_selection(callback, state)
    await callback.answer()


async def dean_show_reminders_selection(callback: CallbackQuery, state: FSMContext):
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
                callback_data=f"dean_reminder_toggle_{minutes}"
            )
        ])

    if selected_reminders:
        keyboard_rows.append([
            InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="dean_reminder_confirm")
        ])

    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="dean_reminder_back")
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


@router.callback_query(F.data.regexp(r"^dean_reminder_toggle_(\d+)$"), UpdateTaskFSM.waiting_for_custom_reminders)
async def dean_handle_reminder_toggle(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    minutes = int(callback.data.split("_")[-1])

    data = await state.get_data()
    selected_reminders = data.get("selected_reminders", [])

    if minutes in selected_reminders:
        selected_reminders.remove(minutes)
    else:
        selected_reminders.append(minutes)

    await state.update_data(selected_reminders=selected_reminders)
    await dean_show_reminders_selection(callback, state)
    await callback.answer()


@router.callback_query(F.data == "dean_reminder_confirm", UpdateTaskFSM.waiting_for_custom_reminders)
async def dean_handle_reminder_confirm(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
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
        [InlineKeyboardButton(text="⬅️ К задаче", callback_data=f"dean_task_detail_{task_id}_{page}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "dean_reminder_back", UpdateTaskFSM.waiting_for_custom_reminders)
async def dean_handle_reminder_back(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    await state.set_state(UpdateTaskFSM.waiting_for_reminders_choice)

    text = "Выберите настройку напоминаний 👇\n\n" \
           "• Настроить: выбрать свои варианты напоминаний\n" \
           "• Без напоминаний: уведомления не будут отправляться"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Настроить напоминания", callback_data="dean_reminder_custom")],
        [InlineKeyboardButton(text="🔕 Без напоминаний", callback_data="dean_reminder_none")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="dean_cancel_edit_task")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data == "dean_cancel_edit_task")
async def dean_cancel_edit_task(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    data = await state.get_data()
    task_id = data.get("task_id")
    page = data.get("page")

    await state.clear()

    if task_id is not None and page is not None:
        await _show_task_detail(callback, telegram_id, task_id, page)
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


@router.callback_query(F.data == "dean_delete_task_from_menu")
async def dean_delete_task_from_main_menu(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    await dean_show_task_deletion_page(callback, telegram_id, page=1)


@router.callback_query(F.data.regexp(r"^dean_choose_task_delete_(\d+)$"))
async def dean_choose_task_for_deletion(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
        return

    page = int(callback.data.split("_")[-1])
    await dean_show_task_deletion_page(callback, telegram_id, page=page)


async def dean_show_task_deletion_page(callback: CallbackQuery, telegram_id: int, page: int):
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
                    callback_data=f"dean_delete_task_confirm_{task['id']}_{current_page}"
                )
            ])

    if not keyboard_rows:
        await callback.answer("❌ У вас нет задач, которые можно удалить", show_alert=True)
        return

    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"dean_choose_task_delete_{current_page - 1}"
        ))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"dean_choose_task_delete_{current_page + 1}"
        ))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([
        InlineKeyboardButton(text="🔙 К списку задач", callback_data=f"dean_tasks_page_{current_page}")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data.regexp(r"^dean_delete_task_confirm_(\d+)_(\d+)$"))
async def dean_confirm_task_deletion(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
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
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"dean_delete_task_{task_id}_{page}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"dean_task_detail_{task_id}_{page}")
        ]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data.regexp(r"^dean_delete_task_(\d+)_(\d+)$"))
async def dean_delete_task(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if role != "dean":
        await callback.answer("Доступно только для деканата.", show_alert=True)
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
        [InlineKeyboardButton(text="🔙 К списку задач", callback_data=f"dean_tasks_page_{page}")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main_menu")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


