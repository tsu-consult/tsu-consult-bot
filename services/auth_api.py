import json
import logging
import requests
import redis
from typing import Optional
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class TSUAuth:
    BASE_URL = config.API_URL

    def __init__(self):
        self.redis = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            decode_responses=True
        )
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.telegram_id: Optional[int] = None

        self.access_ttl = getattr(config, "ACCESS_EXPIRES_IN", 300)
        self.refresh_ttl = getattr(config, "REFRESH_EXPIRES_IN", 86400)

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _save_tokens(self):
        if self.telegram_id and self.access_token and self.refresh_token:
            try:
                self.redis.setex(f"tsu_access:{self.telegram_id}", self.access_ttl, self.access_token)
                self.redis.setex(f"tsu_refresh:{self.telegram_id}", self.refresh_ttl, self.refresh_token)
                logger.info(f"Tokens saved for telegram_id={self.telegram_id} "
                            f"(access TTL={self.access_ttl}s, refresh TTL={self.refresh_ttl}s)")
            except redis.RedisError as e:
                logger.error(f"Redis error (save): {e}")

    def _load_tokens(self):
        if not self.telegram_id:
            return False
        try:
            access_token = self.redis.get(f"tsu_access:{self.telegram_id}")
            refresh_token = self.redis.get(f"tsu_refresh:{self.telegram_id}")

            if access_token and refresh_token:
                self.access_token = access_token
                self.refresh_token = refresh_token
                logger.info(f"Tokens loaded for telegram_id={self.telegram_id}")
                return True
        except redis.RedisError as e:
            logger.error(f"Redis error (load): {e}")
        return False

    def _delete_tokens_from_redis(self):
        if self.telegram_id:
            try:
                self.redis.delete(f"tsu_access:{self.telegram_id}")
                self.redis.delete(f"tsu_refresh:{self.telegram_id}")
                logger.info(f"Tokens deleted from Redis for telegram_id={self.telegram_id}")
            except redis.RedisError as e:
                logger.error(f"Redis error (delete): {e}")
        self.access_token = None
        self.refresh_token = None

    def is_registered(self, telegram_id: int) -> bool:
        self.telegram_id = telegram_id
        try:
            refresh_token = self.redis.get(f"tsu_refresh:{self.telegram_id}")
            access_token = self.redis.get(f"tsu_access:{self.telegram_id}")

            self.refresh_token = refresh_token
            self.access_token = access_token

            if not self.refresh_token:
                try:
                    login_data = self.login(telegram_id)
                    if login_data:
                        return True
                except ValueError:
                    return False

            if not self.access_token:
                try:
                    self._auto_refresh()
                except ValueError as e:
                    if "Пользователь удалён из системы" in str(e):
                        self._delete_tokens_from_redis()
                        return False
                    try:
                        login_data = self.login(telegram_id)
                        if login_data:
                            return True
                    except ValueError:
                        return False

            return True
        except redis.RedisError:
            return False

    def _auto_refresh(self):
        if not self.access_token and self.refresh_token:
            logger.info(f"Access token missing or expired, refreshing for telegram_id={self.telegram_id}")
            self.refresh()

    def get_role(self, telegram_id: int) -> Optional[str]:
        self.telegram_id = telegram_id

        try:
            if not self._load_tokens():
                logger.warning(f"No tokens found in Redis for telegram_id={telegram_id}, trying login()")
                self.login(telegram_id)

            response = self.api_request("GET", f"/profile/")
            if not response:
                logger.error(f"No response from /profile for telegram_id={telegram_id}")
                return None

            role = response.get("role")
            if role in ("student", "teacher"):
                logger.info(f"Detected role={role} for telegram_id={telegram_id}")
                return role

            logger.warning(f"Unknown role '{role}' for telegram_id={telegram_id}")
            return None
        except ValueError as e:
            logger.error(f"Failed to get role for telegram_id={telegram_id}: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error while fetching role for telegram_id={telegram_id}: {e}")
            return None

    @staticmethod
    def _extract_error_message(data):
        if isinstance(data, dict):
            messages = []
            for value in data.values():
                if isinstance(value, list):
                    messages.append(str(value[0]))
                else:
                    messages.append(str(value))
            return " ".join(messages)
        elif isinstance(data, list):
            return " ".join(map(str, data))
        return str(data)

    @staticmethod
    def _translate_error(text: str) -> str:
        text_lower = text.lower()

        translations = {
            "user already exists": "Такой пользователь уже существует.",
            "phone number already exists": "Этот номер телефона уже используется.",
            "invalid phone number": "Некорректный номер телефона.",
            "invalid credentials": "Неверные данные для входа.",
            "missing field": "Не заполнено обязательное поле.",
            "password too short": "Слишком короткий пароль.",
            "username": "Некорректное имя пользователя или пользователь уже существует.",
            "email already exists": "Эта почта уже используется.",
            "internal server error": "Ошибка на сервере. Попробуйте позже.",
            "permission denied": "Доступ запрещён."
        }

        for eng, rus in translations.items():
            if eng in text_lower:
                return rus

        return text.capitalize()


    # Endpoints
    def api_request(self, method: str, endpoint: str, **kwargs):
        self._auto_refresh()
        url = f"{self.BASE_URL}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers.update(self._headers())

        try:
            response = requests.request(method, url, headers=headers, timeout=10, **kwargs)

            if response.status_code == 401 and self.refresh_token:
                logger.info("Access token expired, refreshing and retrying...")
                self.refresh()
                headers = self._headers()
                response = requests.request(method, url, headers=headers, timeout=10, **kwargs)

            if 200 <= response.status_code < 300:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    logger.error("Invalid JSON response from server")
                    raise ValueError("Некорректный ответ от сервера.")
            else:
                logger.error(f"API request failed: {response.status_code} | {response.text}")
                raise ValueError(f"Ошибка API: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during API request: {e}")
            raise ValueError("Ошибка соединения с сервером.")

    def register(self, telegram_id: int, username: str, first_name: str = "",
                 last_name: str = "", phone_number: str = "", role: str = "student"):
        self.telegram_id = telegram_id

        payload = {
            "username": username,
            "telegram_id": telegram_id,
            "first_name": first_name,
            "last_name": last_name,
            "phone_number": phone_number,
            "role": role
        }

        logger.info("Sending register request: %s", payload)

        try:
            response = requests.post(f"{self.BASE_URL}/auth/register/", json=payload, timeout=10)
            logger.info("Register response: %s | %s", response.status_code, response.text)

            if response.status_code not in (200, 201):
                try:
                    error_data = response.json()
                    details = self._extract_error_message(error_data)
                except json.JSONDecodeError:
                    details = response.text or "Unknown error"

                translated = self._translate_error(details)
                error_msg = f"Ошибка регистрации\n\n{translated}"
                raise ValueError(error_msg)

            data = response.json()
            self.access_token = data.get("access")
            self.refresh_token = data.get("refresh")
            self._save_tokens()
            return data
        except requests.exceptions.RequestException as e:
            logger.error("Network error during register: %s", e)
            raise ValueError("Ошибка соединения с сервером. Проверьте интернет или попробуйте позже.")
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from server")
            raise ValueError("Некорректный ответ от сервера.")

    def login(self, telegram_id: int):
        self.telegram_id = telegram_id

        if self._load_tokens():
            logger.info("Tokens found in Redis for telegram_id=%s", telegram_id)
            return {"access": self.access_token, "refresh": self.refresh_token}

        logger.info("Sending login request for telegram_id=%s", telegram_id)
        try:
            response = requests.post(f"{self.BASE_URL}/auth/login/", json={"telegram_id": telegram_id}, timeout=10)
            logger.info("Login response: %s | %s", response.status_code, response.text)

            if response.status_code == 404:
                logger.warning(f"User {telegram_id} not found. Deleting tokens from Redis.")
                self._delete_tokens_from_redis()
                raise ValueError("Пользователь удалён из системы. Пожалуйста, зарегистрируйтесь заново.")

            if response.status_code != 200:
                logger.error("Login failed: %s", response.text)
                raise ValueError("Ошибка авторизации. Попробуйте снова.")

            data = response.json()
            self.access_token = data.get("access")
            self.refresh_token = data.get("refresh")
            self._save_tokens()
            return data
        except requests.exceptions.RequestException as e:
            logger.error("Network error during login: %s", e)
            raise ValueError("Ошибка соединения с сервером.")
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from server")
            raise ValueError("Некорректный ответ от сервера.")

    def refresh(self):
        if not self.refresh_token:
            raise ValueError("Нет refresh_token для обновления")

        logger.info("Refreshing access token for telegram_id=%s", self.telegram_id)
        try:
            response = requests.post(f"{self.BASE_URL}/auth/refresh/", json={"refresh": self.refresh_token}, timeout=10)
            logger.info("Refresh response: %s | %s", response.status_code, response.text)

            if response.status_code == 404:
                logger.warning(f"User {self.telegram_id} not found during refresh. Deleting tokens from Redis.")
                self._delete_tokens_from_redis()
                raise ValueError("Пользователь удалён из системы. Пожалуйста, зарегистрируйтесь заново.")

            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access")
                self._save_tokens()
                logger.info("Access token refreshed successfully")
                return True
            elif response.status_code in (400, 403):
                logger.warning("Refresh token expired, attempting re-login for telegram_id=%s", self.telegram_id)
                try:
                    relog_data = self.login(self.telegram_id)
                    if relog_data:
                        logger.info("Re-login successful, tokens renewed automatically")
                        return True
                except Exception as relog_error:
                    logger.error(f"Auto re-login failed: {relog_error}")
                    raise ValueError("Не удалось обновить токен. Требуется повторная авторизация.")
            else:
                logger.error("Unexpected refresh response: %s", response.text)
                raise ValueError("Ошибка при обновлении токена.")
        except requests.exceptions.RequestException as e:
            logger.error("Network error during refresh: %s", e)
            raise ValueError("Ошибка соединения с сервером.")
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from server")
            raise ValueError("Некорректный ответ от сервера.")

    def logout(self):
        if not self.refresh_token:
            return

        logger.info("Sending logout request for telegram_id=%s", self.telegram_id)
        try:
            response = requests.post(f"{self.BASE_URL}/auth/logout/", json={"refresh": self.refresh_token}, timeout=10)
            logger.info("Logout response: %s | %s", response.status_code, response.text)

            if response.status_code == 200 and self.telegram_id:
                self.redis.delete(f"tsu_access:{self.telegram_id}")
                self.redis.delete(f"tsu_refresh:{self.telegram_id}")
                logger.info("Tokens deleted from Redis for telegram_id=%s", self.telegram_id)
            else:
                logger.error("Logout failed: %s", response.text)
                raise ValueError("Ошибка при выходе из системы.")
        except requests.exceptions.RequestException as e:
            logger.error("Network error during logout: %s", e)
            raise ValueError("Ошибка соединения с сервером.")
        finally:
            self.access_token = None
            self.refresh_token = None
