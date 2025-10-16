from aiogram.types import Message, CallbackQuery, BotCommand, BotCommandScopeChat

from keyboards.main_keyboard import show_main_menu
from services.auth import auth


async def ensure_auth(telegram_id: int, obj: Message | CallbackQuery) -> str | None:
    role = await auth.get_role(telegram_id)

    if not role:
        try:
            await auth.login(telegram_id)
            role = await auth.get_role(telegram_id)
        except ValueError:
            await show_main_menu(obj, role=None)
            return None

    if role:
        await obj.bot.set_my_commands(
            commands=[BotCommand(command="/home", description="Главное меню")],
            scope=BotCommandScopeChat(chat_id=obj.message.chat.id if isinstance(obj, CallbackQuery) else obj.chat.id)
        )

    return role
