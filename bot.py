import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import start, register, logout, home, profile, student, student_and_teacher, teacher
from services.auth import shutdown


async def main():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(start.router)
    dp.include_router(register.router)
    dp.include_router(logout.router)
    dp.include_router(home.router)
    dp.include_router(profile.router)
    dp.include_router(student.router)
    dp.include_router(student_and_teacher.router)
    dp.include_router(teacher.router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Начать")
    ])

    print("Бот запущен...")

    try:
        await dp.start_polling(bot)
    finally:
        asyncio.run(shutdown())
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())