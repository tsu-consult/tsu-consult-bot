import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import start, register, logout, home, profile, student, student_and_teacher, teacher, help, dean, tasks_menu
from services.auth import shutdown

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')


async def main():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(start.router)
    dp.include_router(register.router)
    dp.include_router(logout.router)
    dp.include_router(home.router)
    dp.include_router(profile.router)
    dp.include_router(tasks_menu.router)
    dp.include_router(student.router)
    dp.include_router(student_and_teacher.router)
    dp.include_router(teacher.router)
    dp.include_router(dean.router)
    dp.include_router(help.router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Начать"),
        BotCommand(command="home", description="Главное меню"),
        BotCommand(command="todos", description="Управление задачами")
    ])

    print("Бот запущен...")

    try:
        await dp.start_polling(bot)
    finally:
        asyncio.run(shutdown())
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())