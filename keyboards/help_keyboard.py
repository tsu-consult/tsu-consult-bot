from aiogram import types
from services.help_content import help_content


async def available_sections(role: str | None, teacher_status: str | None = None) -> list[tuple[str, str]]:
    return await help_content.get_sections(role, teacher_status)


async def make_help_menu(role: str | None, teacher_status: str | None = None) -> types.InlineKeyboardMarkup:
    sections = await available_sections(role, teacher_status)
    buttons = [types.InlineKeyboardButton(text=title, callback_data=f"help_section:{key}") for key, title in sections]
    buttons.append(types.InlineKeyboardButton(text="🔙 В главное меню", callback_data="help_to_main"))
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[b] for b in buttons])
    return kb


async def make_help_page(role: str | None, current_key: str, teacher_status: str | None = None) -> types.InlineKeyboardMarkup:
    secs = await available_sections(role, teacher_status)
    keys = [k for k, _ in secs]
    try:
        idx = keys.index(current_key)
    except ValueError:
        idx = 0

    back_btn = types.InlineKeyboardButton(text="🔙 Назад к разделам", callback_data="help_back")

    inline_keyboard: list[list[types.InlineKeyboardButton]] = []
    
    raw = await help_content.get_raw()
    content = raw.get("content", {})
    step_scenarios: list[tuple[str, str]] = []
    step_prefixes = set()
    for k in content.keys():
        if k.endswith("_step_1") or "_step_" in k:
            if "_step_" in k:
                prefix = k.split("_step_")[0]
                step_prefixes.add(prefix)

    if current_key == "teacher":
        candidate_prefixes = sorted([p for p in step_prefixes if p.startswith("teacher_")])
    else:
        candidate_prefixes = sorted([p for p in step_prefixes if not p.startswith("teacher_")])

    for prefix in candidate_prefixes:
        raw_title = content.get(prefix)
        if raw_title:
            first_line = raw_title.splitlines()[0].strip()
            if first_line.startswith("<b>") and first_line.endswith("</b>"):
                title = first_line[3:-4].strip()
            else:
                title = first_line
        else:
            title = prefix.replace("_", " ").capitalize()
        step_scenarios.append((prefix, title))

    if current_key == "teacher":
        preferred_order = [
            "teacher_registration",
            "teacher_create_slots",
            "teacher_close_cancel",
            "teacher_view_students",
            "teacher_requests",
            "teacher_main_menu",
        ]
    else:
        preferred_order = ["subscribe", "notifications", "navigation"]

    ordered: list[tuple[str, str]] = []
    for p in preferred_order:
        for item in step_scenarios:
            if item[0] == p:
                ordered.append(item)
                break
    for item in step_scenarios:
        if item not in ordered:
            ordered.append(item)
    step_scenarios = ordered

    if current_key in ("student", "teacher") and step_scenarios:
        for sc_key, sc_title in step_scenarios:
            inline_keyboard.append([types.InlineKeyboardButton(text=f"{sc_title}", callback_data=f"help_flow:{sc_key}:1:{current_key}")])

    inline_keyboard.append([back_btn])

    kb = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return kb


async def make_help_flow_keyboard(scenario: str, step: int, max_steps: int, origin: str = "student") -> types.InlineKeyboardMarkup:
    buttons: list[types.InlineKeyboardButton] = []

    if step > 1:
        buttons.append(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"help_flow:{scenario}:{step-1}:{origin}"))
    if step < max_steps:
        buttons.append(types.InlineKeyboardButton(text="Далее ➡️", callback_data=f"help_flow:{scenario}:{step+1}:{origin}"))

    footer = types.InlineKeyboardButton(text="🔙 Назад в руководство", callback_data=f"help_section:{origin}")

    inline_keyboard: list[list[types.InlineKeyboardButton]] = []
    if buttons:
        inline_keyboard.append(buttons)
    inline_keyboard.append([footer])

    return types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
