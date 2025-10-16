from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.consultations import consultations
from utils.auth_utils import ensure_auth
from utils.consultations_utils import format_time, format_date_verbose, format_datetime_verbose

router = Router()
PAGE_SIZE = 3
STATUS_RU = {
    "open": "Открыт",
    "accepted": "Принят",
    "closed": "Закрыт"
}


@router.callback_query(F.data.regexp(r"(student|teacher)_my_consultations(_\d+)?"))
async def view_my_consultations(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    if callback.data.startswith(f"{role}_my_consultations"):
        parts = callback.data.split("_")
        page = int(parts[-1]) if len(parts) > 2 and parts[-1].isdigit() else 1
    else:
        page = 1

    consultations_page = await consultations.get_consultations(
        telegram_id,
        page=page,
        page_size=PAGE_SIZE
    )

    if not consultations_page or not consultations_page.get("results"):
        await callback.message.edit_text("📅 У вас пока нет консультаций.")
        await callback.answer()
        return

    current_page = consultations_page.get("current_page", 1)
    total_pages = max(consultations_page.get("total_pages", 1), 1)

    text_lines = [f"📅 <b>Мои консультации — страница {current_page} из {total_pages}</b>"]
    cancellable_consultations_exist = False

    for c in consultations_page["results"]:
        start_time = format_time(c["start_time"])
        end_time = format_time(c["end_time"])
        formatted_date = format_date_verbose(c["date"])

        if role == "student" and c["status"] == "active":
            cancellable_consultations_exist = True

        text_lines.append(
            f"\n<b>{c['title']}</b>\n"
            f"📅 {formatted_date}\n"
            f"🕒 {start_time} – {end_time}\n"
            f"👨‍🏫 {c.get('teacher_name', '—')}\n"
            f"👥 Мест: {c.get('max_students', '—')}\n"
            f"📌 Статус: {'Закрыта' if c['is_closed'] else 'Открыта'}"
        )

    keyboard_rows = []

    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"{role}_my_consultations_{current_page - 1}"
        ))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"{role}_my_consultations_{current_page + 1}"
        ))
    if nav_row:
        keyboard_rows.append(nav_row)

    if role == "student" and cancellable_consultations_exist:
        keyboard_rows.append([InlineKeyboardButton(
            text="❌ Отменить запись",
            callback_data=f"student_cancel_consultations_{current_page}"
        )])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "student_requests")
async def view_requests(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    await show_requests_page(callback, telegram_id, role, page=1)


@router.callback_query(F.data.regexp(r"(student|teacher)_requests_\d+"))
async def paginate_requests(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    page = int(callback.data.split("_")[-1])
    await show_requests_page(callback, telegram_id, role, page=page)

@router.callback_query(F.data.regexp(r"choose_request_subscribe_\d+"))
async def choose_request_to_subscribe(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    page = int(callback.data.split("_")[-1])

    requests_page = await consultations.get_requests(telegram_id, role=role, page=page, page_size=PAGE_SIZE)

    if not requests_page or not requests_page.get("results"):
        await callback.answer("❌ Нет запросов", show_alert=True)
        return

    keyboard_rows = []
    for r in requests_page["results"]:
        title = r.get("title", "Без названия")
        status = STATUS_RU.get(r.get("status"), r.get("status", "—"))
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"{title} — {status}",
                callback_data=f"subscribe_request_{r['id']}_{page}"
            )
        ])

    keyboard_rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{role}_requests_{page}")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(
        "Выберите запрос, на который хотите подписаться 👇",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.regexp(r"subscribe_request_\d+_\d+"))
async def subscribe_to_request(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    _, _, request_id_str, page_str = callback.data.split("_")
    request_id = int(request_id_str)
    page = int(page_str)

    success = await consultations.subscribe_request(telegram_id, request_id)
    if success:
        await callback.answer("✅ Вы подписались на обновления запроса!", show_alert=True)
    else:
        await callback.answer("❌ Не удалось подписаться. Возможно, вы уже подписаны. Попробуйте позже.", show_alert=True)

    await show_requests_page(callback, telegram_id, role, page=page)


async def show_requests_page(callback: CallbackQuery, telegram_id: int, role: str, page: int):
    requests_page = await consultations.get_requests(telegram_id, role=role, page=page, page_size=PAGE_SIZE)

    if not requests_page or not requests_page.get("results"):
        await callback.message.edit_text("📄 Нет запросов на консультацию.")
        await callback.answer()
        return

    current_page = requests_page.get("current_page", 1)
    total_pages = max(requests_page.get("total_pages", 1), 1)

    text_lines = [f"📄 <b>Запросы на консультацию — страница {current_page} из {total_pages}</b>"]

    for r in requests_page["results"]:
        student = r.get("student") or {}
        student_name = f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()
        created_at = format_datetime_verbose(r.get("created_at"))
        status_ru = STATUS_RU.get(r.get("status"), r.get("status", "—"))

        text_lines.append(
            f"\n<b>{r['title']}</b>\n"
            f"{r['description']}\n"
            f"👤 Студент: {student_name} ({student.get('username', '—')})\n"
            f"📅 Создан: {created_at}\n"
            f"📌 Статус: {status_ru}"
        )

    keyboard_rows = []

    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"{role}_requests_{current_page - 1}"
        ))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="➡️ Вперёд",
            callback_data=f"{role}_requests_{current_page + 1}"
        ))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([
        InlineKeyboardButton(text="🔔 Подписаться", callback_data=f"choose_request_subscribe_{current_page}")
    ])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()
