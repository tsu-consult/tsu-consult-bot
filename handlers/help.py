from aiogram import Router, F
from aiogram.types import CallbackQuery
import logging

from services.auth import auth
from services.profile import profile
from services.help_content import help_content
from keyboards.help_keyboard import make_help_menu, make_help_page, make_help_flow_keyboard
from keyboards.main_keyboard import show_main_menu

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "menu_help")
async def open_help_menu(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    logger.info(f"open_help_menu called by {telegram_id}, data={callback.data}")
    role = await auth.get_role(telegram_id)
    teacher_status = None
    if role == "teacher":
        teacher_status = await profile.get_teacher_status(telegram_id)

    kb = await make_help_menu(role, teacher_status)
    await callback.message.edit_text("❓ Справка — выберите раздел:", reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("help_section:"))
async def help_section_callback(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    logger.info(f"help_section_callback called by {telegram_id}, data={callback.data}")
    role = await auth.get_role(telegram_id)
    teacher_status = None
    if role == "teacher":
        teacher_status = await profile.get_teacher_status(telegram_id)

    _, key = callback.data.split(":", 1)

    try:
        text = await help_content.get_section_text(key)
        if not text:
            if key == "student":
                text = (
                    "📘 Руководство пользователя\n\n"
                    "1. Как найти преподавателя\n"
                    "2. Как создать запрос на консультацию\n"
                    "3. Как просмотреть свои консультации\n"
                )
            elif key == "teacher":
                text = (
                    "📗 Руководство пользователя\n\n"
                    "1. Как создать консультацию\n"
                    "2. Как просматривать запросы студентов\n"
                    "3. Как управлять расписанием\n"
                )
            elif key == "guest":
                text = (
                    "👋 Руководство для гостя:\n\n"
                    "1. Регистрация и вход — нажмите кнопку 'Регистрация / Вход' в главном меню.\n"
                    "2. Доступные функции для гостей — только просмотр справки и регистрация.\n"
                    "3. После регистрации вы сможете создавать запросы и смотреть преподавателей.\n"
                )
            else:
                text = (
                    "❓ Частые вопросы (FAQ):\n\n"
                    "Q: Как зарегистрироваться?\nA: Нажмите кнопку 'Регистрация / Вход' в главном меню.\n\n"
                    "Q: Что делать, если не приходит подтверждение?\nA: Проверьте, правильно ли указан Telegram ID в профиле.\n"
                )

        kb = await make_help_page(role, key, teacher_status)

        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logger.exception(f"Failed to edit message for help_section:{key}: {e}")
            try:
                await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
            except Exception as e2:
                logger.exception(f"Failed to send message fallback for help_section:{key}: {e2}")
                await callback.answer("❌ Произошла ошибка при отображении раздела справки.", show_alert=True)
                return

        await callback.answer()
    except Exception as e:
        logger.exception(f"Unhandled error in help_section_callback for key={key}: {e}")
        await callback.answer("❌ Ошибка при открытии раздела справки. Попробуйте ещё раз.", show_alert=True)


@router.callback_query(F.data == "help_back")
async def help_back_callback(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await auth.get_role(telegram_id)

    await show_main_menu(callback, role, edit_message=callback.message)
    await callback.answer()


@router.callback_query(F.data.regexp(r"help_flow:([a-z_]+):(\d+)$"))
async def help_flow_callback(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    logger.info(f"help_flow_callback called by {telegram_id}, data={callback.data}")
    role = await auth.get_role(telegram_id)
    teacher_status = None
    if role == "teacher":
        teacher_status = await profile.get_teacher_status(telegram_id)

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    _, scenario, step_str = parts
    try:
        step = int(step_str)
    except ValueError:
        await callback.answer()
        return

    try:
        raw = await help_content.get_raw()
        content = raw.get("content", {})

        max_steps = 0
        prefix = f"{scenario}_step_"
        for k in content.keys():
            if k.startswith(prefix):
                try:
                    n = int(k[len(prefix):])
                    if n > max_steps:
                        max_steps = n
                except Exception:
                    continue

        if max_steps == 0:
            text = await help_content.get_section_text(scenario)
            kb = await make_help_page(role, scenario, teacher_status)
            try:
                await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception as e:
                logger.exception(f"Failed to edit message for help_flow fallback scenario={scenario}: {e}")
                try:
                    await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
                except Exception as e2:
                    logger.exception(f"Failed to send message fallback for help_flow scenario={scenario}: {e2}")
                    await callback.answer("❌ Произошла ошибка при отображении справки.", show_alert=True)
                    return
            await callback.answer()
            return

        key = f"{scenario}_step_{step}"
        text = content.get(key) or await help_content.get_section_text(key) or ""

        if not text:
            text = "❌ Инструкция недоступна."

        kb = await make_help_flow_keyboard(scenario, step, max_steps)

        try:
            await callback.message.edit_text(text + "\n\n" + (content.get("help_footer", "")), reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logger.exception(f"Failed to edit message for help_flow {scenario} step {step}: {e}")
            try:
                await callback.message.answer(text + "\n\n" + (content.get("help_footer", "")), reply_markup=kb, parse_mode="HTML")
            except Exception as e2:
                logger.exception(f"Failed to send fallback message for help_flow {scenario} step {step}: {e2}")
                await callback.answer("❌ Произошла ошибка при открытии пошаговой инструкции.", show_alert=True)
                return

        await callback.answer()
    except Exception as e:
        logger.exception(f"Unhandled error in help_flow_callback for scenario={scenario}, step={step}: {e}")
        await callback.answer("❌ Ошибка при навигации по инструкции. Попробуйте ещё раз.", show_alert=True)
