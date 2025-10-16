from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.consultations import consultations
from utils.auth_utils import ensure_auth
from utils.consultations_utils import format_time

router = Router()
PAGE_SIZE = 3


@router.callback_query(F.data.regexp(r"(student|teacher)_my_consultations(_\d+)?"))
async def view_my_consultations(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    parts = callback.data.split("_")
    page = int(parts[-1]) if parts[-1].isdigit() else 1

    consultations_page = await consultations.get_consultations(telegram_id, page=page, page_size=PAGE_SIZE)
    if not consultations_page or not consultations_page.get("results"):
        await callback.message.edit_text("📅 У вас пока нет консультаций.")
        await callback.answer()
        return

    current_page = consultations_page.get("current_page", 1)
    total_pages = max(consultations_page.get("total_pages", 1), 1)

    text_lines = [f"📅 <b>Мои консультации — страница {current_page} из {total_pages}</b>"]
    for c in consultations_page["results"]:
        start_time = format_time(c["start_time"])
        end_time = format_time(c["end_time"])
        text_lines.append(
            f"\n<b>{c['title']}</b>\n"
            f"📅 {c['date']} | 🕒 {start_time}–{end_time}\n"
            f"👨‍🏫 {c.get('teacher_name', '—')}\n"
            f"👥 Мест: {c.get('max_students', '—')}\n"
            f"📌 Статус: {'Закрыта' if c['is_closed'] else 'Открыта'}"
        )

    keyboard_rows = []

    if current_page > 1:
        keyboard_rows.append([InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"{role}_my_consultations_{current_page - 1}"
        )])

    if current_page < total_pages:
        keyboard_rows.append([InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"{role}_my_consultations_{current_page + 1}"
        )])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()
