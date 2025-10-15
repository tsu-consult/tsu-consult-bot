from aiogram import Router, F
from aiogram.types import CallbackQuery

from keyboards.paginated_keyboard import build_paginated_keyboard
from services.teachers import teachers
from utils.auth_utils import ensure_auth

router = Router()

@router.callback_query(F.data == "student_view_teachers")
async def show_teachers_first_page(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    page_data = await teachers.get_teachers_page(callback.from_user.id, page=0, page_size=5)
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
    page_data = await teachers.get_teachers_page(callback.from_user.id, page=page, page_size=5)

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
    page_data = await teachers.get_teacher_schedule(callback.from_user.id, teacher_id, page=0, page_size=5)

    if not page_data["results"]:
        await callback.message.edit_text("📅 У этого преподавателя пока нет консультаций.")
        await callback.answer()
        return

    text_lines = [f"📅 Расписание консультаций {page_data['results'][0]['teacher_name']}:\n"]
    for c in page_data["results"]:
        status_emoji = "❌" if c["is_closed"] else "✅"
        text_lines.append(
            f"{status_emoji} {c['title']} — {c['date']} {c['start_time']}–{c['end_time']} "
            f"({c['max_students']} мест)"
        )

    await callback.message.edit_text("\n".join(text_lines))
    await callback.answer()
