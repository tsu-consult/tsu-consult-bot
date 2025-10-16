import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, Message

from config import PARSE_MODE


async def delete_msg(bot: Bot, chat_id: int, message_id: int | None):
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest:
        pass
    except Exception as e:
        logging.warning(f"Unable to delete message {message_id}: {e}")

async def answer_and_delete(message: Message, text: str, delay: int = 5):
    msg = await message.answer(text, parse_mode=PARSE_MODE)
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except TelegramBadRequest:
        pass

async def edit_step(message: Message, state: FSMContext, text: str,
                    keyboard: InlineKeyboardMarkup | None = None, msg_id_key: str = "register_msg_id"):
    data = await state.get_data()
    msg_id = data.get(msg_id_key)

    if msg_id:
        try:
            await message.bot.edit_message_text(
                text=text,
                chat_id=message.chat.id,
                message_id=msg_id,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return
        except TelegramBadRequest as e:
            logging.warning("Cannot edit message: %s. Will send new message.", e)

    new_msg = await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.update_data(**{msg_id_key: new_msg.message_id})
