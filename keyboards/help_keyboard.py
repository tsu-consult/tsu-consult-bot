from aiogram import types
from services.help_content import help_content


async def available_sections(role: str | None, teacher_status: str | None = None) -> list[tuple[str, str]]:
    return await help_content.get_sections(role, teacher_status)


async def make_help_menu(role: str | None, teacher_status: str | None = None) -> types.InlineKeyboardMarkup:
    sections = await available_sections(role, teacher_status)
    buttons = [types.InlineKeyboardButton(text=title, callback_data=f"help_section:{key}") for key, title in sections]
    buttons.append(types.InlineKeyboardButton(text="🔙 Назад в меню", callback_data="help_back"))
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[b] for b in buttons])
    return kb


async def make_help_page(role: str | None, current_key: str, teacher_status: str | None = None) -> types.InlineKeyboardMarkup:
    secs = await available_sections(role, teacher_status)
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
    
    raw = await help_content.get_raw()
    content = raw.get("content", {})
    step_prefix = f"{current_key}_step_"
    has_steps = any(k.startswith(step_prefix) for k in content.keys())
    if has_steps:
        inline_keyboard.append([types.InlineKeyboardButton(text="📖 Пошаговая инструкция", callback_data=f"help_flow:{current_key}:1")])

    inline_keyboard.append([back_btn])

    kb = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return kb


async def make_help_flow_keyboard(scenario: str, step: int, max_steps: int) -> types.InlineKeyboardMarkup:
    buttons: list[types.InlineKeyboardButton] = []

    if step > 1:
        buttons.append(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"help_flow:{scenario}:{step-1}"))
    if step < max_steps:
        buttons.append(types.InlineKeyboardButton(text="Далее ➡️", callback_data=f"help_flow:{scenario}:{step+1}"))

    footer = types.InlineKeyboardButton(text="🔙 Назад в меню", callback_data="help_back")

    inline_keyboard: list[list[types.InlineKeyboardButton]] = []
    if buttons:
        inline_keyboard.append(buttons)
    inline_keyboard.append([footer])

    return types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
