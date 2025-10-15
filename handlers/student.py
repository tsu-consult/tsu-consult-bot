from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from keyboards.paginated_keyboard import build_paginated_keyboard
from services.teachers import teachers
from utils.auth_utils import ensure_auth

router = Router()
PAGE_SIZE = 3

@router.callback_query(F.data == "student_view_teachers")
async def show_teachers_first_page(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    page_data = await teachers.get_teachers_page(callback.from_user.id, page=0, page_size=PAGE_SIZE)
    keyboard = build_paginated_keyboard(
        data_list=page_data["results"],
        page=page_data["current_page"],
        total_pages=page_data["total_pages"],
        callback_prefix="teacher"
    )
    await callback.message.edit_text(
        "👨‍🏫 Преподаватели\n\n"
        "Нажмите на преподавателя, чтобы посмотреть его расписание или подписаться/отписаться на уведомления о новых консультациях.",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.regexp(r"teacher_page_\d+"))
async def paginate_teachers(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    page = int(callback.data.split("_")[-1])
    page_data = await teachers.get_teachers_page(callback.from_user.id, page=page, page_size=PAGE_SIZE)

    keyboard = build_paginated_keyboard(
        data_list=page_data["results"],
        page=page_data["current_page"],
        total_pages=page_data["total_pages"],
        callback_prefix="teacher"
    )
    await callback.message.edit_text(
        "👨‍🏫 Преподаватели\n\n"
        "Нажмите на преподавателя, чтобы посмотреть его расписание или подписаться/отписаться на уведомления о новых консультациях.",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"teacher_\d+"))
async def show_teacher_schedule(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    teacher_id = int(callback.data.split("_")[1])
    await show_schedule_page(callback, telegram_id, teacher_id, 0)

@router.callback_query(F.data.regexp(r"schedule_\d+_\d+"))
async def paginate_schedule(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    teacher_id, page = map(int, callback.data.split("_")[1:])
    await show_schedule_page(callback, telegram_id, teacher_id, page)

@router.callback_query(F.data.regexp(r"subscribe_\d+"))
async def subscribe_teacher(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    teacher_id = int(callback.data.split("_")[1])

    success = await teachers.subscribe_teacher(telegram_id, teacher_id)
    if success:
        await callback.answer("✅ Вы подписались на обновления преподавателя!", show_alert=True)
        await show_schedule_page(callback, telegram_id, teacher_id, 0)
    else:
        await callback.answer("❌ Не удалось подписаться. Попробуйте позже.", show_alert=True)

@router.callback_query(F.data.regexp(r"unsubscribe_\d+"))
async def unsubscribe_teacher(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    teacher_id = int(callback.data.split("_")[1])

    success = await teachers.unsubscribe_teacher(telegram_id, teacher_id)
    if success:
        await callback.answer("🚫 Подписка отменена.", show_alert=True)
        await show_schedule_page(callback, telegram_id, teacher_id, 0)
    else:
        await callback.answer("❌ Не удалось отписаться. Попробуйте позже.", show_alert=True)



async def show_schedule_page(callback: CallbackQuery, telegram_id: int, teacher_id: int, page: int):
    page_data = await teachers.get_teacher_schedule(telegram_id, teacher_id, page=page, page_size=PAGE_SIZE)
    subscribed_teachers = await teachers.get_subscribed_teachers(telegram_id)
    is_subscribed = any(t["id"] == teacher_id for t in subscribed_teachers)

    if not page_data["results"]:
        await callback.message.edit_text("📅 У этого преподавателя пока нет консультаций.")
        await callback.answer()
        return

    teacher_name = page_data["results"][0].get("teacher_name", "Преподаватель")

    def format_time(t: str) -> str:
        try:
            return datetime.strptime(t, "%H:%M:%S").strftime("%H:%M")
        except ValueError:
            return t

    text_lines = [
        f"👨‍🏫 <b>Расписание консультаций — {teacher_name}</b>\n",
        "Вы можете записаться на доступные консультации (✅) или следить за обновлениями.",
    ]

    for c in page_data["results"]:
        status_emoji = "✅" if not c["is_closed"] else "🔒"
        start_time = format_time(c["start_time"])
        end_time = format_time(c["end_time"])
        text_lines.append(
            f"\n<b>{status_emoji} {c['title']}</b>\n"
            f"📅 {c['date']} | 🕒 {start_time}–{end_time}\n"
            f"👥 Мест: {c['max_students']}\n"
            f"📌 Статус: {'Открыта' if not c['is_closed'] else 'Закрыта'}"
        )

    current_page = page_data["current_page"]
    total_pages = page_data["total_pages"]

    nav_row = []
    if current_page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"schedule_{teacher_id}_{current_page - 1}"))
    if current_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="➡️ Вперёд", callback_data=f"schedule_{teacher_id}_{current_page + 1}"))

    if is_subscribed:
        subscribe_row = [
            InlineKeyboardButton(text="🚫 Отписаться", callback_data=f"unsubscribe_{teacher_id}")
        ]
    else:
        subscribe_row = [
            InlineKeyboardButton(text="🔔 Подписаться", callback_data=f"subscribe_{teacher_id}")
        ]

    back_row = [InlineKeyboardButton(text="🔙 К преподавателям", callback_data="student_view_teachers")]

    keyboard_rows = []
    if nav_row:
        keyboard_rows.append(nav_row)
    keyboard_rows.append(subscribe_row)
    keyboard_rows.append(back_row)

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()