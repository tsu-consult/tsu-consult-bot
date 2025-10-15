from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_paginated_keyboard(data_list: list, page: int, total_pages: int, callback_prefix: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"{item.get('first_name', '')} {item.get('last_name', '')}".strip(),
            callback_data=f"{callback_prefix}_{item['id']}"
        )]
        for item in data_list
    ]

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад", callback_data=f"{callback_prefix}_page_{page-1}"
        ))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="Вперёд ➡️", callback_data=f"{callback_prefix}_page_{page+1}"
        ))

    if nav_buttons:
        buttons.append(nav_buttons)

    return InlineKeyboardMarkup(inline_keyboard=buttons)
