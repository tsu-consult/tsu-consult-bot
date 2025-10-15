from aiogram import Router, F
from aiogram.types import CallbackQuery

from keyboards.paginated_keyboard import build_paginated_keyboard
from services.teachers import teachers

router = Router()

@router.callback_query(F.data == "student_view_teachers")
async def show_teachers_first_page(callback: CallbackQuery):
    page_data = await teachers.get_teachers_page(page=0, page_size=2)
    keyboard = build_paginated_keyboard(
        data_list=page_data["results"],
        page=page_data["current_page"],
        total_pages=page_data["total_pages"],
        callback_prefix="teacher",
        label_key="username"
    )
    await callback.message.edit_text(
        "👨‍🏫 Список преподавателей",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"teacher_page_\d+"))
async def paginate_teachers(callback: CallbackQuery):
    page = int(callback.data.split("_")[-1])
    page_data = await teachers.get_teachers_page(page=page, page_size=2)

    keyboard = build_paginated_keyboard(
        data_list=page_data["results"],
        page=page_data["current_page"],
        total_pages=page_data["total_pages"],
        callback_prefix="teacher",
        label_key="username"
    )
    await callback.message.edit_text(
        "👨‍🏫 Список преподавателей",
        reply_markup=keyboard
    )
    await callback.answer()
