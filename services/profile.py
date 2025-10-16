import logging
from services.auth import auth

logger = logging.getLogger(__name__)


class TSUProfile:
    @staticmethod
    async def get_profile(telegram_id: int) -> dict | None:
        try:
            auth.telegram_id = telegram_id
            await auth.init_redis()
            await auth.init_session()

            await auth.load_tokens_if_needed()

            response = await auth.api_request("GET", "profile/")
            if not response or "role" not in response:
                logger.warning(f"Profile not found for telegram_id={telegram_id}")
                return None

            return response
        except Exception as e:
            logger.error(f"Error retrieving telegram_id profile={telegram_id}: {e}")
            return None

    async def get_teacher_status(self, telegram_id: int) -> str | None:
        try:
            profile_data = await self.get_profile(telegram_id)
            if profile_data and profile_data.get("role") == "teacher":
                return profile_data.get("status")
        except Exception as e:
            logger.error(f"Error obtaining teacher status: {e}")
        return None

    @staticmethod
    async def update_profile(telegram_id: int, first_name: str, last_name: str) -> bool:
        try:
            auth.telegram_id = telegram_id
            await auth.init_redis()
            await auth.init_session()

            await auth.load_tokens_if_needed()

            payload = {
                "first_name": first_name,
                "last_name": last_name
            }
            response = await auth.api_request("PUT", "profile/", json=payload)

            if response and response.get("first_name") == first_name and response.get("last_name") == last_name:
                logger.info(f"First and last name successfully updated for telegram_id={telegram_id}")
                return True
            else:
                logger.warning(f"Error updating name for telegram_id={telegram_id}: {response}")
        except Exception as e:
            logger.error(f"Error updating name for telegram_id={telegram_id}: {e}")
        return False

    async def format_profile_text(self, telegram_id: int) -> str:
        user_data = await self.get_profile(telegram_id)
        if not user_data:
            return "❌ Профиль не найден. Попробуйте войти снова."

        username = user_data.get("username", "—")
        first_name = user_data.get("first_name", "—")
        last_name = user_data.get("last_name", "—")
        role = user_data.get("role", "—")
        phone_number = user_data.get("phone_number", "—")
        status = user_data.get("status", "—")

        phone_display = phone_number if phone_number.startswith("+") else f"+{phone_number}"

        status_translation = {
            "active": "Активен",
            "pending": "На рассмотрении",
            "rejected": "Отклонён"
        }
        status_text = status_translation.get(status, status)

        if role == "teacher":
            profile_text = (
                f"👤 <b>Мой профиль</b>\n\n"
                f"🪪 <b>Имя:</b> {first_name} {last_name}\n"
                f"📞 <b>Телефон:</b> {phone_display}\n"
                f"💬 <b>Telegram:</b> {username or '—'}\n"
                f"🎓 <b>Роль:</b> Преподаватель\n"
                f"📌 <b>Статус:</b> {status_text}"
            )
        else:
            profile_text = (
                f"👤 <b>Мой профиль</b>\n\n"
                f"🪪 <b>Имя:</b> {first_name} {last_name}\n"
                f"📞 <b>Телефон:</b> {phone_display}\n"
                f"💬 <b>Telegram:</b> {username or '—'}\n"
                f"🎓 <b>Роль:</b> Студент"
            )

        return profile_text

    @staticmethod
    async def resubmit_teacher_request(telegram_id: int) -> bool:
        try:
            auth.telegram_id = telegram_id
            await auth.init_redis()
            await auth.init_session()
            await auth.load_tokens_if_needed()

            response = await auth.api_request("POST", "profile/approval/resubmit/")

            return bool(response)
        except Exception as e:
            import logging
            logging.error(f"Error resubmitting teacher request for telegram_id={telegram_id}: {e}")
            return False


profile = TSUProfile()
