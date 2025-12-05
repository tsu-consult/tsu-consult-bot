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

    async def get_dean_status(self, telegram_id: int) -> str | None:
        try:
            profile_data = await self.get_profile(telegram_id)
            if profile_data and profile_data.get("role") == "dean":
                return profile_data.get("status")
        except Exception as e:
            logger.error(f"Error obtaining dean status: {e}")
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
        email = user_data.get("email", "")

        phone_display = phone_number if phone_number.startswith("+") else f"+{phone_number}"

        show_email = email and not email.endswith("@telegram.local")

        status_translation = {
            "active": "Активен",
            "pending": "На рассмотрении",
            "rejected": "Отклонён"
        }
        status_text = status_translation.get(status, status)

        if role == "teacher":
            is_calendar_connected = await TSUProfile.is_calendar_connected(telegram_id)
            calendar_status = "✅" if is_calendar_connected else "❌"

            profile_text = (
                f"👤 <b>Мой профиль</b>\n\n"
                f"🪪 <b>Имя:</b> {first_name} {last_name}\n"
                f"📞 <b>Телефон:</b> {phone_display}\n"
                f"💬 <b>Telegram:</b> {username or '—'}\n"
                f"🎓 <b>Роль:</b> Преподаватель\n"
                f"📌 <b>Статус:</b> {status_text}\n"
                f"📅 <b>Google Calendar:</b> {calendar_status}"
            )
        elif role == "dean":
            profile_text = (
                f"👤 <b>Мой профиль</b>\n\n"
                f"🪪 <b>Имя:</b> {first_name} {last_name}\n"
                f"📞 <b>Телефон:</b> {phone_display}\n"
                f"💬 <b>Telegram:</b> {username or '—'}\n"
            )
            if show_email:
                profile_text += f"📧 <b>Email:</b> {email}\n"

            is_calendar_connected = await TSUProfile.is_calendar_connected(telegram_id)
            calendar_status = "✅" if is_calendar_connected else "❌"

            profile_text += (
                f"🎓 <b>Роль:</b> Деканат\n"
                f"📌 <b>Статус:</b> {status_text}\n"
                f"📅 <b>Google Calendar:</b> {calendar_status}"
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

    @staticmethod
    async def resubmit_dean_request(telegram_id: int) -> bool:
        try:
            auth.telegram_id = telegram_id
            await auth.init_redis()
            await auth.init_session()
            await auth.load_tokens_if_needed()

            response = await auth.api_request("POST", "profile/approval/resubmit/dean/")

            return bool(response)
        except Exception as e:
            import logging
            logging.error(f"Error resubmitting dean request for telegram_id={telegram_id}: {e}")
            return False
    @staticmethod
    async def get_calendar_auth_url(telegram_id: int) -> str | None:
        try:
            auth.telegram_id = telegram_id
            await auth.init_redis()
            await auth.init_session()
            await auth.load_tokens_if_needed()

            response = await auth.api_request("GET", "profile/calendar/init/")
            logger.info(f"Calendar init API response for telegram_id={telegram_id}: {response}")

            if response and "authorization_url" in response:
                return response["authorization_url"]

            logger.warning(f"Failed to get calendar auth URL for telegram_id={telegram_id}. Response: {response}")
        except Exception as e:
            logger.error(f"Error getting calendar auth URL for telegram_id={telegram_id}: {e}")
        return None

    @staticmethod
    async def disconnect_calendar(telegram_id: int) -> bool:
        try:
            auth.telegram_id = telegram_id
            await auth.init_redis()
            await auth.init_session()
            await auth.load_tokens_if_needed()

            response = await auth.api_request("DELETE", "profile/calendar/disconnect/")
            return bool(response)
        except Exception as e:
            logger.error(f"Error disconnecting calendar for telegram_id={telegram_id}: {e}")
            return False

    @staticmethod
    async def set_calendar_connected(telegram_id: int, connected: bool):
        try:
            await auth.init_redis()
            key = f"calendar_connected:{telegram_id}"
            if connected:
                await auth.redis_flags.set(key, "1", ex=86400 * 365)
            else:
                await auth.redis_flags.delete(key)
            logger.info(f"Set calendar connection status for telegram_id={telegram_id}: {connected}")
        except Exception as e:
            logger.error(f"Error setting calendar connection status for telegram_id={telegram_id}: {e}")

    @staticmethod
    async def is_calendar_connected(telegram_id: int) -> bool:
        try:
            await auth.init_redis()
            key = f"calendar_connected:{telegram_id}"
            result = await auth.redis_flags.get(key)
            is_connected = result == "1" if result else False
            logger.info(f"Calendar connection status for telegram_id={telegram_id}: {is_connected}")
            return is_connected
        except Exception as e:
            logger.error(f"Error checking calendar connection for telegram_id={telegram_id}: {e}")
        return False


profile = TSUProfile()
