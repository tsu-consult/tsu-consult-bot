import logging
from services.auth import auth

logger = logging.getLogger(__name__)


class DeanCredentials:
    @staticmethod
    async def add_credentials(telegram_id: int, email: str, password: str) -> tuple[bool, str]:
        try:
            auth.telegram_id = telegram_id
            await auth.init_redis()
            await auth.init_session()
            await auth.load_tokens_if_needed()

            payload = {
                "email": email,
                "password": password
            }

            status, response = await auth.api_request_with_status("POST", "auth/credentials/add/", json=payload)

            if status == 200:
                logger.info(f"Credentials added successfully for telegram_id={telegram_id}")
                return True, ""
            elif status == 400:
                error_msg = response if isinstance(response, str) else "Некорректные данные или учетные данные уже существуют"
                logger.warning(f"Failed to add credentials for telegram_id={telegram_id}: {error_msg}")
                return False, error_msg
            else:
                logger.error(f"Unexpected status {status} when adding credentials for telegram_id={telegram_id}")
                return False, "Ошибка при добавлении учетных данных"

        except Exception as e:
            logger.error(f"Error adding credentials for telegram_id={telegram_id}: {e}")
            return False, "Произошла ошибка при добавлении учетных данных"

    @staticmethod
    async def change_email(telegram_id: int, new_email: str) -> tuple[bool, str]:
        try:
            auth.telegram_id = telegram_id
            await auth.init_redis()
            await auth.init_session()
            await auth.load_tokens_if_needed()

            payload = {
                "new_email": new_email
            }

            status, response = await auth.api_request_with_status("PUT", "profile/change/email/", json=payload)

            if status == 200:
                logger.info(f"Email changed successfully for telegram_id={telegram_id}")
                return True, ""
            elif status == 400:
                error_msg = response if isinstance(response, str) else "Email уже используется или некорректен"
                logger.warning(f"Failed to change email for telegram_id={telegram_id}: {error_msg}")
                return False, error_msg
            elif status == 403:
                return False, "У вас нет учетных данных. Сначала добавьте email и пароль."
            else:
                logger.error(f"Unexpected status {status} when changing email for telegram_id={telegram_id}")
                return False, "Ошибка при изменении email"

        except Exception as e:
            logger.error(f"Error changing email for telegram_id={telegram_id}: {e}")
            return False, "Произошла ошибка при изменении email"

    @staticmethod
    async def change_password(telegram_id: int, current_password: str, new_password: str) -> tuple[bool, str]:
        try:
            auth.telegram_id = telegram_id
            await auth.init_redis()
            await auth.init_session()
            await auth.load_tokens_if_needed()

            payload = {
                "current_password": current_password,
                "new_password": new_password
            }

            status, response = await auth.api_request_with_status("PUT", "profile/change/password/", json=payload)

            if status == 200:
                logger.info(f"Password changed successfully for telegram_id={telegram_id}")
                return True, ""
            elif status == 400:
                error_msg = response if isinstance(response, str) else "Неверный текущий пароль или новый пароль не соответствует требованиям"
                logger.warning(f"Failed to change password for telegram_id={telegram_id}: {error_msg}")
                return False, error_msg
            elif status == 403:
                return False, "У вас нет учетных данных. Сначала добавьте email и пароль."
            else:
                logger.error(f"Unexpected status {status} when changing password for telegram_id={telegram_id}")
                return False, "Ошибка при изменении пароля"

        except Exception as e:
            logger.error(f"Error changing password for telegram_id={telegram_id}: {e}")
            return False, "Произошла ошибка при изменении пароля"

    @staticmethod
    async def has_credentials(telegram_id: int) -> bool:
        try:
            auth.telegram_id = telegram_id
            await auth.init_redis()
            await auth.init_session()
            await auth.load_tokens_if_needed()

            response = await auth.api_request("GET", "profile/")
            email = response.get("email", "")

            return email and not email.endswith("@telegram.local")

        except Exception as e:
            logger.error(f"Error checking credentials for telegram_id={telegram_id}: {e}")
            return False


dean_credentials = DeanCredentials()

