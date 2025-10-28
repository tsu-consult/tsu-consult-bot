from aiogram import types


def available_sections(role: str | None, teacher_status: str | None = None) -> list[tuple[str, str]]:
    sections = []
    if role != "teacher":
        sections.append(("student", "📘 Руководство пользователя"))
    if role == "teacher" and teacher_status == "active":
        sections.append(("teacher", "📗 Руководство пользователя"))
    sections.append(("faq", "❓ Частые вопросы (FAQ)"))
    return sections


def make_help_menu(role: str | None, teacher_status: str | None = None) -> types.InlineKeyboardMarkup:
    buttons = [types.InlineKeyboardButton(text=title, callback_data=f"help_section:{key}") for key, title in available_sections(role, teacher_status)]
    buttons.append(types.InlineKeyboardButton(text="🔙 Назад в меню", callback_data="help_back"))
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[b] for b in buttons])
    return kb


def make_help_page(role: str | None, current_key: str, teacher_status: str | None = None) -> types.InlineKeyboardMarkup:
    secs = available_sections(role, teacher_status)
    keys = [k for k, _ in secs]
    try:
        idx = keys.index(current_key)
    except ValueError:
        idx = 0

    nav_buttons: list[types.InlineKeyboardButton] = []
    if idx > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"help_section:{keys[idx-1]}"))
    if idx < len(keys) - 1:
        nav_buttons.append(types.InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"help_section:{keys[idx+1]}"))

    back_btn = types.InlineKeyboardButton(text="🔙 Назад в меню", callback_data="help_back")

    inline_keyboard: list[list[types.InlineKeyboardButton]] = []
    if nav_buttons:
        inline_keyboard.append(nav_buttons)
    inline_keyboard.append([back_btn])

    kb = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return kb
