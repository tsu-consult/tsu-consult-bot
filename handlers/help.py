import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from keyboards.help_keyboard import make_help_menu, make_help_page, make_help_flow_keyboard
from keyboards.main_keyboard import show_main_menu
from services.help_content import help_content
from services.profile import profile
from utils.auth_utils import ensure_auth

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "guest_faq")
async def guest_faq(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    logger.info(f"guest_faq called by {telegram_id}")

    try:
        text = await help_content.get_section_text("faq")
        if not text:
            text = "❌ Раздел FAQ временно недоступен."
        
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В главное меню", callback_data="guest_to_main")]
            ]
        )

        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.exception(f"Error in guest_faq: {e}")
        await callback.answer("❌ Не удалось открыть раздел справки.", show_alert=True)

@router.callback_query(F.data == "guest_to_main")
async def guest_to_main(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    logger.info(f"guest_to_main called by {telegram_id}")

    greeting = "👋 Привет!\n\nЧтобы продолжить, зарегистрируйтесь или войдите в систему 👇"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Регистрация / Вход", callback_data="start")],
            [InlineKeyboardButton(text="❓ Справка", callback_data="guest_faq")],
        ]
    )

    try:
        await callback.message.edit_text(greeting, reply_markup=kb)
    except Exception:
        await callback.message.answer(greeting, reply_markup=kb)

    await callback.answer()


@router.callback_query(F.data.regexp(r"^menu_help(?::(.+))?$"))
async def open_help_menu(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return
    
    logger.info(f"open_help_menu called by {telegram_id}, data={callback.data}")

    origin = None
    if ":" in callback.data:
        origin = callback.data.split(":", 1)[1]

    teacher_status = None
    if role == "teacher":
        teacher_status = await profile.get_teacher_status(telegram_id)

    kb = await make_help_menu(role, teacher_status, origin)
    await callback.message.edit_text("❓ Справка — выберите раздел:", reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("help_section:"))
async def help_section_callback(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return
    
    logger.info(f"help_section_callback called by {telegram_id}, data={callback.data}")
    teacher_status = None
    if role == "teacher":
        teacher_status = await profile.get_teacher_status(telegram_id)

    parts = callback.data.split(":")
    key = parts[1]
    origin = parts[2] if len(parts) > 2 and parts[2] else None

    try:
        text = await help_content.get_section_text(key)
        if not text:
            text = "❌ Инструкция недоступна."

        kb = await make_help_page(role, key, teacher_status, origin)

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


@router.callback_query(F.data.regexp(r"^help_back(?::(.+))?$"))
async def help_back_callback(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return

    origin = None
    if ":" in callback.data:
        origin = callback.data.split(":", 1)[1]

    teacher_status = None
    if role == "teacher":
        teacher_status = await profile.get_teacher_status(telegram_id)

    kb = await make_help_menu(role, teacher_status, origin)
    try:
        await callback.message.edit_text("❓ Справка — выберите раздел:", reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer("❓ Справка — выберите раздел:", reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.regexp(r"^help_to_main(?::(.+))?$"))
async def help_to_main_callback(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return
    
    logger.info(f"help_to_main called by {telegram_id}, data={callback.data}")

    origin = None
    if ":" in callback.data:
        origin = callback.data.split(":", 1)[1]

    if origin == "tasks_menu":
        from handlers.tasks_menu import show_teacher_tasks_menu
        await show_teacher_tasks_menu(callback)
    else:
        await show_main_menu(callback, role, edit_message=callback.message)
        await callback.answer()


@router.callback_query(F.data.regexp(r"help_flow:([a-z_]+):(\d+)(?::([a-z_]+))?(?::([a-z_]+))?$") )
async def help_flow_callback(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    role = await ensure_auth(telegram_id, callback)
    if not role:
        await callback.answer()
        return
    
    logger.info(f"help_flow_callback called by {telegram_id}, data={callback.data}")
    teacher_status = None
    if role == "teacher":
        teacher_status = await profile.get_teacher_status(telegram_id)

    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return
    _, scenario, step_str, *rest = parts
    origin = rest[0] if rest else "student"
    menu_origin = rest[1] if len(rest) > 1 else None
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
            kb = await make_help_page(role, scenario, teacher_status, menu_origin)
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

        kb = await make_help_flow_keyboard(scenario, step, max_steps, origin=origin, menu_origin=menu_origin)

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
