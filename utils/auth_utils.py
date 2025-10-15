from aiogram.types import Message, CallbackQuery, BotCommand, BotCommandScopeChat
from handlers import register
from services.auth import auth


async def ensure_auth(telegram_id: int, obj: Message | CallbackQuery, state=None) -> str | None:
    role = await auth.get_role(telegram_id)

    if not role:
        try:
            await auth.login(telegram_id)
            role = await auth.get_role(telegram_id)
        except ValueError:
            if isinstance(obj, CallbackQuery):
                await register.start_registration(obj.message, state)
            else:
                await register.start_registration(obj, state)
            return None

    if role:
        await obj.bot.set_my_commands(
            commands=[BotCommand(command="/home", description="Главное меню")],
            scope=BotCommandScopeChat(chat_id=obj.message.chat.id if isinstance(obj, CallbackQuery) else obj.chat.id)
        )

    return role
